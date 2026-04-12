import json
import logging
import os
import sys
from pathlib import Path

os.environ["PYTHONUNBUFFERED"] = "1"  # conda run 파이프 버퍼링 방지

import torch
from PIL import Image
from torchvision.transforms import InterpolationMode
import torchvision.transforms as T
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
OUTPUT_DIR = BASE / "ocr_training/output/got_ocr_finetuned_v2"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# chat()과 동일한 대화 형식 프롬프트
# prompt(287 tokens) + ground_truth(최대 353 tokens) = 640 max
MAX_LENGTH = 640
PROMPT = (
    "<|im_start|>system\n"
    "        You should follow the instructions carefully and explain your answers in detail."
    "<|im_end|>"
    "<|im_start|>user\n"
    "<img>" + "<imgpad>" * 256 + "</img>\n"
    "OCR: "
    "<|im_end|>"
    "<|im_start|>assistant\n"
)
SEP = "<|im_end|>"

def load_jsonl(path: Path) -> list[dict]:
    with open(path) as f:
        return [json.loads(line) for line in f]

class OcrDataset(torch.utils.data.Dataset):
    def __init__(self, records: list[dict]):
        self.records = records
        # chat()의 GOTImageEvalProcessor와 동일한 전처리 (BICUBIC, 1024×1024)
        self.transform = T.Compose([
            T.Resize((1024, 1024), interpolation=InterpolationMode.BICUBIC),
            T.ToTensor(),
            T.Normalize(mean=[0.48145466, 0.4578275, 0.40821073],
                        std=[0.26862954, 0.26130258, 0.27577711]),
        ])

    def __len__(self):
        return len(self.records)

    def __getitem__(self, idx):
        rec = self.records[idx]
        try:
            image = Image.open(rec["image"]).convert("RGB")
            image_tensor = self.transform(image)  # (C, H, W)
        except Exception as e:
            raise RuntimeError(f"이미지 로드 실패 - {rec['image']}: {e}")

        return {
            "image_tensor": image_tensor,
            "ground_truth": rec["conversations"][1]["value"],
        }

class OcrDataCollator:
    def __init__(self, tokenizer, max_length: int = MAX_LENGTH):
        self.tokenizer = tokenizer
        self.max_length = max_length
        # 프롬프트 토큰 ID를 미리 인코딩해 두기
        self.prompt_ids = tokenizer.encode(PROMPT, add_special_tokens=False)
        self.sep_ids    = tokenizer.encode(SEP,    add_special_tokens=False)
        self.pad_id     = tokenizer.pad_token_id

    def __call__(self, features: list[dict]) -> dict:
        all_input_ids = []
        all_labels    = []

        for f in features:
            gt_ids  = self.tokenizer.encode(f["ground_truth"], add_special_tokens=False)
            sep_ids = self.sep_ids

            # full sequence: [prompt] + [ground_truth] + [<|im_end|>]
            full_ids = self.prompt_ids + gt_ids + sep_ids
            full_ids = full_ids[:self.max_length]

            # labels: prompt 부분은 -100으로 마스킹, gt + sep만 학습
            prompt_len = min(len(self.prompt_ids), len(full_ids))
            labels = [-100] * prompt_len + full_ids[prompt_len:]
            labels = labels[:self.max_length]

            all_input_ids.append(full_ids)
            all_labels.append(labels)

        # 배치 내 최대 길이에 맞춰 왼쪽 정렬 패딩
        max_len = max(len(x) for x in all_input_ids)
        input_ids_tensor  = torch.full((len(features), max_len), self.pad_id, dtype=torch.long)
        labels_tensor     = torch.full((len(features), max_len), -100,        dtype=torch.long)
        attention_mask    = torch.zeros((len(features), max_len),              dtype=torch.long)

        for i, (ids, lbs) in enumerate(zip(all_input_ids, all_labels)):
            input_ids_tensor[i, :len(ids)] = torch.tensor(ids)
            labels_tensor[i, :len(lbs)]    = torch.tensor(lbs)
            attention_mask[i, :len(ids)]   = 1

        # images: list[Tensor(1,C,H,W)], 모델과 동일한 bfloat16
        images = [f["image_tensor"].unsqueeze(0).to(torch.bfloat16) for f in features]

        return {
            "input_ids":      input_ids_tensor,
            "attention_mask": attention_mask,
            "labels":         labels_tensor,
            "images":         images,
        }

class OcrTrainer(Trainer):
    """images가 list[Tensor]이므로 Trainer의 자동 GPU 이동을 override"""
    def _prepare_inputs(self, inputs: dict) -> dict:
        images = inputs.pop("images", None)
        inputs = super()._prepare_inputs(inputs)
        if images is not None:
            inputs["images"] = [img.to("cuda") for img in images]
        return inputs

def main():
    import transformers

    log_path = OUTPUT_DIR / "train.log"
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))

    # root 로거 설정
    logging.basicConfig(level=logging.INFO, handlers=[file_handler, stream_handler], force=True)

    # transformers 자체 로거에도 동일한 핸들러 추가 (Trainer step 로그 캡처)
    transformers.utils.logging.set_verbosity_info()
    hf_logger = transformers.utils.logging.get_logger("transformers.trainer")
    hf_logger.addHandler(file_handler)
    hf_logger.addHandler(stream_handler)

    logger = logging.getLogger(__name__)
    logger.info("=== GOT-OCR 2.0 LoRA 파인튜닝 시작 (bf16) ===")
    logger.info(f"CUDA: {torch.cuda.is_available()} | device: {torch.cuda.get_device_name(0)}")
    logger.info(f"로그 파일: {log_path}")

    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL, trust_remote_code=True)
    tokenizer.pad_token_id = 151643  # Qwen tokenizer는 bos/eos가 None → pad token 고정

    config = AutoConfig.from_pretrained(BASE_MODEL, trust_remote_code=True)
    model_class = get_class_from_dynamic_module(
        config.auto_map["AutoModel"], BASE_MODEL
    )

    # device_map="auto" 제거: Trainer가 디바이스 배치를 직접 관리하도록 함
    model = model_class.from_pretrained(
        BASE_MODEL,
        config=config,
        trust_remote_code=True,
        attn_implementation="sdpa",
        torch_dtype=torch.bfloat16,
    )
    model = model.to("cuda")

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
    model.enable_input_require_grads()  # LoRA + gradient checkpointing 호환성 패치
    model.print_trainable_parameters()

    print("데이터셋 로딩 중...")
    train_dataset = OcrDataset(load_jsonl(TRAIN_DATA))
    eval_dataset  = OcrDataset(load_jsonl(EVAL_DATA))
    print(f"train: {len(train_dataset):,}개, eval: {len(eval_dataset):,}개")

    collator = OcrDataCollator(tokenizer)

    training_args = TrainingArguments(
        output_dir=str(OUTPUT_DIR),
        num_train_epochs=3,
        per_device_train_batch_size=2,         # MAX_LENGTH 640 → attention 2.8x → OOM 방지
        per_device_eval_batch_size=2,
        gradient_accumulation_steps=16,        # effective batch 32 유지 (2×16)
        gradient_checkpointing=True,           # VRAM 절감 (필요 시 속도 trade-off)
        dataloader_num_workers=4,              # RAM 47/48GB OOM 위험으로 복귀
        dataloader_persistent_workers=True,
        dataloader_pin_memory=True,
        dataloader_prefetch_factor=2,          # 4→2 축소 (총 버퍼 ~1.5GB로 감소)
        learning_rate=2e-4,                    # effective batch 32 (batch=8 × accum=4)
        bf16=True,
        warmup_ratio=0.03,
        lr_scheduler_type="cosine",
        logging_steps=10,
        save_strategy="steps",
        save_steps=2000,                       # ~1시간마다 저장 (크래시 복구용)
        eval_strategy="steps",
        eval_steps=7000,                       # 에폭당 ~2회 (eval 27k 샘플 오버헤드 절감)
        save_total_limit=3,                    # 최근 3개 체크포인트 유지
        report_to="none",
        remove_unused_columns=False,           # 커스텀 입력 키('images') 삭제 방지
    )

    trainer = OcrTrainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        data_collator=collator,
    )

    # 체크포인트가 있으면 이어서 학습, 없으면 처음부터
    last_checkpoint = None
    if OUTPUT_DIR.exists() and any(OUTPUT_DIR.glob("checkpoint-*")):
        checkpoints = sorted(OUTPUT_DIR.glob("checkpoint-*"), key=lambda p: int(p.name.split("-")[-1]))
        last_checkpoint = str(checkpoints[-1])
        print(f"체크포인트 발견, 이어서 학습: {last_checkpoint}")

    trainer.train(resume_from_checkpoint=last_checkpoint)
    trainer.save_model(str(OUTPUT_DIR))
    tokenizer.save_pretrained(str(OUTPUT_DIR))
    print(f"\n학습 완료. 저장: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
