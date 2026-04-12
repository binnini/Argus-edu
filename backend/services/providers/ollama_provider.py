"""Ollama OpenAI-compatible LLM provider."""

import httpx
from openai import AsyncOpenAI

from config import settings
from services.providers.base import LLMResponse

OLLAMA_TOKEN_MULTIPLIER = 4


class OllamaProvider:
    """Local Ollama provider through the OpenAI-compatible API."""

    provider = "ollama"

    def __init__(self) -> None:
        self._openai = AsyncOpenAI(
            base_url=f"{settings.ollama_base_url}/v1",
            api_key="ollama",
            http_client=httpx.AsyncClient(timeout=settings.llm_timeout_seconds),
        )

    async def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str,
        max_tokens: int = 1024,
        temperature: float = 1.0,
    ) -> LLMResponse:
        response = await self._openai.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=max_tokens * OLLAMA_TOKEN_MULTIPLIER,
            temperature=temperature,
        )
        content = response.choices[0].message.content or ""
        return LLMResponse(text=content, model=model, provider=self.provider)
