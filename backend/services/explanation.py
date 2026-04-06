"""
explanation.py — 풀이 설명 생성 서비스 (멀티 샘플링 3회).

- 멀티 샘플링: temperature=0.7, 동일 프롬프트 3회 호출
- 불일치율 계산: SBERT 코사인 유사도 행렬 기반
- JSON 구조화 출력 파싱
- 풀이 설명은 반드시 교사 승인 후에만 노출 (이 레이어에서 제어하지 않음)
"""

import asyncio
import json
import logging
from dataclasses import dataclass

import anthropic
import numpy as np
from sentence_transformers import SentenceTransformer

from config import settings

logger = logging.getLogger(__name__)

EXPLANATION_SYSTEM_PROMPT = (
    "당신은 한국 고등학교 수학 교사입니다.\n"
    "학생이 이해할 수 있도록 풀이를 단계별로 명확하게 설명하세요.\n"
    "각 단계는 반드시 분리하고, 수학적으로 정확한 내용만 작성하세요.\n"
    "추측이나 불확실한 내용은 절대 포함하지 마세요."
)

EXPLANATION_USER_TEMPLATE = """\
[문제]
{problem_content}

[정답]
{answer}

[참조 풀이]
{reference_solution}

위 문제의 풀이를 학생에게 설명하세요. 반드시 아래 JSON 형식으로만 응답하세요.

{{
  "steps": [
    {{
      "step": <단계 번호>,
      "title": "<단계 제목>",
      "content": "<단계 설명>"
    }}
  ],
  "summary": "<핵심 개념 요약, 1~2문장>"
}}"""


@dataclass
class ExplanationOutput:
    """최종 선택된 풀이 설명 + 불일치율."""
    steps: list[dict]
    summary: str
    inconsistency_rate: float
    raw_samples: list[dict]  # 3개 샘플 원본 (디버깅/로깅용)


class ExplanationService:
    def __init__(self, sbert_model: SentenceTransformer) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        self._sbert = sbert_model

    async def generate(
        self,
        problem_content: str,
        answer: str,
        reference_solution: str,
    ) -> ExplanationOutput:
        """멀티 샘플링 3회 후 불일치율 계산. 실패 시 ExplanationError 발생."""
        user_prompt = EXPLANATION_USER_TEMPLATE.format(
            problem_content=problem_content,
            answer=answer,
            reference_solution=reference_solution,
        )

        # 3회 병렬 호출
        try:
            raw_texts = await asyncio.wait_for(
                asyncio.gather(
                    self._call_claude(user_prompt),
                    self._call_claude(user_prompt),
                    self._call_claude(user_prompt),
                ),
                timeout=90.0,  # 3회 × 30초
            )
        except asyncio.TimeoutError:
            raise ExplanationError("Claude API 타임아웃 (풀이 설명 3회 샘플링)")
        except anthropic.APIError as e:
            raise ExplanationError(f"Claude API 오류: {e}") from e

        samples = [self._parse_response(text) for text in raw_texts]
        inconsistency_rate = self._calculate_inconsistency_rate(samples)

        # 첫 번째 샘플을 대표 풀이로 사용
        best = samples[0]

        return ExplanationOutput(
            steps=best["steps"],
            summary=best["summary"],
            inconsistency_rate=inconsistency_rate,
            raw_samples=samples,
        )

    async def _call_claude(self, user_prompt: str) -> str:
        """프롬프트 캐싱 적용, temperature=0.7."""
        message = await self._client.messages.create(
            model=settings.explanation_model,
            max_tokens=2048,
            temperature=0.7,
            system=[
                {
                    "type": "text",
                    "text": EXPLANATION_SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[
                {
                    "role": "user",
                    "content": user_prompt,
                }
            ],
        )
        return message.content[0].text

    def _parse_response(self, raw: str) -> dict:
        """JSON 응답 파싱 + 유효성 검증."""
        text = raw.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1]) if lines[-1].startswith("```") else "\n".join(lines[1:])

        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            raise ExplanationError(f"풀이 설명 JSON 파싱 실패: {e}\n원문: {raw[:200]}") from e

        if "steps" not in data or "summary" not in data:
            raise ExplanationError("풀이 설명 필드 누락: steps, summary 필요")

        if not isinstance(data["steps"], list) or not data["steps"]:
            raise ExplanationError("steps는 비어 있지 않은 리스트여야 합니다")

        return data

    def _calculate_inconsistency_rate(self, samples: list[dict]) -> float:
        """
        3개 풀이 설명의 불일치율 계산.

        알고리즘:
        1. 각 샘플의 step content를 SBERT로 임베딩
        2. 동일 단계 번호끼리 코사인 유사도 계산
        3. 유사도 < 0.85인 단계 쌍을 불일치로 판정
        4. 불일치 단계 수 / 전체 비교 단계 수 = 불일치율
        """
        if len(samples) < 2:
            return 0.0

        # 단계별로 모든 샘플의 content를 그룹화
        step_contents: dict[int, list[str]] = {}
        for sample in samples:
            for step in sample.get("steps", []):
                step_num = step.get("step", 0)
                content = step.get("content", "")
                step_contents.setdefault(step_num, []).append(content)

        if not step_contents:
            return 0.0

        total_comparisons = 0
        inconsistent_count = 0
        threshold = 0.85

        for step_num, contents in step_contents.items():
            if len(contents) < 2:
                continue

            embeddings = self._sbert.encode(
                contents,
                convert_to_numpy=True,
                normalize_embeddings=True,
            )

            # 쌍별 유사도 계산
            for i in range(len(embeddings)):
                for j in range(i + 1, len(embeddings)):
                    sim = float(np.dot(embeddings[i], embeddings[j]))
                    total_comparisons += 1
                    if sim < threshold:
                        inconsistent_count += 1

        if total_comparisons == 0:
            return 0.0

        return inconsistent_count / total_comparisons

    def format_explanation_text(self, steps: list[dict], summary: str) -> str:
        """풀이 설명을 마크다운 텍스트로 변환 (DB 저장 및 API 응답용)."""
        lines = []
        for step in steps:
            lines.append(f"**{step['step']}단계: {step.get('title', '')}**")
            lines.append(step.get("content", ""))
            lines.append("")
        lines.append(f"**핵심 요약**: {summary}")
        return "\n".join(lines)


class ExplanationError(Exception):
    """풀이 설명 생성 실패 예외."""
    pass
