"""
Step 3: GOT-OCR 2.0 LoRA 파인튜닝 (bf16, 양자화 없음)
- 568M 모델은 16GB VRAM에서 QLoRA 없이도 충분히 학습 가능
- QLoRA(4-bit) 대비 4~10배 빠른 속도, VRAM 7~9GB 사용
- SDPA attention (PyTorch 내장, CUDA 13 호환)
- batch=8, gradient_accumulation=2 (effective batch=16)
"""
import json
from pathlib import Path

import torch
from peft import LoraConfig, get_peft_model
from transformers import (
    AutoConfig,
    AutoTokenizer,
    Trainer,
    TrainingArguments,
)
from transformers.dynamic_module_utils import get_class_from_dynamic_module

BASE = Path.home() / "projects/Argus-edu"
BASE_MODEL = "stepfun-ai/GOT-OCR2_0"
TRAIN_DATA = BASE / "data/ocr_samples/dataset/train.jsonl"
EVAL_DATA  = BASE / "data/ocr_samples/dataset/test.jsonl"
OUTPUT_DIR = BASE / "ocr_training/output/got_ocr_finetuned"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# p99 = 295, 여유 포함해서 512로 설정. 동적 패딩으로 실제 처리 토큰 최소화.
MAX_LENGTH = 512


def load_jsonl(path: Path) -> list[dict]:
    with open(path) as f:
        return [json.loads(line) for line in f]


class OcrDataset(torch.utils.data.Dataset):
    def __init__(self, records: list[dict]):
        self.records = records

    def __len__(self):
        return len(self.records)

    def __getitem__(self, idx):
        rec = self.records[idx]
        return {
            "image_path": rec["image"],
            "ground_truth": rec["conversations"][1]["value"],
            "prompt": rec["conversations"][0]["value"],
        }


class OcrDataCollator:
    """prompt + ground_truth를 하나의 시퀀스로 토크나이즈.
    prompt 부분은 loss 계산에서 제외(-100), answer 부분만 학습.
    GOT-OCR2 커스텀 모델은 token_type_ids 미지원 → 제거.
    """

    def __init__(self, tokenizer, max_length: int = MAX_LENGTH):
        self.tokenizer = tokenizer
        self.max_length = max_length

    def __call__(self, features: list[dict]) -> dict:
        texts = [f["prompt"] + f["ground_truth"] for f in features]

        # 동적 패딩: 배치 내 가장 긴 시퀀스 기준으로만 패딩 (고정 max_length 금지)
        encoding = self.tokenizer(
            texts,
            max_length=self.max_length,
            truncation=True,
            padding=True,           # longest in batch
            return_tensors="pt",
        )

        labels = encoding["input_ids"].clone()
        labels[encoding["attention_mask"] == 0] = -100

        # prompt 부분 loss 제외
        for i, f in enumerate(features):
            prompt_ids = self.tokenizer(
                f["prompt"], add_special_tokens=False
            )["input_ids"]
            labels[i, : len(prompt_ids)] = -100

        encoding["labels"] = labels
        encoding.pop("token_type_ids", None)
        return encoding


def main():
    print("=== GOT-OCR 2.0 LoRA 파인튜닝 시작 (bf16) ===")
    print(f"CUDA: {torch.cuda.is_available()} | device: {torch.cuda.get_device_name(0)}")

    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL, trust_remote_code=True)

    # AutoModelForCausalLM은 custom GOTConfig를 거부 → auto_map 직접 사용
    config = AutoConfig.from_pretrained(BASE_MODEL, trust_remote_code=True)
    model_class = get_class_from_dynamic_module(
        config.auto_map["AutoModel"], BASE_MODEL
    )

    model = model_class.from_pretrained(
        BASE_MODEL,
        config=config,
        trust_remote_code=True,
        attn_implementation="sdpa",
        torch_dtype=torch.bfloat16,
        device_map="auto",
        # quantization_config 제거: bf16 full-precision LoRA
    )

    lora_config = LoraConfig(
        r=16,
        lora_alpha=32,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                        "gate_proj", "up_proj", "down_proj"],
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    print("데이터셋 로딩 중...")
    train_dataset = OcrDataset(load_jsonl(TRAIN_DATA))
    eval_dataset  = OcrDataset(load_jsonl(EVAL_DATA))
    print(f"train: {len(train_dataset):,}개, eval: {len(eval_dataset):,}개")

    collator = OcrDataCollator(tokenizer)

    training_args = TrainingArguments(
        output_dir=str(OUTPUT_DIR),
        num_train_epochs=3,
        per_device_train_batch_size=8,
        per_device_eval_batch_size=8,
        gradient_accumulation_steps=2,      # effective batch = 16
        learning_rate=2e-4,
        bf16=True,
        warmup_ratio=0.03,
        lr_scheduler_type="cosine",
        logging_steps=100,
        save_strategy="epoch",
        eval_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        report_to="none",
        dataloader_num_workers=4,
        dataloader_pin_memory=True,
        remove_unused_columns=False,
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        data_collator=collator,
    )

    trainer.train()
    trainer.save_model(str(OUTPUT_DIR))
    tokenizer.save_pretrained(str(OUTPUT_DIR))
    print(f"\n학습 완료. 저장: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
