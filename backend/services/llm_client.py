"""
llm_client.py — LLM 클라이언트 추상화 레이어.

LLM_PROVIDER 환경변수로 제공자를 전환:
  - "anthropic" (기본): Claude API
  - "ollama": 로컬 Ollama (OpenAI 호환 API)
  - "mlx": 로컬 MLX (mlx_lm 직접 사용, Apple Silicon 전용)
             mlx provider는 main.py lifespan에서 모델을 로드한 뒤
             LLMClient(mlx_model=..., mlx_tokenizer=...) 형태로 주입받는다.

이 레이어를 통해 grading_feedback.py 등 서비스 계층은
제공자를 알 필요 없이 동일한 인터페이스로 LLM을 호출한다.
"""

import asyncio
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from config import settings

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    text: str
    model: str
    provider: str


def _strip_gemma4_thinking(text: str) -> str:
    """Gemma4 thinking channel 출력 제거.

    enable_thinking=False 를 적용해도 간헐적으로
    <|channel>thought ... <|channel>response 블록이 나올 수 있어 방어적으로 처리.
    """
    if "<|channel>response" in text:
        return text.split("<|channel>response", 1)[-1].strip()
    # thought 블록만 있고 response 마커가 없는 경우
    cleaned = re.sub(r"<\|channel>thought.*?(?=<\|channel>|\Z)", "", text, flags=re.DOTALL)
    return cleaned.strip()


class LLMClient:
    """
    Anthropic / Ollama / MLX 통합 클라이언트.
    provider는 settings.llm_provider로 결정.

    MLX provider 사용 시:
        main.py lifespan에서 mlx_lm.load()로 로드한 model/tokenizer를 주입해야 한다.
        ThreadPoolExecutor(max_workers=1) 로 GPU 직렬화 — 동시 요청은 큐잉됨.
    """

    def __init__(self, mlx_model=None, mlx_tokenizer=None) -> None:
        self.provider = settings.llm_provider
        logger.info(f"LLM 클라이언트 초기화: provider={self.provider}")

        if self.provider == "anthropic":
            # anthropic 클라이언트는 실제 호출 시점에 초기화 (httpx 버전 충돌 방지)
            self._anthropic = None

        elif self.provider == "ollama":
            import httpx
            from openai import AsyncOpenAI
            _timeout = settings.llm_timeout_seconds
            self._openai = AsyncOpenAI(
                base_url=f"{settings.ollama_base_url}/v1",
                api_key="ollama",
                http_client=httpx.AsyncClient(timeout=_timeout),
            )

        elif self.provider == "mlx":
            if mlx_model is None or mlx_tokenizer is None:
                raise ValueError(
                    "LLM_PROVIDER=mlx 일 때 mlx_model과 mlx_tokenizer를 주입해야 합니다. "
                    "main.py lifespan에서 mlx_lm.load() 후 LLMClient(mlx_model=...) 형태로 생성하세요."
                )
            self._mlx_model = mlx_model
            self._mlx_tokenizer = mlx_tokenizer
            # max_workers=1: Metal GPU는 단일 스레드로 직렬화해야 안전
            self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="mlx_gpu")
            # 채점 우선 카운터: 양수이면 배치 할루시네이션 검증은 해당 회차를 건너뜀
            self._grading_inflight: int = 0
            logger.info(f"MLX 클라이언트 준비 완료: model_path={settings.mlx_model_path}")

        else:
            raise ValueError(f"지원하지 않는 LLM_PROVIDER: {self.provider}")

    @property
    def grading_inflight(self) -> int:
        """현재 진행 중인 채점 호출 수. 배치 할루시네이션 검증이 양보 여부를 판단하는 데 사용."""
        return getattr(self, "_grading_inflight", 0)

    from contextlib import asynccontextmanager as _acm

    @_acm
    async def grading_context(self):
        """채점 호출 구간을 표시하는 비동기 컨텍스트 매니저.

        CombinedGradingFeedbackService.run() 이 이 컨텍스트 안에서 chat()을 호출하면,
        HallucinationBatchService.run_batch() 는 grading_inflight > 0 을 감지하고
        해당 회차를 건너뛴다.

        Usage:
            async with llm_client.grading_context():
                response = await llm_client.chat(...)
        """
        if hasattr(self, "_grading_inflight"):
            self._grading_inflight += 1
        try:
            yield
        finally:
            if hasattr(self, "_grading_inflight"):
                self._grading_inflight -= 1

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
        elif self.provider == "mlx":
            return await self._chat_mlx(
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

    async def _chat_mlx(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str,
        max_tokens: int,
        temperature: float,
    ) -> LLMResponse:
        """MLX 직접 추론.

        1. apply_chat_template(enable_thinking=False) 으로 Gemma4 thinking 채널 비활성화.
        2. ThreadPoolExecutor(max_workers=1) 로 이벤트 루프 블로킹 없이 GPU 호출.
        3. _strip_gemma4_thinking() 으로 혹시 남은 thinking 출력 제거.
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        # apply_chat_template: enable_thinking=False 우선, TypeError 시 fallback
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

        text = _strip_gemma4_thinking(raw)
        return LLMResponse(text=text, model=model, provider="mlx")
