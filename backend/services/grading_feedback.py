"""
grading_feedback.py — 채점 + 개인화 피드백 통합 서비스 (단일 LLM 호출).

기존 grading.py + feedback.py의 흐름을 단순화해 채점 1회 + 피드백 1회로 처리.
- GRADING_MODEL로 채점 결과 생성
- FEEDBACK_MODEL로 개인화 피드백 생성
- HHEM/SBERT 할루시네이션 검증 제거 (배치 검증으로 대체 예정)
- inconsistency_rate 제거 (단일 샘플링)
"""

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from typing import Any

from config import settings
from services.feedback import FEEDBACK_SYSTEM_PROMPT, FEEDBACK_USER_TEMPLATE
from services.grading import GRADING_SYSTEM_PROMPT, GRADING_USER_TEMPLATE, check_final_answer
from services.llm_client import LLMClient

logger = logging.getLogger(__name__)


def parse_combined_response(raw: str) -> dict[str, Any]:
    """Parse and validate combined grading/feedback JSON from LLM output."""
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        text = match.group(0)

    try:
        data: dict[str, Any] = json.loads(text)
    except json.JSONDecodeError:
        text = re.sub(r'\\(?!["\\/bfnrtu])', r"\\\\", text)
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


def parse_grading_response(raw: str) -> dict[str, Any]:
    """Parse and validate grading JSON from LLM output."""
    text = _extract_json_object(raw)
    try:
        data: dict[str, Any] = json.loads(text)
    except json.JSONDecodeError:
        text = re.sub(r'\\(?!["\\/bfnrtu])', r"\\\\", text)
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            raise CombinedError(f"채점 JSON 파싱 실패: {e}\n원문: {raw[:300]}") from e

    required = {"total_score", "steps", "overall_comment"}
    missing = required - set(data.keys())
    if missing:
        raise CombinedError(f"채점 필드 누락: {missing}")

    if not isinstance(data.get("total_score"), int):
        try:
            data["total_score"] = int(data["total_score"])
        except (TypeError, ValueError):
            raise CombinedError("total_score가 정수가 아닙니다")

    if not isinstance(data.get("steps"), list):
        raise CombinedError("steps가 리스트가 아닙니다")

    return data


def parse_feedback_response(raw: str) -> dict[str, Any]:
    """Parse and validate feedback JSON from LLM output."""
    text = _extract_json_object(raw)
    try:
        data: dict[str, Any] = json.loads(text)
    except json.JSONDecodeError:
        text = re.sub(r'\\(?!["\\/bfnrtu])', r"\\\\", text)
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            raise CombinedError(f"피드백 JSON 파싱 실패: {e}\n원문: {raw[:300]}") from e

    required = {"student_mistakes", "correct_approach", "key_concept"}
    missing = required - set(data.keys())
    if missing:
        raise CombinedError(f"피드백 필드 누락: {missing}")

    if not isinstance(data.get("student_mistakes"), list):
        raise CombinedError("student_mistakes는 리스트여야 합니다")
    if not isinstance(data.get("correct_approach"), list):
        raise CombinedError("correct_approach는 리스트여야 합니다")

    return data


def _extract_json_object(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])

    match = re.search(r"\{.*\}", text, re.DOTALL)
    return match.group(0) if match else text


def _format_grading_summary(steps: list[dict[str, Any]]) -> str:
    lines = []
    for step in steps:
        earned = step.get("earned", step.get("earned_score", 0))
        max_score = step.get("max", step.get("max_score", 1))
        reason = step.get("reason", "")
        step_num = step.get("step", "?")
        status = "정답" if earned == max_score else f"오답 ({earned}/{max_score}점)"
        lines.append(f"- {step_num}단계: {status} — {reason}")
    return "\n".join(lines) if lines else "채점 결과 없음"


@dataclass
class CombinedOutput:
    # 채점
    total_score: int
    steps: list[dict[str, Any]]
    overall_comment: str
    # 피드백
    student_mistakes: list[dict]
    correct_approach: list[dict]
    key_concept: str
    # 메타
    model: str
    provider: str
    raw_response: str


class CombinedGradingFeedbackService:
    """채점 + 피드백을 분리된 모델 호출로 처리."""

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self._llm = llm_client if llm_client is not None else LLMClient()

    async def run(
        self,
        problem_content: str,
        answer: str,
        reference_solution: str,
        rubric: dict,
        student_answer: str,
    ) -> CombinedOutput:
        """채점 + 피드백을 각각 설정된 모델로 호출한다."""
        answer_verdict = check_final_answer(student_answer, answer)
        logger.info("최종 답 판별: %s", answer_verdict)

        grading_prompt = GRADING_USER_TEMPLATE.format(
            problem_content=problem_content,
            answer=answer,
            reference_solution=reference_solution,
            rubric_json=json.dumps(rubric, ensure_ascii=False, indent=2),
            student_answer=student_answer,
            answer_verdict=answer_verdict,
        )

        timeout = settings.llm_timeout_seconds
        try:
            # grading_context: 채점/피드백 진행 중임을 LLMClient에 알림
            # → HallucinationBatchService가 이 구간에 GPU를 선점하지 않음
            async with self._llm.grading_context():
                grading_response = await asyncio.wait_for(
                    self._llm.chat(
                        system_prompt=GRADING_SYSTEM_PROMPT,
                        user_prompt=grading_prompt,
                        model=settings.grading_model,
                        max_tokens=1024,
                        temperature=0.0,
                    ),
                    timeout=timeout,
                )

                grading = parse_grading_response(grading_response.text)

                # 오답으로 확정 판별된 경우 total_score를 0으로 강제
                if "오답" in answer_verdict:
                    if grading["total_score"] != 0:
                        logger.warning(
                            "오답 판별 → total_score %d → 0 강제 (answer_verdict=%s)",
                            grading["total_score"], answer_verdict,
                        )
                    grading["total_score"] = 0

                feedback_prompt = FEEDBACK_USER_TEMPLATE.format(
                    problem_content=problem_content,
                    answer=answer,
                    reference_solution=reference_solution,
                    student_answer=student_answer,
                    grading_summary=_format_grading_summary(grading["steps"]),
                )
                feedback_response = await asyncio.wait_for(
                    self._llm.chat(
                        system_prompt=FEEDBACK_SYSTEM_PROMPT,
                        user_prompt=feedback_prompt,
                        model=settings.feedback_model,
                        max_tokens=2048,
                        temperature=0.7,
                    ),
                    timeout=timeout,
                )
        except asyncio.TimeoutError:
            raise CombinedError(f"LLM 타임아웃 ({timeout:.0f}초)")
        except Exception as e:
            raise CombinedError(f"LLM API 오류: {e}") from e

        feedback = parse_feedback_response(feedback_response.text)

        return CombinedOutput(
            total_score=grading["total_score"],
            steps=grading["steps"],
            overall_comment=grading.get("overall_comment", ""),
            student_mistakes=feedback.get("student_mistakes", []),
            correct_approach=feedback.get("correct_approach", []),
            key_concept=feedback.get("key_concept", ""),
            model=f"{grading_response.model} / {feedback_response.model}",
            provider=grading_response.provider,
            raw_response=json.dumps(
                {
                    "grading": grading_response.text,
                    "feedback": feedback_response.text,
                },
                ensure_ascii=False,
            ),
        )

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
