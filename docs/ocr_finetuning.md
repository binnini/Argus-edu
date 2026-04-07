# GOT-OCR 2.0 파인튜닝 가이드

> AI-HUB 수학 손글씨 데이터로 GOT-OCR 2.0을 파인튜닝하여 한국어+수식 혼합 OCR 성능을 개선한다.  
> **실행 환경**: WSL2 (Ubuntu 22.04) + RTX 5070Ti (16GB VRAM)  
> **기반 모델**: [stepfun-ai/GOT-OCR2_0](https://huggingface.co/stepfun-ai/GOT-OCR2_0)

---

## 1. 데이터 구조

### 원본 AI-HUB 데이터 (Mac 기준 경로)

```
data/AI_HUB/3.개방데이터/1.데이터/Training/
├── 01.원천데이터/
│   ├── TS_3.손글씨풀이_초등학교_3학년.zip   ← 이미지 JPEG (13,486개)
│   ├── TS_3.손글씨풀이_초등학교_4학년.zip   ← 이미지 JPEG (13,640개)
│   ├── TS_3.손글씨풀이_초등학교_5학년.zip   ← 이미지 JPEG (22,698개)
│   ├── TS_3.손글씨풀이_초등학교_6학년.zip   ← 이미지 JPEG (24,044개)
│   ├── TS_3.손글씨풀이_중학교_1학년.zip     ← 이미지 JPEG (24,252개)
│   ├── TS_3.손글씨풀이_중학교_2학년.zip     ← 이미지 JPEG (20,321개)
│   ├── TS_3.손글씨풀이_중학교_3학년.zip     ← 이미지 JPEG (24,138개)
│   └── TS_3.손글씨풀이_고등학교_공통수학.zip ← 이미지 JPEG (17,436개)
└── 02.라벨링데이터/
    ├── TL_3.손글씨풀이_초등학교_3학년.zip   ← JSON (ground truth 텍스트)
    ├── ...
    └── TL_3.손글씨풀이_고등학교_공통수학.zip
```

**총 이미지**: 160,015개 (초등학교 3학년 ~ 고등학교 공통수학)

### Argus 변환 데이터

```
data/ocr_samples/labels.json  ← 이미지-텍스트 매핑 (160,015개)
```

`labels.json` 한 항목 예시:
```json
{
  "image": "images/P3_1_01_21114_49506_8_X.jpeg",
  "ground_truth_text": "$ \\begin{array}{r} 296\\\\ 403\\\\ \\hline 759 \\\\296\\\\ \\hline 5 \\end{array} $ $1$",
  "expected_result": "correct",
  "source": "AI-HUB_초등학교_3학년"
}
```

> `expected_result`는 학생 답안의 정오(正誤)를 나타내며, OCR 학습에는 무관. `ground_truth_text`가 해당 이미지에 쓰여진 실제 텍스트(LaTeX)이므로 정오 구분 없이 전량 사용.

---

## 2. 데이터 준비

에이전트 실행 전 Mac에서 WSL로 데이터를 전송해야 한다.

### 2-1. Mac → WSL 데이터 전송

```bash
# WSL에서 (192.168.219.101)
mkdir -p ~/argus_ocr/data/raw_zips
mkdir -p ~/argus_ocr/data/images
mkdir -p ~/argus_ocr/data/dataset

# Mac에서 rsync
rsync -avz \
  "/Users/yebin/workSpace/Argus/data/AI_HUB/3.개방데이터/1.데이터/Training/01.원천데이터/" \
  yebin@192.168.219.101:~/argus_ocr/data/raw_zips/source/

rsync -avz \
  "/Users/yebin/workSpace/Argus/data/ocr_samples/labels.json" \
  yebin@192.168.219.101:~/argus_ocr/data/
```

### 2-2. 이미지 추출 (WSL에서)

```bash
cd ~/argus_ocr
python3 scripts/extract_images.py
```

`scripts/extract_images.py`는 에이전트가 생성. 역할:
- `raw_zips/source/TS_3.손글씨풀이_*.zip` 전체 해제 → `data/images/`
- 해제 후 `labels.json`의 `image` 경로와 매핑 검증

---

## 3. GOT-OCR 2.0 모델 구조

- **기반**: Qwen-VL 계열 멀티모달 LLM (~580M params)
- **입력**: 이미지 + OCR 지시 텍스트
- **출력**: LaTeX 포함 구조화 텍스트
- **지원 OCR 유형**: plain text, format (LaTeX), fine-grained, multi-crop

### Fine-tuning 입력 포맷

GOT-OCR는 LLaVA 스타일 conversation 포맷을 사용한다.

```json
{
  "id": "P3_1_01_21114_49506_8_X",
  "image": "data/images/P3_1_01_21114_49506_8_X.jpeg",
  "conversations": [
    {
      "from": "human",
      "value": "<img>data/images/P3_1_01_21114_49506_8_X.jpeg</img>\nOCR with format: "
    },
    {
      "from": "gpt",
      "value": "$ \\begin{array}{r} 296\\\\ 403\\\\ \\hline 759 \\end{array} $"
    }
  ]
}
```

---

## 4. 파인튜닝 전략

### 4-1. 방법: QLoRA

| 파라미터 | 값 | 이유 |
|---|---|---|
| 방법 | QLoRA (4-bit NF4) | RTX 5070Ti 16GB에서 full fine-tuning 불가 |
| LoRA rank (r) | 16 | 성능-메모리 균형 |
| LoRA alpha | 32 | 일반적 2x rank |
| target modules | q_proj, k_proj, v_proj, o_proj, gate_proj, up_proj, down_proj | Attention + FFN |
| batch_size | 4 | VRAM 16GB 기준 |
| gradient_accumulation | 4 | effective batch = 16 |
| learning_rate | 2e-4 | LoRA 표준 |
| epochs | 3 | 160k 샘플 기준 충분 |
| bf16 | True | RTX 5070Ti 지원 |

### 4-2. 예상 학습 시간

```
160,015 samples / 16 (effective batch) = 10,001 steps/epoch
3 epochs = 30,003 steps
RTX 5070Ti 기준 ~0.3초/step → 약 9,000초 = 2.5시간/epoch → 총 7~8시간
```

---

## 5. 파인튜닝 후 검증

### 5-1. OCR 정확도 평가

평가 지표:
- **CER** (Character Error Rate): 문자 단위 오류율
- **LaTeX Match**: 핵심 수식 토큰 일치율

```bash
python3 scripts/evaluate_ocr.py \
  --model_path ./output/got_ocr_finetuned \
  --test_data ./data/dataset/test.jsonl \
  --num_samples 1000
```

### 5-2. 목표 지표

| 지표 | 목표 | 기본 GOT-OCR 기준 |
|---|---|---|
| CER | < 5% | ~15% (한국어+수식 혼합) |
| LaTeX 수식 매칭 | > 85% | ~70% |

---

## 6. 모델 내보내기

파인튜닝 완료 후 LoRA 어댑터를 base model에 merge하여 단일 파라미터 파일로 내보낸다.

```bash
python3 scripts/merge_lora.py \
  --base_model stepfun-ai/GOT-OCR2_0 \
  --lora_path ./output/got_ocr_finetuned \
  --output_path ./output/got_ocr_merged
```

내보낸 모델 디렉토리를 Mac의 `Argus` 서버에 업로드한 뒤, `.env`에서 전환:

```env
OCR_MODEL=got_ocr
GOT_OCR_MODEL_PATH=/path/to/got_ocr_merged
```

---

## 7. 파일 구조 (WSL)

```
~/argus_ocr/
├── data/
│   ├── raw_zips/source/       ← TS_3 원본 zip
│   ├── images/                ← 추출된 JPEG (~160k개)
│   ├── dataset/
│   │   ├── train.jsonl        ← 144k개 (90%)
│   │   └── test.jsonl         ← 16k개 (10%)
│   └── labels.json            ← Mac에서 rsync
├── scripts/
│   ├── extract_images.py
│   ├── prepare_dataset.py     ← labels.json → GOT-OCR 포맷 변환
│   ├── train.py               ← QLoRA 학습
│   ├── evaluate_ocr.py
│   └── merge_lora.py
├── output/
│   └── got_ocr_finetuned/     ← LoRA 체크포인트
└── requirements.txt
```
