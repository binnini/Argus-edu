# 데이터셋 구조 및 확보 전략

MVP 목표: AI-HUB 수학 데이터셋 기반 초·중·고 전과정 채점 및 손글씨 OCR 데이터 활용.

---

## 데이터 소스

### 주 데이터: AI-HUB

AI-HUB(aihub.or.kr)에서 제공하는 수학 관련 공개 데이터셋을 사용한다.

| 데이터셋 | 대상 학년 | 활용 목적 |
|---|---|---|
| TL_1 문제 + TL_2 모범답안 | 초3~6, 중1~3, 고등(공통수학) | 채점 문제 DB (30,050개) |
| TL_3 손글씨풀이 (라벨) | 초3~6, 중1~3, 고등(공통수학) | OCR ground truth 텍스트 |
| TS_3 손글씨풀이 (원천) | 초3~6, 중1~3, 고등(공통수학) | OCR 학습 이미지 (160,015개) |

**기존 자체 생성 데이터(Claude 생성 15개)는 품질 문제로 AI-HUB 데이터로 전면 교체.**

---

## AI-HUB 데이터 디렉토리 구조

```
data/AI_HUB/3.개방데이터/1.데이터/Training/
├── 01.원천데이터/          ← 이미지 원본
│   ├── TS_3.손글씨풀이_초등학교_3학년.zip   (13,486 JPEG)
│   ├── TS_3.손글씨풀이_초등학교_4학년.zip   (13,640 JPEG)
│   ├── TS_3.손글씨풀이_초등학교_5학년.zip   (22,698 JPEG)
│   ├── TS_3.손글씨풀이_초등학교_6학년.zip   (24,044 JPEG)
│   ├── TS_3.손글씨풀이_중학교_1학년.zip     (24,252 JPEG)
│   ├── TS_3.손글씨풀이_중학교_2학년.zip     (20,321 JPEG)
│   ├── TS_3.손글씨풀이_중학교_3학년.zip     (24,138 JPEG)
│   └── TS_3.손글씨풀이_고등학교_공통수학.zip (17,436 JPEG)
└── 02.라벨링데이터/        ← JSON 라벨
    ├── TL_1.문제_*.zip          ← 문제 본문 (LaTeX)
    ├── TL_2.모범답안_*.zip      ← 모범답안 텍스트
    └── TL_3.손글씨풀이_*.zip    ← 손글씨 ground truth 텍스트
```

---

## 문제 JSON 스키마

DB의 `problems` 테이블에 삽입하기 전 검수용 JSON 형식.

```json
{
  "id": "H_1_01_25766_84187",
  "source": "AI-HUB_고등학교_공통수학",
  "domain": "다항식의 연산",
  "difficulty": 3,
  "content": "문제 본문 (LaTeX $...$ 포함)",
  "answer": "$-3$",
  "reference_solution": {
    "steps": [
      {
        "step": 1,
        "title": "도함수 계산",
        "content": "f'(x) = 3x² - 6x = 3x(x - 2)"
      }
    ]
  },
  "rubric": {
    "total_score": 3,
    "steps": [
      {"step": 1, "description": "도함수 올바르게 계산", "score": 1}
    ]
  }
}
```

`source` 필드: `AI-HUB_초등학교_3학년` ~ `AI-HUB_고등학교_공통수학`

---

## OCR 파인튜닝 데이터 구조

### Argus 변환 데이터 (`data/ocr_samples/labels.json`)

`scripts/convert_aihub.py`가 TL_3 zip을 읽어 생성한다.

```json
[
  {
    "image": "images/P3_1_01_21114_49506_8_X.jpeg",
    "ground_truth_text": "$ \\begin{array}{r} 296\\\\ 403\\\\ \\hline 759 \\end{array} $ $1$",
    "expected_result": "correct",
    "source": "AI-HUB_초등학교_3학년"
  }
]
```

| 필드 | 설명 |
|---|---|
| `image` | `images/{filename}` — TS_3 zip에서 추출 후의 경로 |
| `ground_truth_text` | 이미지에 쓰인 텍스트 (LaTeX+한국어 혼합). OCR 학습 정답. |
| `expected_result` | 학생 답안의 정오. OCR 학습에는 무관 (전량 사용). |
| `source` | 학년 출처 |

**총 160,015개** — 이미지 다양성:
- 초등학교: 73,868개 (연산, 기초 도형)
- 중학교: 68,711개 (방정식, 함수, 도형)
- 고등학교: 17,436개 (수열, 극한, 미분)

### 파일 위치

```
data/
├── ocr_samples/
│   ├── labels.json          ← 160,015개 매핑 (gitignore — convert_aihub.py로 재생성)
│   └── images/              ← TS_3 zip 추출 후 생성 (gitignore)
└── problems/
    └── aihub_전과정_수학.json ← 30,050개 채점 문제 (gitignore — seed.py로 재삽입)
```

---

## AI-HUB 데이터 변환 절차

```
scripts/
├── convert_aihub.py   ← TL_1+TL_2 → problems JSON, TL_3 → labels.json
└── seed.py            ← problems JSON → PostgreSQL problems 테이블
```

### convert_aihub.py 동작

1. `GRADE_SETS` 리스트의 8개 학년을 순서대로 처리
2. TL_1(문제) + TL_2(모범답안) 병합 → `aihub_전과정_수학.json`
3. TL_3(손글씨 라벨) → `labels.json` (이미지 파일명 + ground truth 텍스트)
4. `question_type1 == "서술"` 필터링
5. `98856` 구분자로 reference_solution 단계 구조화

### 재실행 명령

```bash
cd /Users/yebin/workSpace/Argus
.venv/bin/python scripts/convert_aihub.py
DATABASE_URL=postgresql+asyncpg://yebin@localhost/argus_dev .venv/bin/python scripts/seed.py
```

---

## OCR 파인튜닝 전략

GOT-OCR 2.0을 WSL2 + RTX 5070Ti에서 QLoRA로 파인튜닝한다.

→ 상세 가이드: [docs/ocr_finetuning.md](ocr_finetuning.md)  
→ 에이전트 프롬프트: [docs/ocr_agent_prompt.md](ocr_agent_prompt.md)

파인튜닝 완료 후 서버 전환:
```env
OCR_MODEL=got_ocr
GOT_OCR_MODEL_PATH=/path/to/got_ocr_merged
```

---

## 데이터 검수 체크리스트

AI-HUB 데이터라도 아래 항목을 확인한다.

- [ ] reference_solution의 각 단계가 논리적으로 연결되는가
- [ ] rubric의 배점 합계 = total_score인가
- [ ] 문제 본문의 LaTeX 수식이 올바르게 렌더링되는가
- [ ] OCR labels.json의 ground_truth_text가 LaTeX 파싱 가능한가

---

## 데모 샘플 이미지셋 (학생 제출 프로토타입)

학생 샘플 입력 탭은 `uploads`가 아니라 `demo/images/manifest.json` 기준으로 동작한다.

- 생성 스크립트: `scripts/extract_demo_samples.py`
- 기본 정책:
  - 학교급(초/중/고)별 100개
  - 도메인별 최대 3개
  - 정답 이미지(`is_answer=true`) 메타데이터 포함

예시 실행:

```bash
.venv/bin/python scripts/extract_demo_samples.py
```
