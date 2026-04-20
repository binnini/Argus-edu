"""Thin wrapper around configured LLM provider implementations."""

import asyncio
import inspect
import logging
from contextlib import asynccontextmanager

from config import settings
from services.providers import AnthropicProvider, MLXProvider, OllamaProvider
from services.providers.base import LLMProvider, LLMResponse

logger = logging.getLogger(__name__)


class LLMClient:
    """
    Anthropic / Ollama / MLX 통합 클라이언트.

    provider는 settings.llm_provider로 결정한다.
    MLX provider는 첫 요청 시 모델을 지연 로딩한다.
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
        self._concurrency_limit = asyncio.Semaphore(1)
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
            return MLXProvider(
                mlx_model=mlx_model,
                mlx_tokenizer=mlx_tokenizer,
                model_path=mlx_model_path,
            )
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
        # async with self._chat_lock:
        #     return await self._provider.chat(
        #         system_prompt=system_prompt,
        #         user_prompt=user_prompt,
        #         model=model,
        #         max_tokens=max_tokens,
        #         temperature=temperature,
        #     )
        # 큐 대기 시간 중 timeout이 발생하면 Semaphore를 획득하기 전에 취소되므로 
        # 스레드 풀에 고아 태스크가 적재되는 것을 원천 차단합니다.
        async with self._concurrency_limit:
            return await self._provider.chat(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
            )

    async def close(self) -> None:
        """Provider가 종료 훅을 제공하면 호출한다."""
        close_fn = getattr(self._provider, "close", None)
        if close_fn is None:
            return
        maybe_awaitable = close_fn()
        if inspect.isawaitable(maybe_awaitable):
            await maybe_awaitable


__all__ = ["LLMClient", "LLMResponse"]
