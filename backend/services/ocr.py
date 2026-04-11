"""
ocr.py — 수식 손글씨 OCR 서비스.

OCR_MODEL 환경변수로 엔진 선택:
    pix2tex  — 오픈소스 LaTeX OCR (기본값)
    mathpix  — Mathpix API (유료, 한국어+수식 혼합 강함)
    got_ocr  — 파인튜닝된 GOT-OCR 2.0 (사용자가 별도 업로드한 모델 파라미터 사용)

OCR 실패 시 에러 반환 (무시하지 않음 — 잘못된 OCR 결과가 채점에 영향을 주면 안 됨).
"""

import logging
from pathlib import Path

from config import settings

logger = logging.getLogger(__name__)


class OCRError(Exception):
    pass


class OCRService:
    """OCR_MODEL 환경변수에 따라 엔진을 선택하는 OCR 서비스."""

    def __init__(self) -> None:
        self._model_name = settings.ocr_model
        self._engine = None
        logger.info(f"OCR 엔진: {self._model_name}")

    def _load_engine(self):
        """지연 로드 — 첫 호출 시 엔진 초기화."""
        if self._engine is not None:
            return

        if self._model_name == "pix2tex":
            self._engine = _Pix2TexEngine()
        elif self._model_name == "mathpix":
            self._engine = _MathpixEngine()
        elif self._model_name == "got_ocr":
            self._engine = _GotOcrEngine()
        else:
            raise OCRError(f"지원하지 않는 OCR 엔진: {self._model_name}. pix2tex | mathpix | got_ocr 중 선택하세요.")

    async def recognize(self, image_bytes: bytes, content_type: str) -> str:
        """이미지 바이트 → LaTeX/텍스트 변환.

        Returns:
            인식된 텍스트 (LaTeX 포함)

        Raises:
            OCRError: OCR 실패 시 (무시하지 않음)
        """
        self._load_engine()
        try:
            result = await self._engine.recognize(image_bytes, content_type)
        except OCRError:
            raise
        except Exception as e:
            raise OCRError(f"OCR 처리 중 오류: {e}") from e

        if not result or not result.strip():
            raise OCRError("OCR 결과가 비어 있습니다. 이미지를 다시 확인해주세요.")

        return result.strip()


# ── 엔진 구현 ─────────────────────────────────────────────────────


class _Pix2TexEngine:
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
        import asyncio
        from PIL import Image
        import io

        try:
            image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        except Exception as e:
            raise OCRError(f"이미지 로드 실패: {e}") from e

        # pix2tex는 동기 실행 — 이벤트 루프 블로킹 방지
        loop = asyncio.get_event_loop()
        try:
            result = await loop.run_in_executor(None, self._model, image)
        except Exception as e:
            raise OCRError(f"pix2tex 인식 실패: {e}") from e

        return result


class _MathpixEngine:
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
        import base64
        import httpx

        image_b64 = base64.b64encode(image_bytes).decode()
        payload = {
            "src": f"data:{content_type};base64,{image_b64}",
            "formats": ["text"],
            "data_options": {"include_latex": True},
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    "https://api.mathpix.com/v3/text",
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


class _GotOcrEngine:
    """GOT-OCR 2.0 파인튜닝 모델 엔진.

    merge_lora.py로 병합된 모델 디렉토리를 사용.
    GOT_OCR_MODEL_PATH 환경변수로 모델 디렉토리 지정.
    model.chat()으로 추론 (학습 포맷이 chat() 형식과 동일).
    """

    def __init__(self) -> None:
        model_path = settings.got_ocr_model_path
        if not model_path:
            raise OCRError(
                "GOT-OCR 모델 경로 없음. "
                ".env에 GOT_OCR_MODEL_PATH를 설정하세요."
            )
        if not Path(model_path).exists():
            raise OCRError(f"GOT-OCR 모델 경로가 존재하지 않습니다: {model_path}")

        try:
            import torch
            from transformers import AutoConfig, AutoTokenizer
            from transformers.dynamic_module_utils import get_class_from_dynamic_module

            if torch.cuda.is_available():
                self._device = "cuda"
                dtype = torch.bfloat16
            elif torch.backends.mps.is_available():
                self._device = "mps"
                dtype = torch.float32  # MPS는 bfloat16 미지원
            else:
                self._device = "cpu"
                dtype = torch.float32

            self._tokenizer = AutoTokenizer.from_pretrained(
                model_path, trust_remote_code=True
            )
            config = AutoConfig.from_pretrained(model_path, trust_remote_code=True)
            model_class = get_class_from_dynamic_module(
                config.auto_map["AutoModel"], model_path
            )
            self._model = model_class.from_pretrained(
                model_path,
                config=config,
                trust_remote_code=True,
                torch_dtype=dtype,
            )
            self._model = self._model.to(self._device)
            self._model.eval()
            logger.info(f"GOT-OCR 모델 로드 완료: {model_path} (device={self._device}, dtype={dtype})")
        except ImportError as e:
            raise OCRError(
                "transformers 또는 torch가 설치되어 있지 않습니다."
            ) from e
        except Exception as e:
            raise OCRError(f"GOT-OCR 모델 로드 실패: {e}") from e

    async def recognize(self, image_bytes: bytes, content_type: str) -> str:
        import asyncio
        import io
        import tempfile

        # model.chat()은 파일 경로를 요구하므로 임시 파일 사용
        suffix = ".png" if "png" in content_type else ".jpg"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
            f.write(image_bytes)
            tmp_path = f.name

        loop = asyncio.get_event_loop()
        try:
            result = await loop.run_in_executor(None, self._run_inference, tmp_path)
        except Exception as e:
            raise OCRError(f"GOT-OCR 추론 실패: {e}") from e
        finally:
            Path(tmp_path).unlink(missing_ok=True)

        return result

    def _run_inference(self, image_path: str) -> str:
        """model.chat()으로 이미지 파일 → 텍스트 추론."""
        return self._model.chat(self._tokenizer, image_path, ocr_type="ocr")
