"""
feedback.py — 개인화 피드백 생성 서비스 (멀티 샘플링 3회).

explanation.py를 대체한다. 일반 풀이 설명이 아닌, 학생의 실제 오류를
분석하고 교정 방향을 제시하는 개인화 피드백을 생성한다.

출력 스키마:
    {
        "student_mistakes": [{"step": N, "description": "..."}],
        "correct_approach": [{"step": N, "title": "...", "content": "..."}],
        "key_concept": "..."
    }

절대 제약: 이 서비스가 생성한 피드백은 반드시 교사 승인 후에만 학생에게 노출.
"""

import asyncio
import json
import re
import logging
from dataclasses import dataclass

import numpy as np
from sentence_transformers import SentenceTransformer

from config import settings
from services.llm_client import LLMClient

logger = logging.getLogger(__name__)

FEEDBACK_SYSTEM_PROMPT = (
    "당신은 한국 수학 교사입니다.\n"
    "학생의 풀이를 분석하여 학생이 어디서 어떻게 틀렸는지 정확히 파악하고,\n"
    "올바른 풀이 방향을 단계별로 제시하세요.\n"
    "일반적인 풀이 설명이 아니라 이 학생의 오류에 집중해야 합니다.\n"
    "수학적으로 정확한 내용만 작성하고, 추측이나 불확실한 내용은 절대 포함하지 마세요."
)

FEEDBACK_USER_TEMPLATE = """\
[문제]
{problem_content}

[정답]
{answer}

[모범 풀이]
{reference_solution}

[학생 답변]
{student_answer}

[채점 결과]
{grading_summary}

위 학생의 풀이를 분석하여 개인화 피드백을 작성하세요.
반드시 아래 JSON 형식으로만 응답하세요.

{{
  "student_mistakes": [
    {{
      "step": <틀린 단계 번호>,
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
}}"""


@dataclass
class FeedbackOutput:
    student_mistakes: list[dict]    # [{step, description}]
    correct_approach: list[dict]    # [{step, title, content}]
    key_concept: str
    inconsistency_rate: float
    model: str
    provider: str
    raw_samples: list[dict]

    def to_dict(self) -> dict:
        return {
            "student_mistakes": self.student_mistakes,
            "correct_approach": self.correct_approach,
            "key_concept": self.key_concept,
        }


class FeedbackService:
    def __init__(self, sbert_model: SentenceTransformer) -> None:
        self._llm = LLMClient()
        self._sbert = sbert_model

    async def generate(
        self,
        problem_content: str,
        answer: str,
        reference_solution: str,
        student_answer: str,
        grading_steps: list[dict],  # GradingOutput.steps
    ) -> FeedbackOutput:
        """멀티 샘플링 3회 후 불일치율 계산."""
        grading_summary = self._format_grading_summary(grading_steps)

        user_prompt = FEEDBACK_USER_TEMPLATE.format(
            problem_content=problem_content,
            answer=answer,
            reference_solution=reference_solution,
            student_answer=student_answer,
            grading_summary=grading_summary,
        )

        call_kwargs = dict(
            system_prompt=FEEDBACK_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            model=settings.feedback_model,
            max_tokens=2048,
            temperature=0.7,
        )

        per_call_timeout = settings.llm_timeout_seconds
        total_timeout = per_call_timeout * 3

        try:
            if settings.llm_provider == "ollama":
                raw_responses = []
                for _ in range(3):
                    r = await asyncio.wait_for(
                        self._llm.chat(**call_kwargs), timeout=per_call_timeout
                    )
                    raw_responses.append(r)
                responses = tuple(raw_responses)
            else:
                responses = await asyncio.wait_for(
                    asyncio.gather(
                        self._llm.chat(**call_kwargs),
                        self._llm.chat(**call_kwargs),
                        self._llm.chat(**call_kwargs),
                    ),
                    timeout=total_timeout,
                )
        except asyncio.TimeoutError:
            raise FeedbackError(f"LLM API 타임아웃 (피드백 3회, {total_timeout:.0f}초)")
        except Exception as e:
            raise FeedbackError(f"LLM API 오류: {e}") from e

        samples = [self._parse_response(r.text) for r in responses]
        inconsistency_rate = self._calculate_inconsistency_rate(samples)
        best = samples[0]

        return FeedbackOutput(
            student_mistakes=best["student_mistakes"],
            correct_approach=best["correct_approach"],
            key_concept=best["key_concept"],
            inconsistency_rate=inconsistency_rate,
            model=responses[0].model,
            provider=responses[0].provider,
            raw_samples=samples,
        )

    def _format_grading_summary(self, steps: list[dict]) -> str:
        """채점 결과를 LLM 프롬프트용 텍스트로 변환."""
        lines = []
        for step in steps:
            earned = step.get("earned_score", 0)
            max_score = step.get("max_score", 1)
            reason = step.get("reason", "")
            step_num = step.get("step", "?")
            status = "정답" if earned == max_score else f"오답 ({earned}/{max_score}점)"
            lines.append(f"- {step_num}단계: {status} — {reason}")
        return "\n".join(lines) if lines else "채점 결과 없음"

    def _parse_response(self, raw: str) -> dict:
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
                raise FeedbackError(f"피드백 JSON 파싱 실패: {e}\n원문: {raw[:200]}") from e

        required = {"student_mistakes", "correct_approach", "key_concept"}
        missing = required - set(data.keys())
        if missing:
            raise FeedbackError(f"피드백 필드 누락: {missing}")

        if not isinstance(data["student_mistakes"], list):
            raise FeedbackError("student_mistakes는 리스트여야 합니다")
        if not isinstance(data["correct_approach"], list) or not data["correct_approach"]:
            raise FeedbackError("correct_approach는 비어 있지 않은 리스트여야 합니다")

        return data

    def _calculate_inconsistency_rate(self, samples: list[dict]) -> float:
        """3개 피드백의 correct_approach 불일치율 (SBERT 코사인 유사도 기반)."""
        if len(samples) < 2:
            return 0.0

        # step별 content 비교
        step_contents: dict[int, list[str]] = {}
        for sample in samples:
            for step in sample.get("correct_approach", []):
                step_num = step.get("step", 0)
                content = step.get("content", "")
                step_contents.setdefault(step_num, []).append(content)

        if not step_contents:
            return 0.0

        total_comparisons = 0
        inconsistent_count = 0
        threshold = 0.85

        for contents in step_contents.values():
            if len(contents) < 2:
                continue
            embeddings = self._sbert.encode(
                contents, convert_to_numpy=True, normalize_embeddings=True
            )
            for i in range(len(embeddings)):
                for j in range(i + 1, len(embeddings)):
                    sim = float(np.dot(embeddings[i], embeddings[j]))
                    total_comparisons += 1
                    if sim < threshold:
                        inconsistent_count += 1

        return inconsistent_count / total_comparisons if total_comparisons > 0 else 0.0

    def format_correct_approach_text(self, correct_approach: list[dict]) -> str:
        """HHEM 검증용 — correct_approach를 단순 텍스트로 변환."""
        lines = []
        for step in correct_approach:
            lines.append(f"{step.get('step')}단계 {step.get('title', '')}: {step.get('content', '')}")
        return "\n".join(lines)


class FeedbackError(Exception):
    pass
