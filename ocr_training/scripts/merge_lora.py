"""
merge_lora.py — LoRA 어댑터를 베이스 모델에 병합하여 저장.

환경에 따라 두 가지 모드로 동작:
  - ZIP 모드 (Mac): checkpoint-8000.zip 압축 해제 후 병합
  - 디렉토리 모드 (WSL): 학습 출력 디렉토리를 직접 참조

사용법:
    # Mac (ZIP 파일 기준)
    cd /Users/yebin/workSpace/Argus
    python ocr_training/scripts/merge_lora.py

    # WSL (학습 체크포인트 디렉토리 직접 지정)
    cd ~/projects/Argus-edu
    LORA_DIR=ocr_training/output/got_ocr_finetuned_v2/checkpoint-8000 \\
        python ocr_training/scripts/merge_lora.py
"""
import os
import shutil
import zipfile
from pathlib import Path

import torch
from peft import PeftModel
from transformers import AutoConfig, AutoTokenizer
from transformers.dynamic_module_utils import get_class_from_dynamic_module

BASE_MODEL  = "stepfun-ai/GOT-OCR2_0"
OUTPUT_PATH = Path(__file__).parents[1] / "output/got_ocr_merged"

# WSL: LORA_DIR 환경변수로 체크포인트 디렉토리 직접 지정
# Mac: 환경변수 없으면 ZIP 파일 자동 탐색
_LORA_DIR_ENV = os.environ.get("LORA_DIR", "")
ZIP_PATH      = Path(__file__).parents[1] / "output/got_ocr_merged/checkpoint-8000.zip"
LORA_TMP      = Path(__file__).parents[1] / "output/_lora_tmp"


def resolve_lora_path() -> Path:
    """LoRA 어댑터 경로 결정: 환경변수 → ZIP 추출 순으로 시도."""
    if _LORA_DIR_ENV:
        lora_path = Path(_LORA_DIR_ENV)
        if not lora_path.exists():
            raise FileNotFoundError(f"LORA_DIR 경로가 존재하지 않습니다: {lora_path}")
        print(f"[1/4] LoRA 경로 (환경변수): {lora_path}")
        return lora_path

    # ZIP 추출 (Mac 기본)
    if not ZIP_PATH.exists():
        raise FileNotFoundError(
            f"ZIP 파일이 없습니다: {ZIP_PATH}\n"
            "WSL에서 실행 시 LORA_DIR 환경변수로 체크포인트 경로를 지정하세요."
        )
    print(f"[1/4] LoRA 어댑터 ZIP 추출: {ZIP_PATH.name}")
    LORA_TMP.mkdir(parents=True, exist_ok=True)
    needed = {"adapter_config.json", "adapter_model.safetensors"}
    with zipfile.ZipFile(ZIP_PATH) as z:
        for member in z.namelist():
            filename = Path(member).name
            if filename in needed:
                data = z.read(member)
                (LORA_TMP / filename).write_bytes(data)
                print(f"  추출: {filename} ({len(data) / 1024 / 1024:.1f} MB)")
    return LORA_TMP


def main():
    print("=== GOT-OCR 2.0 LoRA Merge ===\n")

    # 1. LoRA 경로 결정
    lora_path = resolve_lora_path()

    # 2. 베이스 모델 로드
    use_cuda = torch.cuda.is_available()
    dtype = torch.bfloat16 if use_cuda else torch.float32
    print(f"\n[2/4] 베이스 모델 로드: {BASE_MODEL} (dtype={dtype}, cuda={use_cuda})")
    print("      (최초 실행 시 HuggingFace에서 다운로드)")
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL, trust_remote_code=True)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token_id = tokenizer.eos_token_id

    config = AutoConfig.from_pretrained(BASE_MODEL, trust_remote_code=True)
    model_class = get_class_from_dynamic_module(
        config.auto_map["AutoModel"], BASE_MODEL
    )
    base_model = model_class.from_pretrained(
        BASE_MODEL,
        config=config,
        trust_remote_code=True,
        torch_dtype=dtype,
    )

    # 3. LoRA 적용 후 merge
    print(f"\n[3/4] LoRA 적용 및 merge...")
    model = PeftModel.from_pretrained(base_model, str(lora_path))
    merged = model.merge_and_unload()
    merged.eval()
    print("      Merge 완료")

    # 4. 저장
    print(f"\n[4/4] 저장: {OUTPUT_PATH}")
    OUTPUT_PATH.mkdir(parents=True, exist_ok=True)
    merged.save_pretrained(str(OUTPUT_PATH))
    tokenizer.save_pretrained(str(OUTPUT_PATH))

    # 임시 디렉토리 정리 (ZIP 추출 시만)
    if not _LORA_DIR_ENV:
        shutil.rmtree(LORA_TMP, ignore_errors=True)

    print(f"\n완료. 저장된 파일:")
    for f in sorted(OUTPUT_PATH.iterdir()):
        size = f.stat().st_size / 1024 / 1024
        print(f"  {f.name:<45} {size:>8.1f} MB")


if __name__ == "__main__":
    main()
