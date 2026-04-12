"""MLX LLM provider for Apple Silicon local inference."""

import asyncio
import re
from concurrent.futures import ThreadPoolExecutor

from config import settings
from services.providers.base import LLMResponse

MLX_WORKERS = 1


def strip_gemma4_thinking(text: str) -> str:
    """Remove Gemma4 thinking channel output when it leaks into content."""
    if "<|channel>response" in text:
        return text.split("<|channel>response", 1)[-1].strip()
    cleaned = re.sub(r"<\|channel>thought.*?(?=<\|channel>|\Z)", "", text, flags=re.DOTALL)
    return cleaned.strip()


class MLXProvider:
    """Direct mlx_lm provider with serialized Metal GPU execution."""

    provider = "mlx"

    def __init__(self, mlx_model, mlx_tokenizer) -> None:
        self._mlx_model = mlx_model
        self._mlx_tokenizer = mlx_tokenizer
        self._executor = ThreadPoolExecutor(max_workers=MLX_WORKERS, thread_name_prefix="mlx_gpu")

    async def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str,
        max_tokens: int = 1024,
        temperature: float = 1.0,
    ) -> LLMResponse:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        try:
            prompt = self._mlx_tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
                enable_thinking=False,
            )
        except TypeError:
            prompt = self._mlx_tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
            )

        effective_max_tokens = max(max_tokens, settings.mlx_max_tokens)

        def _run_generate() -> str:
            from mlx_lm import generate

            try:
                from mlx_lm.sample_utils import make_sampler

                sampler = make_sampler(temp=temperature)
                return generate(
                    self._mlx_model,
                    self._mlx_tokenizer,
                    prompt=prompt,
                    max_tokens=effective_max_tokens,
                    sampler=sampler,
                    verbose=False,
                )
            except (ImportError, TypeError):
                return generate(
                    self._mlx_model,
                    self._mlx_tokenizer,
                    prompt=prompt,
                    max_tokens=effective_max_tokens,
                    verbose=False,
                )

        loop = asyncio.get_event_loop()
        raw = await loop.run_in_executor(self._executor, _run_generate)
        text = strip_gemma4_thinking(raw)
        return LLMResponse(text=text, model=model, provider=self.provider)
