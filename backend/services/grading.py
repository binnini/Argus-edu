"""
grading.py — LLM 기반 채점 서비스.

정오 판별 흐름:
  1. _check_final_answer(): student_answer의 [최종 답] 줄에서 숫자를 추출해
     problem.answer의 숫자와 비교 → 코드 레벨에서 정답/오답/미기입 판별
  2. 판별 결과를 채점 프롬프트에 포함 → AI는 부분점수·풀이 평가에만 집중
  3. 오답으로 판별된 경우 AI가 만점을 줘도 total_score를 0으로 강제하지 않음
     (AI가 중간 과정 점수를 줄 수 있으므로 AI 판단 유지, 단 오답 사실을 명시)
"""

import json
import re
import asyncio
import logging
from dataclasses import dataclass
from typing import Any

from config import settings
from services.embeddings import EmbeddingModel
from services.llm_client import LLMClient

logger = logging.getLogger(__name__)

GRADING_SYSTEM_PROMPT = (
    "당신은 한국 초·중·고 수학 채점 전문가입니다.\n"
    "학생의 답변을 루브릭 기준에 따라 단계별로 채점하고, "
    "반드시 아래 JSON 형식으로만 응답하세요.\n"
    "수학적 사실에 근거하지 않는 내용은 절대 포함하지 마세요."
)

GRADING_USER_TEMPLATE = """\
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

[최종 답 정오 판별 — 시스템 자동 검증 결과]
{answer_verdict}

위 루브릭에 따라 학생 답변을 채점하세요.

채점 원칙:
1. 위 "최종 답 정오 판별" 결과는 학생의 [최종 답]과 정답의 숫자를 비교한 확정적 사실입니다.
   오답으로 판별된 경우, 최종 답을 구하는 마지막 단계는 반드시 0점으로 채점하세요.
2. 중간 풀이 과정의 각 단계는 해당 단계의 계산이 수학적으로 올바른지 직접 검증하여 채점하세요.
3. steps의 earned 합계가 반드시 total_score와 같아야 합니다.

반드시 아래 JSON 형식으로만 응답하세요.

{{
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
}}"""


@dataclass
class GradingOutput:
    total_score: int
    steps: list[dict[str, Any]]
    overall_comment: str
    sbert_similarity: float
    model: str
    provider: str
    raw_response: str


def _extract_numbers(text: str) -> set[str]:
    """LaTeX·쉼표 등을 제거한 뒤 정수·소수 숫자 집합을 반환."""
    cleaned = re.sub(r'\$', '', text)          # $...$ 제거
    cleaned = re.sub(r'\\[a-zA-Z]+', '', cleaned)  # \frac 등 LaTeX 명령 제거
    cleaned = re.sub(r'[{}]', '', cleaned)
    return set(re.findall(r'\d+(?:\.\d+)?', cleaned))


def check_final_answer(student_answer: str, problem_answer: str) -> str:
    """
    student_answer 의 '[최종 답]' 줄과 problem.answer 의 숫자를 비교한다.

    반환값 (채점 프롬프트에 삽입):
      - "정답 (학생의 최종 답이 정답의 숫자와 일치합니다)"
      - "오답 (학생: {student_nums} / 정답: {answer_nums})"
      - "최종 답 미기입 — 풀이 과정만으로 채점"
    """
    match = re.search(r'\[최종 답\]\s*(.+?)(?:\n|$)', student_answer)
    if not match:
        return "최종 답 미기입 — 풀이 과정만으로 채점"

    final = match.group(1).strip()
    if not final:
        return "최종 답 미기입 — 풀이 과정만으로 채점"

    student_nums = _extract_numbers(final)
    answer_nums = _extract_numbers(problem_answer)

    if not student_nums:
        return "최종 답 확인 불가 — 풀이 과정만으로 채점"

    if not answer_nums:
        # 정답 필드에 숫자가 없는 경우(서술형 등) → AI에 위임
        return "정답 숫자 추출 불가 — 풀이 내용으로 판단"

    # 학생이 제출한 모든 숫자가 정답 숫자 집합에 포함되어 있으면 정답으로 간주
    if student_nums.issubset(answer_nums):
        return f"정답 (학생의 최종 답 {student_nums}이(가) 정답 숫자 {answer_nums}에 포함됩니다)"
    else:
        wrong = student_nums - answer_nums
        return (
            f"오답 (학생 최종 답의 {wrong}이(가) 정답에 없습니다. "
            f"학생: {student_nums} / 정답: {answer_nums})"
        )


class GradingService:
    def __init__(self, sbert_model: EmbeddingModel) -> None:
        self._llm = LLMClient()
        self._sbert = sbert_model

    async def grade(
        self,
        problem_content: str,
        answer: str,
        reference_solution: str,
        rubric: dict,
        student_answer: str,
    ) -> GradingOutput:
        """채점 실행. 실패 시 GradingError 발생."""
        answer_verdict = check_final_answer(student_answer, answer)
        logger.info("최종 답 판별: %s", answer_verdict)

        user_prompt = GRADING_USER_TEMPLATE.format(
            problem_content=problem_content,
            answer=answer,
            reference_solution=reference_solution,
            rubric_json=json.dumps(rubric, ensure_ascii=False, indent=2),
            student_answer=student_answer,
            answer_verdict=answer_verdict,
        )

        timeout = settings.llm_timeout_seconds

        try:
            response = await asyncio.wait_for(
                self._llm.chat(
                    system_prompt=GRADING_SYSTEM_PROMPT,
                    user_prompt=user_prompt,
                    model=settings.grading_model,
                    max_tokens=1024,
                    temperature=0.0,
                ),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            raise GradingError(f"LLM API 타임아웃 ({timeout}초)")
        except Exception as e:
            raise GradingError(f"LLM API 오류: {e}") from e

        parsed = self._parse_response(response.text)

        # 오답으로 확정 판별된 경우 AI가 만점을 줬어도 total_score를 rubric 만점 이하로 제한
        # (단, 중간 과정 점수는 AI가 판단한 값을 그대로 사용)
        if "오답" in answer_verdict:
            max_score = rubric.get("total_score", parsed["total_score"])
            if parsed["total_score"] == max_score:
                # AI가 만점을 부여했으나 최종 답이 오답 → 최소 1점 감점 보정
                parsed["total_score"] = max(0, max_score - 1)
                logger.warning(
                    "오답 판별 + AI 만점 → %d/%d 로 보정", parsed["total_score"], max_score
                )

        sbert_sim = self._compute_sbert_similarity(student_answer, reference_solution)

        return GradingOutput(
            total_score=parsed["total_score"],
            steps=parsed["steps"],
            overall_comment=parsed["overall_comment"],
            sbert_similarity=sbert_sim,
            model=response.model,
            provider=response.provider,
            raw_response=response.text,
        )

    def _parse_response(self, raw: str) -> dict:
        """JSON 응답 파싱 + 유효성 검증."""
        text = raw.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1]) if lines[-1].startswith("```") else "\n".join(lines[1:])

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            text = re.sub(r'\\(?!["\\/bfnrtu])', r'\\\\', text)
            try:
                data = json.loads(text)
            except json.JSONDecodeError as e:
                raise GradingError(f"채점 결과 JSON 파싱 실패: {e}\n원문: {raw[:200]}") from e

        required = {"total_score", "steps", "overall_comment"}
        if not required.issubset(data.keys()):
            raise GradingError(f"채점 결과 필드 누락: {required - data.keys()}")

        if not isinstance(data["total_score"], int):
            raise GradingError("total_score는 정수여야 합니다")

        if not isinstance(data["steps"], list) or not data["steps"]:
            raise GradingError("steps는 비어 있지 않은 리스트여야 합니다")

        return data

    def _compute_sbert_similarity(self, student_answer: str, reference_solution: str) -> float:
        """SBERT 코사인 유사도 계산 (0~1)."""
        import numpy as np

        embeddings = self._sbert.encode(
            [student_answer, reference_solution],
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        sim = float(np.dot(embeddings[0], embeddings[1]))
        return max(0.0, min(1.0, sim))


class GradingError(Exception):
    """채점 실패 예외 — 라우터에서 재시도 큐에 적재."""
    pass
