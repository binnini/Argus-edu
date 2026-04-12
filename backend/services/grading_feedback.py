"""
grading_feedback.py — 채점 + 개인화 피드백 통합 서비스 (단일 LLM 호출).

기존 grading.py + feedback.py의 4회 LLM 호출을 1회로 통합.
- 채점 결과(grading) + 개인화 피드백(feedback) 동시 생성
- HHEM/SBERT 할루시네이션 검증 제거 (배치 검증으로 대체 예정)
- inconsistency_rate 제거 (단일 샘플링)
"""

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from typing import Any

from sentence_transformers import SentenceTransformer

from config import settings
from services.llm_client import LLMClient

logger = logging.getLogger(__name__)


COMBINED_SYSTEM_PROMPT = """\
당신은 한국 수학 채점 및 개인화 피드백 전문가입니다.
학생 답변을 루브릭 기준으로 단계별 채점하고, 학생의 오류를 분석한 개인화 피드백을 작성하세요.
반드시 아래 JSON 형식으로만 응답하세요. 수학적 사실에 근거하지 않는 내용은 절대 포함하지 마세요."""

COMBINED_USER_TEMPLATE = """\
[문제]
{problem_content}

[정답]
{answer}

[참조 풀이]
{reference_solution}

[채점 루브릭]
{rubric_json}

[학생 답변]
{student_answer}

위 루브릭에 따라 채점하고, 학생의 오류를 분석한 개인화 피드백을 작성하세요.
반드시 아래 JSON 형식으로만 응답하세요.

{{
  "grading": {{
    "total_score": <총점, 정수>,
    "steps": [
      {{
        "step": <단계 번호>,
        "earned": <획득 점수, 정수>,
        "max": <최대 점수, 정수>,
        "reason": "<판단 근거, 1~2문장>"
      }}
    ],
    "overall_comment": "<총평, 1~2문장>"
  }},
  "feedback": {{
    "student_mistakes": [
      {{
        "step": <틀린 단계 번호, 없으면 0>,
        "description": "<학생이 어디서 어떻게 틀렸는지 구체적 설명>"
      }}
    ],
    "correct_approach": [
      {{
        "step": <단계 번호>,
        "title": "<단계 제목>",
        "content": "<이 학생이 이해해야 할 내용>"
      }}
    ],
    "key_concept": "<이 문제에서 학생이 놓친 핵심 개념, 1~2문장>"
  }}
}}

student_mistakes가 없으면 빈 배열 []로 응답하세요."""


@dataclass
class CombinedOutput:
    # 채점
    total_score: int
    steps: list[dict[str, Any]]
    overall_comment: str
    sbert_similarity: float
    # 피드백
    student_mistakes: list[dict]
    correct_approach: list[dict]
    key_concept: str
    # 메타
    model: str
    provider: str
    raw_response: str


class CombinedGradingFeedbackService:
    """채점 + 피드백을 단일 LLM 호출로 처리."""

    def __init__(self, sbert_model: SentenceTransformer, llm_client: LLMClient | None = None) -> None:
        # llm_client를 외부에서 주입받으면 그것을 사용 (MLX는 lifespan에서 모델 로드 후 주입)
        # 주입이 없으면 기존처럼 자체 생성 (anthropic/ollama provider용)
        self._llm = llm_client if llm_client is not None else LLMClient()
        self._sbert = sbert_model

    async def run(
        self,
        problem_content: str,
        answer: str,
        reference_solution: str,
        rubric: dict,
        student_answer: str,
    ) -> CombinedOutput:
        """채점 + 피드백 단일 호출. 타임아웃은 LLM_TIMEOUT_SECONDS."""
        user_prompt = COMBINED_USER_TEMPLATE.format(
            problem_content=problem_content,
            answer=answer,
            reference_solution=reference_solution,
            rubric_json=json.dumps(rubric, ensure_ascii=False, indent=2),
            student_answer=student_answer,
        )

        timeout = settings.llm_timeout_seconds
        try:
            # grading_context: 채점 진행 중임을 LLMClient에 알림
            # → HallucinationBatchService가 이 구간에 GPU를 선점하지 않음
            async with self._llm.grading_context():
                response = await asyncio.wait_for(
                    self._llm.chat(
                        system_prompt=COMBINED_SYSTEM_PROMPT,
                        user_prompt=user_prompt,
                        model=settings.grading_model,
                        max_tokens=2048,
                        temperature=0.7,
                    ),
                    timeout=timeout,
                )
        except asyncio.TimeoutError:
            raise CombinedError(f"LLM 타임아웃 ({timeout:.0f}초)")
        except Exception as e:
            raise CombinedError(f"LLM API 오류: {e}") from e

        parsed = self._parse_response(response.text)
        sbert_sim = self._compute_sbert_similarity(student_answer, reference_solution)

        grading = parsed["grading"]
        feedback = parsed["feedback"]

        return CombinedOutput(
            total_score=grading["total_score"],
            steps=grading["steps"],
            overall_comment=grading.get("overall_comment", ""),
            sbert_similarity=sbert_sim,
            student_mistakes=feedback.get("student_mistakes", []),
            correct_approach=feedback.get("correct_approach", []),
            key_concept=feedback.get("key_concept", ""),
            model=response.model,
            provider=response.provider,
            raw_response=response.text,
        )

    def _parse_response(self, raw: str) -> dict:
        text = raw.strip()
        # 코드 블록 제거
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])

        # JSON 추출 (앞뒤 텍스트 제거)
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            text = match.group(0)

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            text = re.sub(r'\\(?!["\\/bfnrtu])', r'\\\\', text)
            try:
                data = json.loads(text)
            except json.JSONDecodeError as e:
                raise CombinedError(f"JSON 파싱 실패: {e}\n원문: {raw[:300]}") from e

        if "grading" not in data:
            raise CombinedError("응답에 'grading' 필드 없음")
        if "feedback" not in data:
            raise CombinedError("응답에 'feedback' 필드 없음")

        grading = data["grading"]
        if not isinstance(grading.get("total_score"), int):
            try:
                grading["total_score"] = int(grading["total_score"])
            except (TypeError, ValueError):
                raise CombinedError("total_score가 정수가 아닙니다")

        if not isinstance(grading.get("steps"), list):
            raise CombinedError("steps가 리스트가 아닙니다")

        return data

    def _compute_sbert_similarity(self, student_answer: str, reference_solution: str) -> float:
        try:
            import numpy as np
            embs = self._sbert.encode(
                [student_answer, reference_solution],
                convert_to_numpy=True,
                normalize_embeddings=True,
            )
            return float(max(0.0, min(1.0, np.dot(embs[0], embs[1]))))
        except Exception:
            return 0.0

    def format_steps_for_trust(self, steps: list[dict]) -> list[dict]:
        """trust_gate 호환 형식으로 steps 변환."""
        result = []
        for s in steps:
            result.append({
                "step": s.get("step", 0),
                "earned_score": s.get("earned", 0),
                "max_score": s.get("max", 1),
                "reason": s.get("reason", ""),
            })
        return result


class CombinedError(Exception):
    pass
