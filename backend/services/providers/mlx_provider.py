"""MLX LLM provider for Apple Silicon local inference."""

import asyncio
import contextlib
import gc
import logging
import re
from concurrent.futures import ThreadPoolExecutor

from config import settings
from services.mlx_model_path import resolve_mlx_model_path
from services.providers.base import LLMResponse

MLX_WORKERS = 1
logger = logging.getLogger(__name__)


def strip_gemma4_thinking(text: str) -> str:
    """Remove Gemma4 thinking channel output when it leaks into content."""
    if "<|channel>response" in text:
        return text.split("<|channel>response", 1)[-1].strip()
    cleaned = re.sub(r"<\|channel>thought.*?(?=<\|channel>|\Z)", "", text, flags=re.DOTALL)
    return cleaned.strip()


class MLXProvider:
    """Direct mlx_lm provider with serialized Metal GPU execution."""

    provider = "mlx"

    def __init__(self, mlx_model=None, mlx_tokenizer=None, model_path: str | None = None) -> None:
        self._mlx_model = mlx_model
        self._mlx_tokenizer = mlx_tokenizer
        self._active_model_path = model_path
        self._executor = ThreadPoolExecutor(max_workers=MLX_WORKERS, thread_name_prefix="mlx_gpu")
        self._idle_timeout_seconds = max(0, int(settings.mlx_idle_shutdown_seconds))
        self._last_used_at: float = 0.0
        self._inflight = 0
        self._idle_task: asyncio.Task | None = None
        if self._mlx_model is not None and self._mlx_tokenizer is not None:
            with contextlib.suppress(RuntimeError):
                self._last_used_at = asyncio.get_running_loop().time()

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
        if (
            target_path == self._active_model_path
            and self._mlx_model is not None
            and self._mlx_tokenizer is not None
        ):
            return target_path

        def _load_model():
            from mlx_lm import load

            return load(target_path)

        if self._active_model_path is None:
            logger.info("MLX 모델 지연 로딩 시작: %s", target_path)
        else:
            logger.info("MLX 모델 전환 로딩 시작: %s -> %s", self._active_model_path, target_path)
        loop = asyncio.get_event_loop()
        self._mlx_model, self._mlx_tokenizer = await loop.run_in_executor(
            self._executor,
            _load_model,
        )
        self._active_model_path = target_path
        self._last_used_at = loop.time()
        self._ensure_idle_watchdog()
        logger.info("MLX 모델 로딩 완료: %s", target_path)
        return target_path

    def _ensure_idle_watchdog(self) -> None:
        if self._idle_timeout_seconds <= 0:
            return
        if self._idle_task and not self._idle_task.done():
            return
        self._idle_task = asyncio.create_task(self._idle_watchdog())

    def _unload_model(self) -> None:
        if self._mlx_model is None and self._mlx_tokenizer is None and self._active_model_path is None:
            return
        self._mlx_model = None
        self._mlx_tokenizer = None
        self._active_model_path = None
        gc.collect()
        with contextlib.suppress(Exception):
            import mlx.core as mx

            metal = getattr(mx, "metal", None)
            if metal and hasattr(metal, "clear_cache"):
                metal.clear_cache()
        logger.info("MLX 모델 유휴 언로드 완료")

    async def _idle_watchdog(self) -> None:
        interval = min(30.0, float(self._idle_timeout_seconds))
        try:
            while True:
                await asyncio.sleep(interval)
                if self._mlx_model is None and self._mlx_tokenizer is None:
                    return
                if self._inflight > 0:
                    continue
                now = asyncio.get_running_loop().time()
                if now - self._last_used_at >= self._idle_timeout_seconds:
                    logger.info(
                        "MLX 모델 유휴 언로드: idle=%.1fs timeout=%ss",
                        now - self._last_used_at,
                        self._idle_timeout_seconds,
                    )
                    self._unload_model()
                    return
        except asyncio.CancelledError:
            return

    async def close(self) -> None:
        if self._idle_task and not self._idle_task.done():
            self._idle_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._idle_task
        self._unload_model()
        self._executor.shutdown(wait=False, cancel_futures=True)

    async def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str,
        max_tokens: int = 1024,
        temperature: float = 1.0,
    ) -> LLMResponse:
        self._inflight += 1
        try:
            model_path = await self._ensure_model_loaded(model)
            loop = asyncio.get_running_loop()
            self._last_used_at = loop.time()

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

            # settings.mlx_max_tokens 를 상한(cap)으로 적용한다.
            # 0 이하 값은 비활성화로 보고 요청값(max_tokens)을 그대로 사용한다.
            cap = int(settings.mlx_max_tokens)
            effective_max_tokens = max_tokens if cap <= 0 else min(max_tokens, cap)

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

            raw = await loop.run_in_executor(self._executor, _run_generate)
            text = strip_gemma4_thinking(raw)
            self._last_used_at = loop.time()
            self._ensure_idle_watchdog()
            return LLMResponse(text=text, model=model_path, provider=self.provider)
        finally:
            self._inflight -= 1
