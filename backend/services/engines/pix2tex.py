"""pix2tex OCR engine."""

import asyncio
import io
import logging

from PIL import Image

from services.ocr import OCRError

logger = logging.getLogger(__name__)


class Pix2TexEngine:
    """pix2tex 로컬 실행 엔진."""

    def __init__(self) -> None:
        try:
            from pix2tex.cli import LatexOCR

            self._model = LatexOCR()
            logger.info("pix2tex 모델 로드 완료")
        except ImportError as e:
            raise OCRError(
                "pix2tex가 설치되어 있지 않습니다. "
                "`pip install pix2tex` 후 다시 시도하세요."
            ) from e

    async def recognize(self, image_bytes: bytes, content_type: str) -> str:
        try:
            image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        except Exception as e:
            raise OCRError(f"이미지 로드 실패: {e}") from e

        loop = asyncio.get_event_loop()
        try:
            result = await loop.run_in_executor(None, self._model, image)
        except Exception as e:
            raise OCRError(f"pix2tex 인식 실패: {e}") from e

        return result
