"""GOT-OCR subprocess engine."""

import asyncio
import base64
import json
import logging
import subprocess
import uuid
from pathlib import Path

from config import settings
from services.ocr import OCRError

logger = logging.getLogger(__name__)

GOT_WORKER_START_TIMEOUT_SECONDS = 120.0
GOT_INFERENCE_TIMEOUT_SECONDS = 120.0


class GotOcrEngine:
    """GOT-OCR 2.0 파인튜닝 모델 엔진 — 서브프로세스 방식."""

    def __init__(self) -> None:
        model_path = settings.got_ocr_model_path
        if not model_path:
            raise OCRError(
                "GOT-OCR 모델 경로 없음. "
                ".env에 GOT_OCR_MODEL_PATH를 설정하세요."
            )
        if not Path(model_path).exists():
            raise OCRError(f"GOT-OCR 모델 경로가 존재하지 않습니다: {model_path}")
        if not Path(settings.got_ocr_worker_python).exists():
            raise OCRError(
                f"argus-gotocr conda 환경이 없습니다: {settings.got_ocr_worker_python}\n"
                "conda create -n argus-gotocr python=3.11 && "
                "pip install 'transformers==4.44.2' torch torchvision timm einops tiktoken accelerate"
            )

        self._model_path = model_path
        self._proc: subprocess.Popen | None = None
        self._lock: asyncio.Lock | None = None
        self._worker_script = (
            Path(__file__).parent.parent.parent / "scripts" / "ocr_worker.py"
        )
        logger.info(f"GOT-OCR 서브프로세스 엔진 초기화 (model={model_path})")

    def _ensure_lock(self) -> None:
        if self._lock is None:
            self._lock = asyncio.Lock()

    async def _start_worker(self) -> None:
        """워커 서브프로세스를 시작하고 'ready' 신호를 기다린다."""
        logger.info("GOT-OCR 워커 프로세스 시작 중...")
        self._proc = await asyncio.create_subprocess_exec(
            settings.got_ocr_worker_python,
            str(self._worker_script),
            "--model-path",
            self._model_path,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=None,
        )

        try:
            ready_line = await asyncio.wait_for(
                self._proc.stdout.readline(), timeout=GOT_WORKER_START_TIMEOUT_SECONDS
            )
        except asyncio.TimeoutError:
            self._proc.kill()
            raise OCRError(f"GOT-OCR 워커 시작 타임아웃 ({GOT_WORKER_START_TIMEOUT_SECONDS:.0f}s)")

        try:
            msg = json.loads(ready_line.decode())
            if not msg.get("ready"):
                raise OCRError(f"GOT-OCR 워커 비정상 시작: {msg}")
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            raise OCRError(f"GOT-OCR 워커 ready 응답 파싱 실패: {e}")

        logger.info("GOT-OCR 워커 준비 완료")

    async def recognize(self, image_bytes: bytes, content_type: str) -> str:
        self._ensure_lock()
        async with self._lock:
            if self._proc is None or self._proc.returncode is not None:
                await self._start_worker()

            req_id = uuid.uuid4().hex
            req = json.dumps({
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
                    self._proc.stdout.readline(), timeout=GOT_INFERENCE_TIMEOUT_SECONDS
                )
            except asyncio.TimeoutError:
                self._proc.kill()
                self._proc = None
                raise OCRError(f"GOT-OCR 추론 타임아웃 ({GOT_INFERENCE_TIMEOUT_SECONDS:.0f}s)")

            try:
                resp = json.loads(resp_line.decode())
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                raise OCRError(f"GOT-OCR 응답 파싱 실패: {e}") from e

            if "error" in resp:
                raise OCRError(f"GOT-OCR 추론 실패: {resp['error']}")

            return resp.get("text", "")
