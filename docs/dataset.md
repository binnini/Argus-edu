# 데이터셋 구조 및 확보 전략

MVP 목표: AI-HUB 수학 데이터셋 기반 문제 및 손글씨 OCR 데이터 활용.

---

## 데이터 소스

### 주 데이터: AI-HUB

AI-HUB(aihub.or.kr)에서 제공하는 수학 관련 공개 데이터셋을 사용한다.

| 데이터셋 | 활용 목적 |
|---|---|
| 수학 문제 풀이 데이터 | 문제·정답·참조 풀이 확보 |
| 손글씨 수식 인식 데이터 | OCR 파이프라인 검증용 이미지-텍스트 쌍 |

**기존 자체 생성 데이터(Claude 생성 15개)는 품질 문제로 AI-HUB 데이터로 전면 교체.**

---

## 문제 JSON 스키마

DB의 `problems` 테이블에 삽입하기 전 검수용 JSON 형식.

```json
{
  "id": "수2_미분_001",
  "source": "AI-HUB_수학풀이_v1",
  "domain": "수학2",
  "topic": "미분",
  "difficulty": 2,
  "content": "함수 f(x) = x³ - 3x² + 1 의 구간 [0, 3]에서의 최솟값을 구하시오.",
  "answer": "-3",
  "reference_solution": {
    "steps": [
      {
        "step": 1,
        "title": "도함수 계산",
        "content": "f'(x) = 3x² - 6x = 3x(x - 2)"
      },
      {
        "step": 2,
        "title": "임계점 탐색",
        "content": "f'(x) = 0 에서 x = 0 또는 x = 2. 구간 [0, 3] 내 임계점은 x = 0, 2"
      },
      {
        "step": 3,
        "title": "최솟값 결정",
        "content": "f(0) = 1, f(2) = 8 - 12 + 1 = -3, f(3) = 27 - 27 + 1 = 1. 최솟값은 f(2) = -3"
      }
    ]
  },
  "rubric": {
    "total_score": 3,
    "steps": [
      {"step": 1, "description": "도함수를 올바르게 계산", "score": 1},
      {"step": 2, "description": "구간 내 임계점을 모두 탐색", "score": 1},
      {"step": 3, "description": "경계값 포함 최솟값 정확히 도출", "score": 1}
    ]
  }
}
```

`source` 필드에 AI-HUB 데이터셋 출처를 명시한다.

---

## OCR 테스트용 데이터 구조

AI-HUB 손글씨 수식 인식 데이터를 이미지 업로드 파이프라인 검증에 사용한다.

```
data/
├── problems/
│   └── aihub_math_*.json        # AI-HUB 변환 문제 데이터
├── ocr_samples/
│   ├── images/                  # 손글씨 이미지 샘플
│   │   ├── sample_001.jpg
│   │   └── ...
│   └── labels.json              # 이미지 → 정답 텍스트 매핑
└── test_answers/
    └── sample_submissions.json  # E2E 테스트용 학생 답변 샘플
```

### labels.json 형식

```json
[
  {
    "image": "images/sample_001.jpg",
    "problem_id": 1,
    "ground_truth": "f'(x) = 3x² - 6x이고 x = 0, 2에서 임계점. 최솟값은 f(2) = -3",
    "answer_type": "partial"
  }
]
```

`answer_type`: `correct` | `partial` | `wrong` — OCR 정확도 + 채점 파이프라인 통합 검증에 사용.

---

## AI-HUB 데이터 변환 절차

AI-HUB 원본 포맷 → Argus 문제 JSON 스키마 변환.

```
scripts/
├── convert_aihub.py   # AI-HUB 원본 → problems JSON 변환
└── seed.py            # problems JSON → PostgreSQL 삽입
```

### convert_aihub.py 역할

1. AI-HUB 다운로드 압축 해제 후 원본 JSON/CSV 파싱
2. `reference_solution` 단계 구조화 (AI-HUB 풀이가 비구조화된 경우 LLM으로 재구조화)
3. `rubric` 자동 생성 (풀이 단계 수 기반)
4. 검수 체크리스트 자동화 (정답·루브릭 합계 검증)

---

## 데이터 검수 체크리스트

AI-HUB 데이터라도 아래 항목을 반드시 확인한다.

- [ ] 정답이 수학적으로 올바른가
- [ ] reference_solution의 각 단계가 논리적으로 연결되는가
- [ ] rubric의 배점 합계 = total_score인가
- [ ] 수능 2~3점 유형과 난이도가 일치하는가 (킬러 문항 제외)
- [ ] 문제 본문의 LaTeX 수식이 올바르게 렌더링되는가

---

## 도메인 분포 목표

| 도메인 | 문제 수 | 주제 |
|---|---|---|
| 수학2 — 미분 | 10+ | 극값, 최솟값, 접선, 증감표 |
| 수학2 — 적분 | 7+ | 정적분, 넓이, 속도-거리 |
| 확률과 통계 | 8+ | 조합, 확률, 정규분포 |

> AI-HUB 데이터 수량에 따라 조정.
