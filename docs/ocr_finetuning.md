# GOT-OCR 2.0 파인튜닝 결과 기록

> **실행 환경**: WSL2 (Ubuntu 22.04) + RTX 5070Ti 16GB VRAM  
> **기반 모델**: [stepfun-ai/GOT-OCR2_0](https://huggingface.co/stepfun-ai/GOT-OCR2_0) (~580M params)  
> **참고 ADR**: ADR-017 (데이터셋), ADR-018 (파인튜닝 전략)

---

## 1. 데이터셋

### 구성

| 데이터 | 이미지 수 | 내용 |
|---|---|---|
| AI-HUB TS_3 손글씨풀이 (초3~고1 공통수학) | 160,015 | 수식 중심 손글씨, LaTeX 라벨 |
| AI-HUB 038 손글씨 (초4~6, 중1~3, 고1~3) | 119,233 | 한국어+수식 혼합 손글씨 |
| **합계** | **279,248** | |

**Split**: train ~251,000 / test ~28,000 (9:1)

### 038 데이터 전처리 규칙

- `type == '수식/텍스트'` segment만 사용 (낙서·기호·도형 제외)
- multi-segment 이미지: 각 segment `equation` 값을 줄바꿈으로 연결
- `\displaystyle` 접두사 제거 (TS_3 라벨 스타일 통일)

---

## 2. 파인튜닝 설정

### v1 실패 원인 (기록)

최초 학습(v1)은 `images 텐서 + ground_truth 토큰`만 입력으로 사용했다. 추론 시 `model.chat()`이 내부적으로 system/user 프롬프트를 앞에 붙이는 포맷을 전혀 학습하지 않아, 이미지를 무시하고 degenerate 출력(`$$$$의수의수...`)을 생성했다.

### v2 학습 포맷 (chat() 포맷 정렬)

`model.chat()`이 실제 생성하는 입력 시퀀스와 동일하게 학습 데이터를 구성했다.

```
input_ids:
  <|im_start|>system
          You should follow the instructions carefully and explain your answers in detail.<|im_end|>
  <|im_start|>user
  <img><imgpad>×256</img>
  OCR: <|im_end|>
  <|im_start|>assistant
  {ground_truth}<|im_end|>

labels:
  prompt 부분(-100 마스킹) + ground_truth + <|im_end|> 부분만 loss 계산
```

### 하이퍼파라미터

| 항목 | 값 | 비고 |
|---|---|---|
| 방법 | LoRA (bfloat16) | QLoRA 미사용 — VRAM 여유 확인 후 full precision LoRA |
| LoRA rank / alpha | 16 / 32 | |
| target modules | q/k/v/o/gate/up/down_proj | Attention + FFN 전체 |
| lora_dropout | 0.05 | |
| MAX_LENGTH | 640 | prompt 287 + gt 최대 353 tokens |
| batch_size | 2 | MAX_LENGTH 증가로 OOM 방지 |
| gradient_accumulation | 16 | effective batch = 32 |
| learning_rate | 2e-4 | cosine decay, warmup 3% |
| epochs | 3 | |
| attn_implementation | sdpa | flash-attn은 CUDA 13/Blackwell 미지원 |
| 이미지 전처리 | GOTImageEvalProcessor (BICUBIC, 1024×1024) | chat()과 동일 |
| images 포맷 | list[Tensor(1,C,H,W)], bfloat16 | OcrTrainer._prepare_inputs로 GPU 이동 |

---

## 3. 학습 결과

### Loss 추이

| Step | Epoch | Train Loss | Eval Loss |
|------|-------|-----------|-----------|
| 10 | 0.00 | 2.956 | — |
| 200 | 0.03 | 1.107 | — |
| 1,000 | 0.13 | 0.767 | — |
| 7,000 | 0.91 | — | **0.4756** |
| 14,000 | 1.82 | — | **0.4160** |
| 21,000 | 2.73 | — | **0.4008** |
| 23,079 (완료) | 3.00 | 0.33 | — |

- 총 학습 시간: **약 46시간** (RTX 5070Ti, batch=2, MAX_LENGTH=640)
- 과적합 없음: eval loss가 3 epoch 내내 감소

---

## 4. 평가 결과

**평가 방식**: `model.chat(tokenizer, image_path, ocr_type=...)`, n=1,000 샘플 (random seed=42)  
**평가 지표**: CER (Character Error Rate = Levenshtein / len(ref)), EM (Exact Match)

| 모델 | OCR 타입 | CER | EM |
|------|----------|-----|----|
| Base GOT-OCR 2.0 | ocr | 1.0616 (106.2%) | 0.9% |
| Base GOT-OCR 2.0 | format | 2.1330 (213.3%) | 0.0% |
| **Fine-tuned v2** | **ocr** | **0.3181 (31.8%)** | **23.5%** |
| **Fine-tuned v2** | **format** | **0.3202 (32.0%)** | **22.0%** |

### 분석

- **CER 개선**: ocr -70.1%, format -85.0%
- **format 타입**: base에서 수학 수식을 SMILES 화학식으로 오분류하던 문제 해소 — fine-tuned 후 ocr 타입과 동일 수준
- **목표 CER 5% 미달성**: **LaTeX 수식 특성상 공백·괄호·명령어 하나 차이도 CER에 반영됨**. \n, \times \slice 등 다양한 특수 문자 데이터의 존재와 데이터의 위치정보를 고려하면 성능 확보가 애초에 어려운 학습 데이터
- **체크포인트 조기 테스트**: checkpoint-4000 (epoch 0.52) 시점에서 이미 LaTeX 구조 정상 출력 확인 (5샘플 완전 일치 2건, 구조 정확 3건)

---

## 5. 산출물

```
ocr_training/output/
├── got_ocr_finetuned_v2/           ← 학습 출력 (LoRA 어댑터)
│   ├── adapter_model.safetensors   ← 최종 어댑터
│   ├── adapter_config.json
│   ├── checkpoint-20000/
│   ├── checkpoint-22000/
│   ├── checkpoint-23079/
│   └── train.log
├── got_ocr_merged/                 ← Merge 완료 모델 (서빙용)
│   ├── model.safetensors           ← 1,069 MB (base + LoRA 병합)
│   ├── tokenizer_config.json
│   └── ...
└── evaluation_comparison.json      ← 평가 결과 JSON
```

---

## 6. 서빙 설정

### WSL 환경

```env
OCR_MODEL=got_ocr
GOT_OCR_MODEL_PATH=/home/yebin/projects/Argus-edu/ocr_training/output/got_ocr_merged
```

### Mac Mini M4 환경 (ADR-020)

```env
OCR_MODEL=got_ocr
GOT_OCR_MODEL_PATH=/path/to/got_ocr_merged
```

- `torch_dtype=torch.float32` (MPS bfloat16 미지원)
- `modeling_GOT.py`의 `.cuda()` 하드코딩 → `next(self.parameters()).device`로 패치 적용

### 추론 코드

```python
result = model.chat(tokenizer, image_path, ocr_type="ocr")
```

---

## 7. 재현 방법

```bash
# 1. 데이터 준비
python ocr_training/scripts/extract_images.py
python ocr_training/scripts/prepare_dataset.py

# 2. 학습 (WSL, RTX 5070Ti)
source ~/miniconda3/etc/profile.d/conda.sh && conda activate argus-ocr
tmux new-session -d -s train \
  'python -u ocr_training/scripts/train.py 2>&1 | tee ocr_training/output/got_ocr_finetuned_v2/train_stdout.log'

# 3. 평가
python ocr_training/scripts/evaluate_ocr.py

# 4. LoRA Merge
LORA_DIR=ocr_training/output/got_ocr_finetuned_v2 \
  python ocr_training/scripts/merge_lora.py
```
