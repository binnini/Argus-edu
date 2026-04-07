"""
Step 5: LoRA 어댑터를 base model에 병합 → 단일 파라미터 파일 저장
"""
from pathlib import Path

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

BASE = Path.home() / "projects/Argus-edu"
BASE_MODEL  = "stepfun-ai/GOT-OCR2_0"
LORA_PATH   = BASE / "ocr_training/output/got_ocr_finetuned"
OUTPUT_PATH = BASE / "ocr_training/output/got_ocr_merged"
OUTPUT_PATH.mkdir(parents=True, exist_ok=True)


def main():
    print("토크나이저 로딩...")
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL, trust_remote_code=True)

    print("Base 모델 로딩 (float16)...")
    base_model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL,
        trust_remote_code=True,
        torch_dtype=torch.float16,
        device_map="auto",
    )

    print("LoRA 어댑터 로딩...")
    model = PeftModel.from_pretrained(base_model, str(LORA_PATH))

    print("Merge & unload...")
    merged = model.merge_and_unload()

    print(f"저장 중: {OUTPUT_PATH}")
    merged.save_pretrained(str(OUTPUT_PATH))
    tokenizer.save_pretrained(str(OUTPUT_PATH))

    print(f"\n완료: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
