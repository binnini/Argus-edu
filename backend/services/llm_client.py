"""Thin wrapper around configured LLM provider implementations."""

import asyncio
import logging
from contextlib import asynccontextmanager

from config import settings
from services.mlx_model_path import resolve_mlx_model_path
from services.providers import AnthropicProvider, MLXProvider, OllamaProvider
from services.providers.base import LLMProvider, LLMResponse

logger = logging.getLogger(__name__)


class LLMClient:
    """
    Anthropic / Ollama / MLX 통합 클라이언트.

    provider는 settings.llm_provider로 결정한다. MLX provider 사용 시
    main.py lifespan에서 로드한 model/tokenizer를 주입해야 한다.
    """

    def __init__(
        self,
        provider: LLMProvider | None = None,
        mlx_model=None,
        mlx_tokenizer=None,
        mlx_model_path: str | None = None,
    ) -> None:
        self.provider = settings.llm_provider
        self._grading_inflight = 0
        self._chat_lock = asyncio.Lock()
        self._provider = provider or self._build_provider(
            mlx_model,
            mlx_tokenizer,
            mlx_model_path,
        )
        logger.info(f"LLM 클라이언트 초기화: provider={self.provider}")

    def _build_provider(
        self,
        mlx_model=None,
        mlx_tokenizer=None,
        mlx_model_path: str | None = None,
    ) -> LLMProvider:
        if self.provider == "anthropic":
            return AnthropicProvider()
        if self.provider == "ollama":
            return OllamaProvider()
        if self.provider == "mlx":
            if mlx_model is None or mlx_tokenizer is None:
                raise ValueError(
                    "LLM_PROVIDER=mlx 일 때 mlx_model과 mlx_tokenizer를 주입해야 합니다. "
                    "main.py lifespan에서 mlx_lm.load() 후 LLMClient(mlx_model=...) 형태로 생성하세요."
                )
            active_model_path = resolve_mlx_model_path(
                mlx_model_path or settings.mlx_feedback_model_path or settings.mlx_model_path
            )
            logger.info(f"MLX 클라이언트 준비 완료: model_path={active_model_path}")
            return MLXProvider(mlx_model, mlx_tokenizer, active_model_path)
        raise ValueError(f"지원하지 않는 LLM_PROVIDER: {self.provider}")

    @property
    def grading_inflight(self) -> int:
        """현재 진행 중인 채점 호출 수."""
        return self._grading_inflight

    @asynccontextmanager
    async def grading_context(self):
        """Mark a grading call section so background verification can yield."""
        self._grading_inflight += 1
        try:
            yield
        finally:
            self._grading_inflight -= 1

    async def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str,
        max_tokens: int = 1024,
        temperature: float = 1.0,
    ) -> LLMResponse:
        """Run a chat completion through the configured provider."""
        async with self._chat_lock:
            return await self._provider.chat(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
            )


__all__ = ["LLMClient", "LLMResponse"]
