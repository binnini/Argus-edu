#!/usr/bin/env python3
"""
ocr_worker.py — GOT-OCR 2.0 지속 서브프로세스 워커.

argus-gotocr conda 환경(transformers==4.44.2)에서 실행되며,
stdin/stdout JSON 라인으로 OCRService와 통신한다.

프로토콜:
  요청  (stdin,  1줄 JSON): {"id": "...", "image_b64": "...", "content_type": "image/jpeg"}
  응답  (stdout, 1줄 JSON): {"id": "...", "text": "..."} | {"id": "...", "error": "..."}

실행:
  /path/to/argus-gotocr/bin/python backend/scripts/ocr_worker.py --model-path /path/to/got_ocr_merged
"""

import argparse
import base64
import json
import logging
import os
import sys
import tempfile
import traceback
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [ocr_worker] %(levelname)s %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)


def load_model(model_path: str):
    import torch
    from transformers import AutoConfig, AutoTokenizer
    from transformers.dynamic_module_utils import get_class_from_dynamic_module

    if torch.cuda.is_available():
        device = "cuda"
        dtype = torch.bfloat16
    elif torch.backends.mps.is_available():
        device = "mps"
        dtype = torch.float32  # MPS는 bfloat16 미지원
    else:
        device = "cpu"
        dtype = torch.float32

    logger.info(f"GOT-OCR 모델 로딩: {model_path} (device={device})")
    tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
    config = AutoConfig.from_pretrained(model_path, trust_remote_code=True)
    model_class = get_class_from_dynamic_module(
        config.auto_map["AutoModel"], model_path
    )
    model = model_class.from_pretrained(
        model_path,
        config=config,
        trust_remote_code=True,
        torch_dtype=dtype,
    )
    model = model.to(device)
    model.eval()
    logger.info(f"GOT-OCR 모델 로딩 완료 (device={device})")
    return model, tokenizer


def run_inference(model, tokenizer, image_bytes: bytes, content_type: str) -> str:
    suffix = ".png" if "png" in content_type else ".jpg"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
        f.write(image_bytes)
        tmp_path = f.name
    try:
        result = model.chat(tokenizer, tmp_path, ocr_type="ocr")
        return result
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--model-path",
        default=os.getenv("GOT_OCR_MODEL_PATH", ""),
        help="GOT-OCR merged model directory",
    )
    args = parser.parse_args()

    if not args.model_path or not Path(args.model_path).exists():
        logger.error(f"모델 경로 없음 또는 존재하지 않음: {args.model_path!r}")
        sys.exit(1)

    model, tokenizer = load_model(args.model_path)

    # 준비 완료 신호 — OCRService가 이 라인을 기다림
    print(json.dumps({"ready": True}), flush=True)
    logger.info("워커 준비 완료. 요청 대기 중...")

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            req = json.loads(line)
        except json.JSONDecodeError as e:
            print(json.dumps({"error": f"JSON 파싱 오류: {e}"}), flush=True)
            continue

        req_id = req.get("id", "")
        try:
            image_bytes = base64.b64decode(req["image_b64"])
            content_type = req.get("content_type", "image/jpeg")
            text = run_inference(model, tokenizer, image_bytes, content_type)
            if not text or not text.strip():
                raise ValueError("OCR 결과가 비어 있습니다")
            print(json.dumps({"id": req_id, "text": text.strip()}, ensure_ascii=False), flush=True)
        except Exception:
            err = traceback.format_exc().splitlines()[-1]
            logger.error(f"추론 실패 id={req_id}: {err}")
            print(json.dumps({"id": req_id, "error": err}), flush=True)


if __name__ == "__main__":
    main()
