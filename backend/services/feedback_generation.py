"""Single-call feedback generation based on deterministic grading verdicts."""

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from typing import Any
import json_repair
from config import settings
from services.deterministic_grading import AnswerVerdict
from services.llm_client import LLMClient

logger = logging.getLogger(__name__)


FEEDBACK_REVIEW_SYSTEM_PROMPT = """\
당신은 한국 수학 교사입니다.
학생의 최종 정오 판정과 점수는 이미 시스템이 확정했습니다.
당신은 점수나 정오를 변경하지 않고, 학생 풀이 과정의 타당성을 검토해 피드백만 작성합니다.
명확한 오류가 없으면 student_mistakes를 빈 배열로 반환하세요.
없는 오류를 추측하거나 만들어내지 마세요.
수학적으로 정확한 내용만 작성하고 JSON 형식으로만 응답하세요.
JSON 응답 내의 모든 LaTeX 수식 및 역슬래시는 반드시 이중 역슬래시로 이스케이프 처리하세요.
(예: \frac 대신 \\frac, \alpha 대신 \\alpha 사용)"""


FEEDBACK_REVIEW_USER_TEMPLATE = """\
[문제]
{problem_content}

[정답]
{answer}

[모범 풀이]
{reference_solution}

[학생 답변]
{student_answer}

[시스템 확정 판정]
final_answer_verdict: {answer_verdict}
score: {score}/{max_score}
reason: {verdict_reason}
student_values: {student_values_json}
answer_values: {answer_values_json}

다음 네 가지 케이스 중 하나로 분류하세요.

1. correct_solution
   최종 답이 맞고 풀이 과정도 수학적으로 타당합니다.
   이 경우 has_mistakes=false, student_mistakes=[] 로 반환하세요.

2. correct_answer_wrong_process
   최종 답은 맞지만 풀이 과정에 수학적 오류, 근거 부족, 우연한 결론, 잘못된 공식 적용이 있습니다.
   이 경우 has_mistakes=true 로 반환하고 student_mistakes에 풀이 과정의 오류를 적으세요.

3. wrong_answer
   최종 답이 틀렸습니다.
   이 경우 has_mistakes=true 로 반환하고 최종 답이 왜 틀렸는지 또는 풀이 과정 어디에서 오류가 생겼는지 적으세요.

4. uncertain
   학생 풀이가 너무 짧거나 해석이 불가능해서 풀이 과정의 타당성을 확정할 수 없습니다.
   이 경우 명확한 오류가 있을 때만 has_mistakes=true 로 두세요.

반드시 아래 JSON 형식으로만 응답하세요.

{{
  "solution_status": "correct_solution | correct_answer_wrong_process | wrong_answer | uncertain",
  "has_mistakes": true,
  "student_mistakes": [
    {{
      "step": <틀린 단계 번호 또는 null>,
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
  "key_concept": "<핵심 개념 또는 풀이 확인 포인트, 1~2문장>"
}}"""


@dataclass
class FeedbackReviewOutput:
    solution_status: str
    has_mistakes: bool
    student_mistakes: list[dict[str, Any]]
    correct_approach: list[dict[str, Any]]
    key_concept: str
    model: str
    provider: str
    raw_response: str

    def to_feedback_dict(self) -> dict[str, Any]:
        return {
            "solution_status": self.solution_status,
            "has_mistakes": self.has_mistakes,
            "student_mistakes": self.student_mistakes,
            "correct_approach": self.correct_approach,
            "key_concept": self.key_concept,
        }


class FeedbackReviewService:
    def __init__(self, llm_client: LLMClient) -> None:
        self._llm = llm_client

    async def generate(
        self,
        problem_content: str,
        answer: str,
        reference_solution: str,
        student_answer: str,
        answer_verdict: AnswerVerdict,
        score: int,
        max_score: int,
    ) -> FeedbackReviewOutput:
        user_prompt = FEEDBACK_REVIEW_USER_TEMPLATE.format(
            problem_content=problem_content,
            answer=answer,
            reference_solution=reference_solution,
            student_answer=student_answer,
            answer_verdict=answer_verdict.verdict,
            score=score,
            max_score=max_score,
            verdict_reason=answer_verdict.reason,
            student_values_json=json.dumps(answer_verdict.student_values, ensure_ascii=False),
            answer_values_json=json.dumps(answer_verdict.answer_values, ensure_ascii=False),
        )

        try:
            response = await asyncio.wait_for(
                self._llm.chat(
                    system_prompt=FEEDBACK_REVIEW_SYSTEM_PROMPT,
                    user_prompt=user_prompt,
                    model=settings.feedback_model,
                    max_tokens=2048,
                    temperature=0.3,
                ),
                timeout=settings.llm_timeout_seconds,
            )
        except asyncio.TimeoutError:
            raise FeedbackReviewError(f"LLM 타임아웃 ({settings.llm_timeout_seconds:.0f}초)")
        except Exception as e:
            raise FeedbackReviewError(f"LLM API 오류: {e}") from e

        parsed = self._parse_response(response.text)
        return FeedbackReviewOutput(
            solution_status=parsed["solution_status"],
            has_mistakes=parsed["has_mistakes"],
            student_mistakes=parsed["student_mistakes"],
            correct_approach=parsed["correct_approach"],
            key_concept=parsed["key_concept"],
            model=response.model,
            provider=response.provider,
            raw_response=response.text,
        )

    def _parse_response(self, raw: str) -> dict[str, Any]:
        text = raw.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])

        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            text = match.group(0)

        # try:
        #     data = json.loads(text)
        # except json.JSONDecodeError:
        #     text = re.sub(r'\\(?!["\\/bfnrtu])', r"\\\\", text)
        #     data = json.loads(text)
        try:
            data = json_repair.loads(text)
        except Exception as e:
            raise FeedbackReviewError(f"JSON 파싱 및 복구 실패: {e}")

        required = {"solution_status", "has_mistakes", "student_mistakes", "correct_approach", "key_concept"}
        missing = required - set(data)
        if missing:
            raise FeedbackReviewError(f"피드백 필드 누락: {missing}")

        valid_statuses = {
            "correct_solution",
            "correct_answer_wrong_process",
            "wrong_answer",
            "uncertain",
        }
        if data["solution_status"] not in valid_statuses:
            raise FeedbackReviewError(f"solution_status 값 오류: {data['solution_status']}")
        if not isinstance(data["student_mistakes"], list):
            raise FeedbackReviewError("student_mistakes는 리스트여야 합니다")
        if not isinstance(data["correct_approach"], list):
            raise FeedbackReviewError("correct_approach는 리스트여야 합니다")

        data["has_mistakes"] = bool(data["has_mistakes"])
        if not data["has_mistakes"]:
            data["student_mistakes"] = []
        return data


class FeedbackReviewError(Exception):
    pass
