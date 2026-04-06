"""
llm_client.py — LLM 클라이언트 추상화 레이어.

LLM_PROVIDER 환경변수로 제공자를 전환:
  - "anthropic" (기본): Claude API
  - "ollama": 로컬 Ollama (OpenAI 호환 API)

이 레이어를 통해 grading.py / explanation.py는
제공자를 알 필요 없이 동일한 인터페이스로 LLM을 호출한다.
"""

import asyncio
import logging
from dataclasses import dataclass

from config import settings

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    text: str
    model: str
    provider: str


class LLMClient:
    """
    Anthropic / Ollama 통합 클라이언트.
    provider는 settings.llm_provider로 결정.
    """

    def __init__(self) -> None:
        self.provider = settings.llm_provider
        logger.info(f"LLM 클라이언트 초기화: provider={self.provider}")

        if self.provider == "anthropic":
            # anthropic 클라이언트는 실제 호출 시점에 초기화 (httpx 버전 충돌 방지)
            self._anthropic = None
        elif self.provider == "ollama":
            import httpx
            from openai import AsyncOpenAI
            # httpx 클라이언트 timeout을 설정값 기반으로 지정
            # Gemma4 thinking 모델은 응답에 2분+ 소요될 수 있음
            _timeout = settings.llm_timeout_seconds
            self._openai = AsyncOpenAI(
                base_url=f"{settings.ollama_base_url}/v1",
                api_key="ollama",
                http_client=httpx.AsyncClient(timeout=_timeout),
            )
        else:
            raise ValueError(f"지원하지 않는 LLM_PROVIDER: {self.provider}")

    async def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str,
        max_tokens: int = 1024,
        temperature: float = 1.0,
    ) -> LLMResponse:
        """
        통합 채팅 호출. provider에 따라 내부 구현이 다름.

        Args:
            system_prompt: 시스템 프롬프트
            user_prompt: 유저 메시지
            model: 모델명 (환경변수에서 주입)
            max_tokens: 최대 토큰 수
            temperature: 샘플링 온도

        Returns:
            LLMResponse
        """
        if self.provider == "anthropic":
            return await self._chat_anthropic(
                system_prompt, user_prompt, model, max_tokens, temperature
            )
        elif self.provider == "ollama":
            return await self._chat_ollama(
                system_prompt, user_prompt, model, max_tokens, temperature
            )

    async def _chat_anthropic(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str,
        max_tokens: int,
        temperature: float,
    ) -> LLMResponse:
        if self._anthropic is None:
            import anthropic
            self._anthropic = anthropic.AsyncAnthropic(
                api_key=settings.anthropic_api_key
            )
        message = await self._anthropic.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=[
                {
                    "type": "text",
                    "text": system_prompt,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": user_prompt}],
        )
        return LLMResponse(
            text=message.content[0].text,
            model=model,
            provider="anthropic",
        )

    async def _chat_ollama(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str,
        max_tokens: int,
        temperature: float,
    ) -> LLMResponse:
        # Gemma4 등 thinking 모델은 reasoning 토큰을 먼저 소비함.
        # max_tokens를 4배 확보해 content 잘림 방지.
        effective_max_tokens = max_tokens * 4

        response = await self._openai.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=effective_max_tokens,
            temperature=temperature,
        )
        content = response.choices[0].message.content or ""
        return LLMResponse(
            text=content,
            model=model,
            provider="ollama",
        )
