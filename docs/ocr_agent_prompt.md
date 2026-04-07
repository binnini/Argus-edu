# GOT-OCR 2.0 파인튜닝 에이전트 프롬프트

> 이 파일을 새 Claude Code 세션의 초기 프롬프트로 사용한다.  
> 실행 환경: WSL2 (Ubuntu 22.04) + RTX 5070Ti 16GB

---

## 컨텍스트

"Argus"라는 수학 서답형 자동 채점 시스템을 개발 중이다.  
학생들이 손으로 쓴 수학 풀이 이미지를 OCR로 텍스트화하는 파이프라인이 필요하다.

기존 pix2tex는 한국어+LaTeX 혼합 텍스트에 약하여, GOT-OCR 2.0을 AI-HUB 수학 손글씨 데이터로 파인튜닝해 사용할 것이다.

---

## 네 역할

WSL2 환경에서 GOT-OCR 2.0 파인튜닝 파이프라인을 처음부터 끝까지 구현하고 실행한다.

---

## 현재 상태

### 데이터 (Mac에서 rsync 예정)

```
~/argus_ocr/data/
├── labels.json          ← 이미 전송됨 (160,015개 이미지-텍스트 쌍)
└── raw_zips/source/     ← TS_3.손글씨풀이_*.zip 8개 파일 (이미지 원본)
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

> `ground_truth_text`: 이미지에 쓰여진 텍스트 (LaTeX+한국어 혼합). OCR 학습 정답.  
> `expected_result`: 학생 풀이의 정오 — OCR 학습에 무관. 전체 160k 사용.  
> `image` 파일명은 `raw_zips/source/TS_3.손글씨풀이_*.zip` 내부 파일과 매칭됨.

### 목표 디렉토리 구조

```
~/argus_ocr/
├── data/
│   ├── labels.json
│   ├── raw_zips/source/       ← TS_3 zip 8개
│   ├── images/                ← 추출 후 생성
│   └── dataset/
│       ├── train.jsonl        ← 144k개 (90%)
│       └── test.jsonl         ← 16k개 (10%)
├── scripts/
│   ├── extract_images.py
│   ├── prepare_dataset.py
│   ├── train.py
│   ├── evaluate_ocr.py
│   └── merge_lora.py
├── output/                    ← 체크포인트 저장
└── requirements.txt
```

---

## 수행할 작업 (순서대로)

### Step 1: 환경 설정

```bash
# CUDA 확인
nvidia-smi
python3 -c "import torch; print(torch.cuda.is_available(), torch.version.cuda)"

# 작업 디렉토리 생성
mkdir -p ~/argus_ocr/{data/{raw_zips/source,images,dataset},scripts,output}
```

`requirements.txt` 작성 후 설치:
```
torch>=2.1.0
transformers>=4.40.0
peft>=0.10.0
bitsandbytes>=0.43.0
accelerate>=0.29.0
datasets>=2.18.0
tqdm
pillow
Levenshtein
```

### Step 2: 이미지 추출 (`scripts/extract_images.py`)

- `~/argus_ocr/data/raw_zips/source/TS_3.손글씨풀이_*.zip` 8개 파일을 순서대로 열기
- 각 zip 내 JPEG 파일을 `~/argus_ocr/data/images/` 에 추출
- 이미 존재하는 파일은 스킵 (재실행 안전)
- 완료 후 `labels.json`의 샘플 10개에 대해 이미지 파일 존재 여부 검증
- 출력: `이미지 추출 완료: {n}개 / 예상 160,015개`

### Step 3: 데이터셋 준비 (`scripts/prepare_dataset.py`)

`labels.json` → GOT-OCR 2.0 파인튜닝 포맷(JSONL)으로 변환.

**GOT-OCR conversation 포맷**:
```json
{
  "id": "P3_1_01_21114_49506_8_X",
  "image": "/home/{user}/argus_ocr/data/images/P3_1_01_21114_49506_8_X.jpeg",
  "conversations": [
    {
      "from": "human",
      "value": "<img>/home/{user}/argus_ocr/data/images/P3_1_01_21114_49506_8_X.jpeg</img>\nOCR with format: "
    },
    {
      "from": "gpt",
      "value": "$ \\begin{array}{r} 296\\\\ 403\\\\ \\hline 759 \\end{array} $ $1$"
    }
  ]
}
```

처리 규칙:
- 이미지 파일이 실제 존재하는 항목만 포함 (존재 검증)
- `ground_truth_text`가 비어 있으면 스킵
- 전체를 섞은 뒤 90/10 분할 → `train.jsonl` / `test.jsonl`
- 완료 출력: `train: {n}개, test: {n}개`

### Step 4: QLoRA 파인튜닝 (`scripts/train.py`)

**학습 설정**:

```python
# 모델
BASE_MODEL = "stepfun-ai/GOT-OCR2_0"

# QLoRA 설정
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

# 학습 파라미터
training_args = TrainingArguments(
    output_dir="~/argus_ocr/output/got_ocr_finetuned",
    num_train_epochs=3,
    per_device_train_batch_size=4,
    gradient_accumulation_steps=4,       # effective batch = 16
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

실행 중 매 100 step마다 로그 출력. 학습 완료 시 `output/got_ocr_finetuned/` 에 저장.

> **주의**: GOT-OCR 2.0은 커스텀 모델 코드를 사용하므로 `trust_remote_code=True` 필수.

### Step 5: 평가 (`scripts/evaluate_ocr.py`)

- `test.jsonl`에서 1,000개 랜덤 샘플링
- 파인튜닝 모델 vs 기본 GOT-OCR 모델 성능 비교
- 지표:
  - **CER** (Character Error Rate): `Levenshtein` 라이브러리 사용
  - **Exact Match Rate**: ground truth와 완전 일치 비율
- 결과를 `output/evaluation_results.json`에 저장

### Step 6: LoRA Merge (`scripts/merge_lora.py`)

```python
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

base_model = AutoModelForCausalLM.from_pretrained(
    "stepfun-ai/GOT-OCR2_0",
    trust_remote_code=True,
    torch_dtype=torch.float16,
)
model = PeftModel.from_pretrained(base_model, "./output/got_ocr_finetuned")
merged = model.merge_and_unload()
merged.save_pretrained("./output/got_ocr_merged")
tokenizer.save_pretrained("./output/got_ocr_merged")
```

---

## 완료 기준

- [ ] `train.jsonl`, `test.jsonl` 생성 완료
- [ ] 학습 3 epoch 완료, `eval_loss` 수렴 확인
- [ ] CER < 15% (파인튜닝 전 기준 대비 개선 확인)
- [ ] `output/got_ocr_merged/` 생성 완료

---

## 완료 후 전달 사항

모든 작업 완료 후 아래 정보를 보고한다:

1. `output/evaluation_results.json` 내용 (CER, Exact Match)
2. 학습 곡선 요약 (초기 loss → 최종 loss)
3. `output/got_ocr_merged/` 의 크기 및 파일 목록
4. Mac으로 모델을 전송하기 위한 rsync 명령어:
   ```bash
   rsync -avz ~/argus_ocr/output/got_ocr_merged/ \
     "yebin@{mac_ip}:/Users/yebin/workSpace/Argus/models/got_ocr_merged/"
   ```

---

## 참고 링크

- GOT-OCR 2.0 GitHub: https://github.com/Ucas-HaoranWei/GOT-OCR2.0
- HuggingFace: stepfun-ai/GOT-OCR2_0
- 파인튜닝 참고: https://github.com/Ucas-HaoranWei/GOT-OCR2.0/tree/main/GOT-OCR-2.0-master
