"""
ocr.py — 수식 손글씨 OCR 서비스.

OCR_MODEL 환경변수로 엔진 선택:
    pix2tex  — 오픈소스 LaTeX OCR (기본값)
    mathpix  — Mathpix API (유료, 한국어+수식 혼합 강함)
    got_ocr  — 파인튜닝된 GOT-OCR 2.0 (사용자가 별도 업로드한 모델 파라미터 사용)

OCR 실패 시 에러 반환 (무시하지 않음 — 잘못된 OCR 결과가 채점에 영향을 주면 안 됨).
"""

import json
import logging
import subprocess
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
    """GOT-OCR 2.0 파인튜닝 모델 엔진 — 서브프로세스 방식.

    transformers 5.x (MLX)와 4.44.2 (GOT-OCR)의 버전 충돌을 해결하기 위해
    argus-gotocr conda 환경의 ocr_worker.py를 지속 서브프로세스로 실행한다.

    통신: stdin/stdout JSON 라인 프로토콜
      요청: {"id": "...", "image_b64": "...", "content_type": "..."}
      응답: {"id": "...", "text": "..."} | {"id": "...", "error": "..."}
    """

    # argus-gotocr 환경 Python 경로
    _WORKER_PYTHON = (
        "/opt/homebrew/Caskroom/miniconda/base/envs/argus-gotocr/bin/python"
    )

    def __init__(self) -> None:
        model_path = settings.got_ocr_model_path
        if not model_path:
            raise OCRError(
                "GOT-OCR 모델 경로 없음. "
                ".env에 GOT_OCR_MODEL_PATH를 설정하세요."
            )
        if not Path(model_path).exists():
            raise OCRError(f"GOT-OCR 모델 경로가 존재하지 않습니다: {model_path}")
        if not Path(self._WORKER_PYTHON).exists():
            raise OCRError(
                f"argus-gotocr conda 환경이 없습니다: {self._WORKER_PYTHON}\n"
                "conda create -n argus-gotocr python=3.11 && "
                "pip install 'transformers==4.44.2' torch torchvision timm einops tiktoken accelerate"
            )

        self._model_path = model_path
        self._proc: "subprocess.Popen | None" = None
        self._lock = None  # asyncio.Lock은 이벤트 루프 생성 후 초기화
        self._worker_script = (
            Path(__file__).parent.parent / "scripts" / "ocr_worker.py"
        )
        logger.info(f"GOT-OCR 서브프로세스 엔진 초기화 (model={model_path})")

    def _ensure_lock(self):
        import asyncio
        if self._lock is None:
            self._lock = asyncio.Lock()

    async def _start_worker(self) -> None:
        """워커 서브프로세스를 시작하고 'ready' 신호를 기다린다."""
        import asyncio
        import subprocess

        logger.info("GOT-OCR 워커 프로세스 시작 중...")
        self._proc = await asyncio.create_subprocess_exec(
            self._WORKER_PYTHON,
            str(self._worker_script),
            "--model-path", self._model_path,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=None,  # stderr는 부모 프로세스로 전달 (서버 로그에 표시)
        )

        # 준비 완료 신호 대기 ({"ready": true})
        try:
            ready_line = await asyncio.wait_for(
                self._proc.stdout.readline(), timeout=120.0
            )
        except asyncio.TimeoutError:
            self._proc.kill()
            raise OCRError("GOT-OCR 워커 시작 타임아웃 (120s)")

        try:
            msg = json.loads(ready_line.decode())
            if not msg.get("ready"):
                raise OCRError(f"GOT-OCR 워커 비정상 시작: {msg}")
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            raise OCRError(f"GOT-OCR 워커 ready 응답 파싱 실패: {e}")

        logger.info("GOT-OCR 워커 준비 완료")

    async def recognize(self, image_bytes: bytes, content_type: str) -> str:
        import asyncio
        import base64
        import uuid
        import json as _json

        self._ensure_lock()
        async with self._lock:
            # 워커가 없거나 종료됐으면 재시작
            if self._proc is None or self._proc.returncode is not None:
                await self._start_worker()

            req_id = uuid.uuid4().hex
            req = _json.dumps({
                "id": req_id,
                "image_b64": base64.b64encode(image_bytes).decode(),
                "content_type": content_type,
            }, ensure_ascii=False) + "\n"

            try:
                self._proc.stdin.write(req.encode())
                await self._proc.stdin.drain()
            except BrokenPipeError as e:
                self._proc = None
                raise OCRError(f"GOT-OCR 워커 파이프 끊김: {e}") from e

            try:
                resp_line = await asyncio.wait_for(
                    self._proc.stdout.readline(), timeout=120.0
                )
            except asyncio.TimeoutError:
                self._proc.kill()
                self._proc = None
                raise OCRError("GOT-OCR 추론 타임아웃 (120s)")

            try:
                resp = _json.loads(resp_line.decode())
            except (_json.JSONDecodeError, UnicodeDecodeError) as e:
                raise OCRError(f"GOT-OCR 응답 파싱 실패: {e}") from e

            if "error" in resp:
                raise OCRError(f"GOT-OCR 추론 실패: {resp['error']}")

            return resp.get("text", "")
