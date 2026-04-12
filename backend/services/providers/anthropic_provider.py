"""Anthropic Claude LLM provider."""

from config import settings
from services.providers.base import LLMResponse


class AnthropicProvider:
    """Anthropic Messages API provider."""

    provider = "anthropic"

    def __init__(self) -> None:
        self._anthropic = None

    async def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str,
        max_tokens: int = 1024,
        temperature: float = 1.0,
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
            provider=self.provider,
        )
