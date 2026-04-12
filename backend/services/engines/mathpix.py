"""Mathpix OCR API engine."""

import base64

import httpx

from config import settings
from services.ocr import OCRError

MATHPIX_TIMEOUT_SECONDS = 30.0
MATHPIX_TEXT_URL = "https://api.mathpix.com/v3/text"


class MathpixEngine:
    """Mathpix API 엔진."""

    def __init__(self) -> None:
        self._app_id = settings.mathpix_app_id
        self._app_key = settings.mathpix_app_key
        if not self._app_id or not self._app_key:
            raise OCRError(
                "Mathpix API 인증 정보 없음. "
                ".env에 MATHPIX_APP_ID, MATHPIX_APP_KEY를 설정하세요."
            )

    async def recognize(self, image_bytes: bytes, content_type: str) -> str:
        image_b64 = base64.b64encode(image_bytes).decode()
        payload = {
            "src": f"data:{content_type};base64,{image_b64}",
            "formats": ["text"],
            "data_options": {"include_latex": True},
        }

        try:
            async with httpx.AsyncClient(timeout=MATHPIX_TIMEOUT_SECONDS) as client:
                resp = await client.post(
                    MATHPIX_TEXT_URL,
                    json=payload,
                    headers={
                        "app_id": self._app_id,
                        "app_key": self._app_key,
                    },
                )
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPStatusError as e:
            raise OCRError(f"Mathpix API 오류 ({e.response.status_code}): {e.response.text}") from e
        except Exception as e:
            raise OCRError(f"Mathpix 요청 실패: {e}") from e

        error = data.get("error")
        if error:
            raise OCRError(f"Mathpix 인식 실패: {error}")

        return data.get("text", "")
