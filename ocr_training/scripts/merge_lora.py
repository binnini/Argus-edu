"""
merge_lora.py — LoRA 어댑터를 베이스 모델에 병합하여 저장.

checkpoint-8000.zip을 자동으로 압축 해제 후 병합.
GPU 불필요 — Mac CPU에서 실행 가능.

사용법:
    cd /Users/yebin/workSpace/Argus
    python ocr_training/scripts/merge_lora.py
"""
import shutil
import zipfile
from pathlib import Path

import torch
from peft import PeftModel
from transformers import AutoConfig, AutoTokenizer
from transformers.dynamic_module_utils import get_class_from_dynamic_module

BASE_MODEL   = "stepfun-ai/GOT-OCR2_0"
ZIP_PATH     = Path(__file__).parents[1] / "output/got_ocr_merged/checkpoint-8000.zip"
LORA_TMP     = Path(__file__).parents[1] / "output/_lora_tmp"
OUTPUT_PATH  = Path(__file__).parents[1] / "output/got_ocr_merged"


def extract_lora(zip_path: Path, dest: Path) -> Path:
    """adapter_config.json과 adapter_model.safetensors만 추출."""
    dest.mkdir(parents=True, exist_ok=True)
    needed = {"adapter_config.json", "adapter_model.safetensors"}
    with zipfile.ZipFile(zip_path) as z:
        for member in z.namelist():
            filename = Path(member).name
            if filename in needed:
                data = z.read(member)
                (dest / filename).write_bytes(data)
                print(f"  추출: {filename} ({len(data) / 1024 / 1024:.1f} MB)")
    return dest


def main():
    print("=== GOT-OCR 2.0 LoRA Merge ===\n")

    # 1. LoRA 어댑터 추출
    print(f"[1/4] LoRA 어댑터 추출: {ZIP_PATH.name}")
    lora_path = extract_lora(ZIP_PATH, LORA_TMP)

    # 2. 베이스 모델 로드 (CPU, float32 — Mac 호환)
    print(f"\n[2/4] 베이스 모델 로드: {BASE_MODEL}")
    print("      (최초 실행 시 HuggingFace에서 다운로드, ~580MB)")
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
        torch_dtype=torch.float32,  # Mac CPU는 bfloat16 미지원
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

    # 임시 디렉토리 정리
    shutil.rmtree(LORA_TMP, ignore_errors=True)

    print(f"\n완료. 저장된 파일:")
    for f in sorted(OUTPUT_PATH.iterdir()):
        size = f.stat().st_size / 1024 / 1024
        print(f"  {f.name:<45} {size:>8.1f} MB")


if __name__ == "__main__":
    main()
