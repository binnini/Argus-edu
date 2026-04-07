# GOT-OCR 2.0 파인튜닝 에이전트 프롬프트

> 이 파일을 새 Claude Code 세션의 초기 프롬프트로 사용한다.  
> 실행 환경: WSL2 (Ubuntu 22.04) + RTX 5070Ti 16GB  
> 작업 디렉토리: `~/workSpace/Argus`

---

## 컨텍스트

"Argus"라는 수학 서답형 자동 채점 시스템을 개발 중이다.  
학생들이 손으로 쓴 수학 풀이 이미지를 OCR로 텍스트화하는 파이프라인이 필요하다.

기존 pix2tex는 한국어+LaTeX 혼합 텍스트에 약하여, GOT-OCR 2.0을 AI-HUB 수학 손글씨 데이터로 파인튜닝해 사용할 것이다.

---

## 네 역할

WSL2 환경에서 GOT-OCR 2.0 파인튜닝 파이프라인을 처음부터 끝까지 구현하고 실행한다.

---

## 현재 상태 (데이터 준비 완료)

모든 데이터는 이미 WSL2 환경에 존재한다.

### 이미지 원본 (TS_3 zip)

```
~/workSpace/Argus/data/AI_HUB/3.개방데이터/1.데이터/Training/01.원천데이터/
├── TS_3.손글씨풀이_초등학교_3학년.zip   (13,486 JPEG)
├── TS_3.손글씨풀이_초등학교_4학년.zip   (13,640 JPEG)
├── TS_3.손글씨풀이_초등학교_5학년.zip   (22,698 JPEG)
├── TS_3.손글씨풀이_초등학교_6학년.zip   (24,044 JPEG)
├── TS_3.손글씨풀이_중학교_1학년.zip     (24,252 JPEG)
├── TS_3.손글씨풀이_중학교_2학년.zip     (20,321 JPEG)
├── TS_3.손글씨풀이_중학교_3학년.zip     (24,138 JPEG)
└── TS_3.손글씨풀이_고등학교_공통수학.zip (17,436 JPEG)
```

### 라벨 데이터

```
~/workSpace/Argus/data/ocr_samples/labels.json   (160,015개)
```

`labels.json` 한 항목:
```json
{
  "image": "images/P3_1_01_21114_49506_8_X.jpeg",
  "ground_truth_text": "$ \\begin{array}{r} 296\\\\ 403\\\\ \\hline 759 \\end{array} $ $1$",
  "expected_result": "correct",
  "source": "AI-HUB_초등학교_3학년"
}
```

> `ground_truth_text`: 이미지에 쓰여진 텍스트(LaTeX+한국어). OCR 학습 정답.  
> `expected_result`: 학생 풀이의 정오 — OCR 학습에 무관. 전량(160k) 사용.  
> `image` 파일명은 TS_3 zip 내부 파일과 매칭된다.

---

## 목표 디렉토리 구조

```
~/workSpace/Argus/
├── data/
│   ├── AI_HUB/.../ TS_3 zip 8개   ← 이미 존재
│   ├── ocr_samples/
│   │   ├── labels.json             ← 이미 존재
│   │   ├── images/                 ← Step 1에서 생성
│   │   └── dataset/
│   │       ├── train.jsonl         ← Step 2에서 생성
│   │       └── test.jsonl          ← Step 2에서 생성
└── ocr_training/                   ← 새로 생성
    ├── scripts/
    │   ├── extract_images.py
    │   ├── prepare_dataset.py
    │   ├── train.py
    │   ├── evaluate_ocr.py
    │   └── merge_lora.py
    ├── output/                     ← 체크포인트 저장
    └── requirements.txt
```

---

## 수행할 작업 (순서대로)

### Step 0: 환경 확인 및 의존성 설치

```bash
# CUDA 및 GPU 확인
nvidia-smi
python3 -c "import torch; print('CUDA:', torch.cuda.is_available(), '| version:', torch.version.cuda)"

mkdir -p ~/workSpace/Argus/ocr_training/{scripts,output}
mkdir -p ~/workSpace/Argus/data/ocr_samples/{images,dataset}
```

`~/workSpace/Argus/ocr_training/requirements.txt`:
```
transformers>=4.40.0
peft>=0.10.0
bitsandbytes>=0.43.0
accelerate>=0.29.0
datasets>=2.18.0
tqdm
pillow
Levenshtein
```

```bash
pip install -r ~/workSpace/Argus/ocr_training/requirements.txt
```

### Step 1: 이미지 추출 (`ocr_training/scripts/extract_images.py`)

TS_3 zip 8개에서 JPEG 이미지를 `data/ocr_samples/images/`로 추출.

구현 요건:
- `TS_3_ZIPS` 리스트: 8개 학년 zip 경로 (절대 경로)
- 출력 디렉토리: `~/workSpace/Argus/data/ocr_samples/images/`
- 이미 존재하는 파일은 스킵 (재실행 안전)
- 진행 상황 tqdm으로 표시
- 완료 후 검증: `labels.json` 첫 10개 항목의 이미지 파일 존재 여부 확인
- 출력: `이미지 추출 완료: {n}개 / 예상 160,015개`

```bash
python3 ~/workSpace/Argus/ocr_training/scripts/extract_images.py
```

### Step 2: 데이터셋 준비 (`ocr_training/scripts/prepare_dataset.py`)

`labels.json` → GOT-OCR 2.0 파인튜닝 포맷(JSONL)으로 변환.

**GOT-OCR conversation 포맷**:
```json
{
  "id": "P3_1_01_21114_49506_8_X",
  "image": "/home/{user}/workSpace/Argus/data/ocr_samples/images/P3_1_01_21114_49506_8_X.jpeg",
  "conversations": [
    {
      "from": "human",
      "value": "<img>/home/{user}/workSpace/Argus/data/ocr_samples/images/P3_1_01_21114_49506_8_X.jpeg</img>\nOCR with format: "
    },
    {
      "from": "gpt",
      "value": "$ \\begin{array}{r} 296\\\\ 403\\\\ \\hline 759 \\end{array} $ $1$"
    }
  ]
}
```

처리 규칙:
- 이미지 파일이 실제 존재하는 항목만 포함
- `ground_truth_text`가 비어 있으면 스킵
- 전체 셔플 후 90/10 분할 → `train.jsonl` / `test.jsonl`
- 이미지 경로는 `Path.home()`으로 절대 경로 사용
- 완료 출력: `train: {n}개, test: {n}개`

```bash
python3 ~/workSpace/Argus/ocr_training/scripts/prepare_dataset.py
```

### Step 3: QLoRA 파인튜닝 (`ocr_training/scripts/train.py`)

**학습 설정**:

```python
BASE_MODEL = "stepfun-ai/GOT-OCR2_0"
TRAIN_DATA = "~/workSpace/Argus/data/ocr_samples/dataset/train.jsonl"
EVAL_DATA  = "~/workSpace/Argus/data/ocr_samples/dataset/test.jsonl"
OUTPUT_DIR = "~/workSpace/Argus/ocr_training/output/got_ocr_finetuned"

bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_use_double_quant=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_compute_dtype=torch.bfloat16,
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

training_args = TrainingArguments(
    output_dir=OUTPUT_DIR,
    num_train_epochs=3,
    per_device_train_batch_size=4,
    gradient_accumulation_steps=4,    # effective batch = 16
    learning_rate=2e-4,
    bf16=True,
    warmup_ratio=0.03,
    lr_scheduler_type="cosine",
    logging_steps=100,
    save_strategy="epoch",
    evaluation_strategy="epoch",
    load_best_model_at_end=True,
    metric_for_best_model="eval_loss",
    report_to="none",
    dataloader_num_workers=4,
)
```

> **주의**: GOT-OCR 2.0은 커스텀 코드 사용 — `trust_remote_code=True` 필수.

```bash
python3 ~/workSpace/Argus/ocr_training/scripts/train.py
```

예상 시간: epoch당 2~3시간, 총 7~8시간.

### Step 4: 평가 (`ocr_training/scripts/evaluate_ocr.py`)

- `test.jsonl`에서 1,000개 랜덤 샘플링
- 파인튜닝 모델 vs 기본 GOT-OCR 모델 CER 비교
- 지표: CER (Levenshtein), Exact Match Rate
- 결과 저장: `ocr_training/output/evaluation_results.json`

목표: CER < 5% (기본 모델 대비 개선 확인)

```bash
python3 ~/workSpace/Argus/ocr_training/scripts/evaluate_ocr.py
```

### Step 5: LoRA Merge (`ocr_training/scripts/merge_lora.py`)

LoRA 어댑터를 base model에 합쳐 단일 파라미터 파일로 내보낸다.

```python
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch

BASE_MODEL = "stepfun-ai/GOT-OCR2_0"
LORA_PATH  = "~/workSpace/Argus/ocr_training/output/got_ocr_finetuned"
OUTPUT_PATH = "~/workSpace/Argus/ocr_training/output/got_ocr_merged"

tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL, trust_remote_code=True)
base_model = AutoModelForCausalLM.from_pretrained(
    BASE_MODEL, trust_remote_code=True, torch_dtype=torch.float16,
)
model = PeftModel.from_pretrained(base_model, LORA_PATH)
merged = model.merge_and_unload()
merged.save_pretrained(OUTPUT_PATH)
tokenizer.save_pretrained(OUTPUT_PATH)
print(f"저장 완료: {OUTPUT_PATH}")
```

---

## 완료 기준

- [ ] `train.jsonl`, `test.jsonl` 생성 완료 (train ≥ 140,000개)
- [ ] 학습 3 epoch 완료, `eval_loss` 수렴 확인
- [ ] CER 기본 모델 대비 개선 확인
- [ ] `ocr_training/output/got_ocr_merged/` 생성 완료

---

## 완료 후 보고 사항

1. `output/evaluation_results.json` 내용 (기본 모델 CER vs 파인튜닝 후 CER)
2. 학습 곡선 요약 (초기 loss → 최종 loss)
3. `got_ocr_merged/` 크기 및 주요 파일 목록
4. Mac에서 Argus 백엔드 전환 방법:
   ```env
   OCR_MODEL=got_ocr
   GOT_OCR_MODEL_PATH=/home/{user}/workSpace/Argus/ocr_training/output/got_ocr_merged
   ```
   (또는 Mac으로 rsync 후 Mac 경로 지정)

---

## 참고

- GOT-OCR 2.0 GitHub: https://github.com/Ucas-HaoranWei/GOT-OCR2.0
- HuggingFace: stepfun-ai/GOT-OCR2_0
- 세부 전략: `docs/ocr_finetuning.md` 참조
