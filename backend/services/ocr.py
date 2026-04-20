"""OCR service factory and common OCR error type."""

import inspect
import logging
from typing import Protocol

from config import settings

logger = logging.getLogger(__name__)


class OCRError(Exception):
    """Raised when OCR cannot produce a trustworthy result."""


class OCREngine(Protocol):
    async def recognize(self, image_bytes: bytes, content_type: str) -> str:
        """Recognize text from image bytes."""


class OCRService:
    """OCR_MODEL 환경변수에 따라 엔진을 선택하는 OCR 서비스."""

    def __init__(self) -> None:
        self._model_name = settings.ocr_model
        self._engine: OCREngine | None = None
        logger.info(f"OCR 엔진: {self._model_name}")

    def _load_engine(self) -> None:
        """지연 로드 — 첫 호출 시 엔진 초기화."""
        if self._engine is not None:
            return

        if self._model_name == "pix2tex":
            from services.engines.pix2tex import Pix2TexEngine

            self._engine = Pix2TexEngine()
        elif self._model_name == "mathpix":
            from services.engines.mathpix import MathpixEngine

            self._engine = MathpixEngine()
        elif self._model_name == "got_ocr":
            from services.engines.got_ocr import GotOcrEngine

            self._engine = GotOcrEngine()
        else:
            raise OCRError(
                f"지원하지 않는 OCR 엔진: {self._model_name}. "
                "pix2tex | mathpix | got_ocr 중 선택하세요."
            )

    async def recognize(self, image_bytes: bytes, content_type: str) -> str:
        """이미지 바이트를 LaTeX/텍스트로 변환한다."""
        self._load_engine()
        if self._engine is None:
            raise OCRError("OCR 엔진이 초기화되지 않았습니다.")

        try:
            result = await self._engine.recognize(image_bytes, content_type)
        except OCRError:
            raise
        except Exception as e:
            raise OCRError(f"OCR 처리 중 오류: {e}") from e

        if not result or not result.strip():
            raise OCRError("OCR 결과가 비어 있습니다. 이미지를 다시 확인해주세요.")

        return result.strip()

    async def close(self) -> None:
        """엔진이 종료 훅을 제공하면 호출한다."""
        if self._engine is None:
            return
        close_fn = getattr(self._engine, "close", None)
        if close_fn is None:
            return
        maybe_awaitable = close_fn()
        if inspect.isawaitable(maybe_awaitable):
            await maybe_awaitable
