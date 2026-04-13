"""MLX LLM provider for Apple Silicon local inference."""

import asyncio
import re
from concurrent.futures import ThreadPoolExecutor

from config import settings
from services.mlx_model_path import resolve_mlx_model_path
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

    def __init__(self, mlx_model, mlx_tokenizer, model_path: str) -> None:
        self._mlx_model = mlx_model
        self._mlx_tokenizer = mlx_tokenizer
        self._active_model_path = model_path
        self._executor = ThreadPoolExecutor(max_workers=MLX_WORKERS, thread_name_prefix="mlx_gpu")

    def _resolve_model_path(self, model: str) -> str:
        """Map logical model names to MLX model paths."""
        if model == settings.grading_model:
            return settings.mlx_grading_model_path or settings.mlx_feedback_model_path or settings.mlx_model_path
        if model == settings.feedback_model:
            return settings.mlx_feedback_model_path or settings.mlx_model_path
        if model == settings.hallucination_model:
            return (
                settings.mlx_hallucination_model_path
                or settings.mlx_feedback_model_path
                or settings.mlx_model_path
            )
        return model or settings.mlx_model_path

    async def _ensure_model_loaded(self, model: str) -> str:
        target_path = resolve_mlx_model_path(self._resolve_model_path(model))
        if target_path == self._active_model_path:
            return target_path

        def _load_model():
            from mlx_lm import load

            return load(target_path)

        loop = asyncio.get_event_loop()
        self._mlx_model, self._mlx_tokenizer = await loop.run_in_executor(
            self._executor,
            _load_model,
        )
        self._active_model_path = target_path
        return target_path

    async def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str,
        max_tokens: int = 1024,
        temperature: float = 1.0,
    ) -> LLMResponse:
        model_path = await self._ensure_model_loaded(model)
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
        return LLMResponse(text=text, model=model_path, provider=self.provider)
