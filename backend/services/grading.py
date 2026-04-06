"""
grading.py — LLM 기반 채점 서비스.

- llm_client.py를 통해 Anthropic / Ollama 모두 지원
- 채점 프롬프트: docs/prompts.md 기준
- 타임아웃: 30초
- 실패 시: GradingError 발생 (라우터에서 재시도 큐 적재)
"""

import json
import asyncio
import logging
from dataclasses import dataclass
from typing import Any

from sentence_transformers import SentenceTransformer

from config import settings
from services.llm_client import LLMClient

logger = logging.getLogger(__name__)

GRADING_SYSTEM_PROMPT = (
    "당신은 한국 고등학교 수학 채점 전문가입니다.\n"
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

위 루브릭에 따라 학생 답변을 채점하세요. 반드시 아래 JSON 형식으로만 응답하세요.

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


class GradingService:
    def __init__(self, sbert_model: SentenceTransformer) -> None:
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
        """채점 실행. 타임아웃 30초. 실패 시 GradingError 발생."""
        user_prompt = GRADING_USER_TEMPLATE.format(
            problem_content=problem_content,
            answer=answer,
            reference_solution=reference_solution,
            rubric_json=json.dumps(rubric, ensure_ascii=False, indent=2),
            student_answer=student_answer,
        )

        # Ollama 로컬 모델은 thinking 포함으로 응답이 느릴 수 있음
        timeout = settings.llm_timeout_seconds

        try:
            response = await asyncio.wait_for(
                self._llm.chat(
                    system_prompt=GRADING_SYSTEM_PROMPT,
                    user_prompt=user_prompt,
                    model=settings.grading_model,
                    max_tokens=1024,
                    temperature=1.0,
                ),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            raise GradingError(f"LLM API 타임아웃 ({timeout}초)")
        except Exception as e:
            raise GradingError(f"LLM API 오류: {e}") from e

        parsed = self._parse_response(response.text)
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
        from sklearn.metrics.pairwise import cosine_similarity
        import numpy as np

        embeddings = self._sbert.encode(
            [student_answer, reference_solution],
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        sim = float(cosine_similarity([embeddings[0]], [embeddings[1]])[0][0])
        return max(0.0, min(1.0, sim))


class GradingError(Exception):
    """채점 실패 예외 — 라우터에서 재시도 큐에 적재."""
    pass
