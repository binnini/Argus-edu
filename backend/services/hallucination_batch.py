"""
hallucination_batch.py — LLM 기반 배치 할루시네이션 검증 서비스 (ADR-026).

동작 방식:
  1. APScheduler가 BATCH_INTERVAL_SECONDS 마다 run_batch() 호출
  2. grading_results WHERE hallucination_status='pending' LIMIT BATCH_SIZE 조회
  3. LLM에게 N건을 한 번에 전달 → JSON 배열 응답 수신
  4. hallucination_score / hallucination_issues / hallucination_status 갱신

LLM 판단 기준:
  - student_mistakes가 grading_steps의 오답 단계와 일치하는가
  - correct_approach가 reference_solution에 근거해 수학적으로 올바른가
  - key_concept이 실제 오류 원인을 정확히 짚는가

검증 모델: LLM_PROVIDER 기반 LLMClient 사용 (기본: mlx / gemma4:e4b)
"""

import asyncio
import json
import logging
import re
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from db import SessionLocal
from models.grading_result import GradingResult
from models.submission import Submission
from models.problem import Problem
from services.llm_client import LLMClient

logger = logging.getLogger(__name__)

BATCH_SIZE = 8          # LLM context에 한 번에 넣을 최대 건수
MAX_TOKENS = 1024       # 배치 검증 응답은 짧음

HALLUCINATION_SYSTEM_PROMPT = """\
당신은 수학 교육 AI 피드백 품질 검증 전문가입니다.
아래 채점 피드백들이 학생의 실제 오류를 정확히 짚고 올바른 교정 방향을 제시하는지 검증하세요.

각 항목에 대해 다음 세 가지를 확인하세요:
1. student_mistakes가 grading_steps에서 오답 처리된 단계와 일치하는가
2. correct_approach가 reference_solution을 근거로 수학적으로 올바른가
3. key_concept이 학생의 실제 오류 원인을 정확히 설명하는가

반드시 아래 JSON 배열 형식으로만 응답하세요. 다른 텍스트는 절대 포함하지 마세요.
[
  {
    "id": <grading_result_id>,
    "is_valid": <true|false>,
    "confidence": <0.0~1.0>,
    "issues": ["<문제점 설명>"]
  }
]
issues는 is_valid=true이면 빈 배열 []로 응답하세요."""

HALLUCINATION_USER_TEMPLATE = """\
[검증 대상 피드백 목록]
{items_json}"""


class HallucinationBatchService:
    """배치 LLM 할루시네이션 검증 서비스."""

    def __init__(self, llm_client: LLMClient) -> None:
        self._llm = llm_client
        self._run_lock = asyncio.Lock()

    async def run_batch(self, limit: int | None = None) -> int:
        """
        pending 항목을 최대 limit 또는 BATCH_SIZE건 가져와 LLM으로 검증.
        채점(grading)이 진행 중이면 GPU를 양보하고 이번 회차를 건너뜀.
        처리된 건수를 반환.
        """
        if self._run_lock.locked():
            logger.info("할루시네이션 배치가 이미 실행 중 → 이번 회차 건너뜀")
            return 0

        async with self._run_lock:
            return await self._run_batch_locked(limit=limit)

    async def run_one(self, grading_result_id: int) -> int:
        """Verify one specific grading result."""
        if self._run_lock.locked():
            logger.info("할루시네이션 배치가 이미 실행 중 → 단건 검증 건너뜀")
            return 0

        async with self._run_lock:
            async with SessionLocal() as db:
                stmt = (
                    select(GradingResult, Submission, Problem)
                    .join(Submission, Submission.id == GradingResult.submission_id)
                    .join(Problem, Problem.id == Submission.problem_id)
                    .where(
                        GradingResult.id == grading_result_id,
                        GradingResult.hallucination_status == "pending",
                    )
                )
                rows = await db.execute(stmt)
                items = list(rows.tuples())
                if not items:
                    return 0
                gr = items[0][0]
                gr.hallucination_status = "running"
                await db.commit()

            try:
                verdicts = await self._call_llm(items)
            except Exception as e:
                logger.error(f"할루시네이션 LLM 단건 호출 실패: {e}")
                await self._mark_failed([grading_result_id])
                return 0

            await self._apply_verdicts([grading_result_id], verdicts)
            return 1

    async def _run_batch_locked(self, limit: int | None = None) -> int:
        """Run one hallucination batch while protected by the service lock."""
        # 채점 우선 처리: grading_inflight > 0 이면 이번 배치를 스킵하고 다음 인터벌에 재시도
        if self._llm.grading_inflight > 0:
            logger.info(
                f"채점 진행 중 (inflight={self._llm.grading_inflight}) "
                "→ 할루시네이션 배치 이번 회차 건너뜀"
            )
            return 0

        batch_limit = limit or BATCH_SIZE

        async with SessionLocal() as db:
            items = await self._fetch_pending(db, batch_limit)
            if not items:
                return 0

            logger.info(f"할루시네이션 배치 검증 시작: {len(items)}건")

            # running 상태로 표시 (중복 처리 방지)
            ids = [gr.id for gr, _, _ in items]
            for gr, _, _ in items:
                gr.hallucination_status = "running"
            await db.commit()

        try:
            verdicts = await self._call_llm(items)
        except Exception as e:
            logger.error(f"할루시네이션 LLM 호출 실패: {e}")
            await self._mark_failed(ids)
            return 0

        await self._apply_verdicts(ids, verdicts)
        logger.info(f"할루시네이션 배치 검증 완료: {len(ids)}건")
        return len(ids)

    async def _fetch_pending(
        self, db: AsyncSession, limit: int
    ) -> list[tuple]:
        """pending 상태 GradingResult + 연관 Submission + Problem 조회."""
        stmt = (
            select(GradingResult, Submission, Problem)
            .join(Submission, Submission.id == GradingResult.submission_id)
            .join(Problem, Problem.id == Submission.problem_id)
            .where(GradingResult.hallucination_status == "pending")
            .order_by(GradingResult.graded_at.asc())
            .limit(limit)
        )
        rows = await db.execute(stmt)
        return list(rows.tuples())

    async def _call_llm(self, items: list[tuple]) -> list[dict]:
        """LLM에 배치 전달 후 JSON 배열 파싱."""
        batch_input = []
        for gr, sub, prob in items:
            feedback = json.loads(gr.ai_feedback) if gr.ai_feedback else {}
            batch_input.append({
                "id": gr.id,
                "reference_solution": (prob.reference_solution or "")[:800],
                "grading_steps": self._parse_steps(gr),
                "student_answer": (sub.student_answer or "")[:800],
                "student_mistakes": feedback.get("student_mistakes", []),
                "correct_approach": feedback.get("correct_approach", []),
                "key_concept": feedback.get("key_concept", ""),
            })

        user_prompt = HALLUCINATION_USER_TEMPLATE.format(
            items_json=json.dumps(batch_input, ensure_ascii=False, indent=2)
        )

        response = await asyncio.wait_for(
            self._llm.chat(
                system_prompt=HALLUCINATION_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                model=settings.feedback_model,
                max_tokens=MAX_TOKENS,
                temperature=0.1,   # 검증은 결정론적으로
            ),
            timeout=settings.llm_timeout_seconds,
        )

        return self._parse_verdicts(response.text)

    def _parse_steps(self, gr: GradingResult) -> list[dict]:
        """Return persisted grading steps used as feedback verification evidence."""
        try:
            steps = json.loads(gr.grading_steps or "[]")
        except (TypeError, json.JSONDecodeError):
            return []
        return steps if isinstance(steps, list) else []

    def _parse_verdicts(self, raw: str) -> list[dict]:
        """LLM 응답에서 JSON 배열 추출."""
        text = raw.strip()

        # 코드 블록 제거
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])

        # JSON 배열 추출 (앞뒤 텍스트 대비)
        match = re.search(r'\[.*\]', text, re.DOTALL)
        if match:
            text = match.group(0)

        try:
            verdicts = json.loads(text)
        except json.JSONDecodeError:
            text = re.sub(r'\\(?!["\\/bfnrtu])', r'\\\\', text)
            verdicts = json.loads(text)

        if not isinstance(verdicts, list):
            raise ValueError(f"LLM 응답이 배열이 아닙니다: {raw[:200]}")

        return verdicts

    async def _apply_verdicts(self, ids: list[int], verdicts: list[dict]) -> None:
        """LLM 판정을 DB에 반영."""
        verdict_map = {v["id"]: v for v in verdicts if isinstance(v.get("id"), int)}
        now = datetime.now(tz=timezone.utc)

        async with SessionLocal() as db:
            stmt = select(GradingResult).where(GradingResult.id.in_(ids))
            rows = await db.execute(stmt)
            records = list(rows.scalars())

            for gr in records:
                v = verdict_map.get(gr.id)
                if v is None:
                    logger.warning(f"GradingResult id={gr.id} 에 대한 판정 없음 → failed")
                    gr.hallucination_status = "failed"
                    continue

                is_valid: bool = bool(v.get("is_valid", True))
                confidence: float = float(v.get("confidence", 0.5))
                issues: list = v.get("issues", [])

                # hallucination_score = trust_score:
                #   is_valid=True  → confidence (피드백 신뢰 가능)
                #   is_valid=False → 1 - confidence (피드백 신뢰 불가)
                trust_score = round(confidence if is_valid else 1.0 - confidence, 4)
                gr.hallucination_score = trust_score
                gr.trust_score = trust_score
                gr.trust_level = "high" if trust_score >= settings.trust_threshold else "low"
                gr.hallucination_issues = json.dumps(issues, ensure_ascii=False) if issues else None
                gr.hallucination_status = "done"
                gr.hallucination_checked_at = now

            await db.commit()

    async def _mark_failed(self, ids: list[int]) -> None:
        """LLM 호출 실패 시 pending으로 롤백 (재시도 가능하게)."""
        async with SessionLocal() as db:
            stmt = select(GradingResult).where(GradingResult.id.in_(ids))
            rows = await db.execute(stmt)
            for gr in rows.scalars():
                gr.hallucination_status = "pending"
            await db.commit()
