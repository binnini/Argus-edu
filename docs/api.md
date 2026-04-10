# API 스펙

모든 엔드포인트 접두사: `/api/v1/`  
교사 엔드포인트: 헤더 `X-Teacher-Password: {TEACHER_PASSWORD}` 필수

---

## 학생 — 답변 제출

### POST /api/v1/submissions

학생 답변을 제출하고 채점 파이프라인을 시작한다.  
텍스트 직접 입력과 이미지 업로드 두 가지 방식을 지원한다.

**Request (텍스트 입력) — application/json**
```json
{
  "problem_id": 3,
  "student_name": "홍길동",
  "student_id": "20240101",
  "student_answer": "f'(x) = 3x² - 6x이고, f'(x) = 0에서 x = 0 또는 x = 2. f(2) = 1이므로 최솟값은 1"
}
```

- `student_name`: 필수. 교사 대시보드 현황 조회에 사용.
- `student_id`: 선택. 동명이인 구분용 학번.

**Request (이미지 업로드) — multipart/form-data**
```
problem_id: 3
student_name: 홍길동
student_id: 20240101      (optional)
image: <binary image file>   # 손글씨 사진, 스캔 이미지, 캔버스 PNG
```

이미지 업로드 시 백엔드가 OCR을 수행하여 `student_answer`를 추출한다.

**Response 202** — 채점 비동기 시작
```json
{
  "submission_id": 42,
  "status": "pending",
  "message": "채점이 시작되었습니다. 결과는 잠시 후 확인할 수 있습니다."
}
```

---

### GET /api/v1/submissions/{submission_id}

채점 결과 폴링. 개인화 피드백은 교사 승인 후에만 포함된다.

**Response 200 — 채점 완료, 교사 검토 대기 중**
```json
{
  "submission_id": 42,
  "status": "graded",
  "score": 3,
  "score_visible": true,
  "feedback": null,
  "teacher_approved": false,
  "message": "교사 검토 중입니다. 피드백은 검토 완료 후 확인할 수 있습니다."
}
```

**Response 200 — 교사 승인 완료**
```json
{
  "submission_id": 42,
  "status": "approved",
  "score": 3,
  "score_visible": true,
  "feedback": {
    "student_mistakes": [
      { "step": 2, "description": "f(2) = 8 - 12 + 1 = -3인데 f(2) = 1로 계산하여 오류" }
    ],
    "correct_approach": [
      { "step": 1, "title": "도함수 계산", "content": "f'(x) = 3x² - 6x = 3x(x-2)" },
      { "step": 2, "title": "임계점 대입", "content": "f(0)=1, f(2)=-3, f(3)=1" },
      { "step": 3, "title": "최솟값 결정", "content": "가장 작은 f(2)=-3이 최솟값" }
    ],
    "key_concept": "닫힌 구간에서 최솟값은 임계점과 양 끝점 모두 비교해야 합니다."
  },
  "teacher_approved": true,
  "message": null
}
```

**Response 200 — 채점 대기 중 (신뢰도 Low)**
```json
{
  "submission_id": 42,
  "status": "graded",
  "score": null,
  "score_visible": false,
  "feedback": null,
  "teacher_approved": false,
  "message": "채점 결과를 검토 중입니다."
}
```

---

## 학생 — 문제 조회

### GET /api/v1/problems

전체 문제 목록.

**Response 200**
```json
{
  "problems": [
    {
      "id": 1,
      "title": "수2_미분_001",
      "content": "함수 f(x) = x³ - 3x² + 1 의 최솟값을 구하시오.",
      "domain": "수학2",
      "difficulty": 2,
      "total_score": 3
    }
  ]
}
```

### GET /api/v1/problems/{problem_id}

개별 문제 상세.  
`answer`와 `reference_solution`은 응답에 포함하지 않음 (학생에게 노출 금지).

---

## 교사 — 문제 관리

모든 엔드포인트에 `X-Teacher-Password` 헤더 필수.

### POST /api/v1/teacher/problems

문제 등록.

**Request**
```json
{
  "title": "수2_미분_002",
  "content": "함수 $f(x) = x^3 - 3x^2 + 1$ 의 최솟값을 구하시오.",
  "answer": "-3",
  "reference_solution": "1단계: 도함수...\n2단계: 임계점...",
  "rubric": {
    "total_score": 3,
    "steps": [
      {"step": 1, "description": "도함수 계산", "score": 1},
      {"step": 2, "description": "임계점 대입", "score": 1},
      {"step": 3, "description": "최솟값 결정", "score": 1}
    ]
  },
  "domain": "수학2",
  "difficulty": 2
}
```

**Response 201**
```json
{ "id": 5, "title": "수2_미분_002", "created_at": "2026-04-10T10:00:00Z" }
```

---

### GET /api/v1/teacher/problems

교사용 문제 목록. 정답·참조 풀이·루브릭 포함.

**Response 200**
```json
{
  "problems": [
    {
      "id": 1,
      "title": "수2_미분_001",
      "content": "함수 f(x) = x³ - 3x² + 1 의 최솟값을 구하시오.",
      "answer": "-3",
      "reference_solution": "1단계: ...",
      "rubric": { "total_score": 3, "steps": [...] },
      "domain": "수학2",
      "difficulty": 2,
      "submission_count": 12,
      "created_at": "2026-04-06T10:00:00Z"
    }
  ]
}
```

---

### PUT /api/v1/teacher/problems/{problem_id}

문제 수정. 요청 본문은 POST와 동일 (부분 수정 가능, 생략된 필드는 유지).

**Response 200** — 수정된 문제 전체 반환

---

### DELETE /api/v1/teacher/problems/{problem_id}

문제 삭제.  
- 제출이 1건 이상 있으면 `soft_delete=true` 플래그 설정 (목록에서 숨김, 데이터 보존).
- 제출이 없으면 완전 삭제.

**Response 200**
```json
{ "id": 5, "deleted": true, "soft_delete": false }
```

---

## 교사 — 학생 제출 현황

### GET /api/v1/teacher/submissions

전체 제출 목록. 필터·정렬 지원.

**Query Parameters**
```
problem_id=1         (optional) 문제 필터
status=graded        (optional) pending | graded | approved | rejected
student_name=홍길동  (optional) 이름 검색 (부분 일치)
page=1               (optional, default=1)
page_size=20         (optional, default=20, max=100)
```

**Response 200**
```json
{
  "submissions": [
    {
      "submission_id": 42,
      "problem_id": 1,
      "problem_title": "수2_미분_001",
      "student_name": "홍길동",
      "student_id": "20240101",
      "input_type": "image",
      "status": "approved",
      "ai_score": 2,
      "final_score": 2,
      "trust_level": "high",
      "submitted_at": "2026-04-10T09:00:00Z",
      "reviewed_at": "2026-04-10T10:30:00Z"
    }
  ],
  "total": 47,
  "page": 1,
  "page_size": 20
}
```

- `final_score`: 교사 수정 시 `teacher_score`, 아니면 `ai_score`. 미검토 시 `null`.

---

### GET /api/v1/teacher/problems/{problem_id}/submissions

특정 문제의 제출 현황. 응답 구조는 위와 동일.

---

## 교사 — 검토 큐

### GET /api/v1/teacher/queue

검토 대기 중인 큐 목록. `action IS NULL` 항목만 반환. SLA 마감 오름차순 정렬.

**Query Parameters**
```
trust_level=low    (optional) high | low — 신뢰도 필터
```

**Response 200**
```json
{
  "queue": [
    {
      "queue_id": 7,
      "submission_id": 42,
      "problem_title": "수2_미분_001",
      "student_name": "홍길동",
      "student_id": "20240101",
      "student_answer": "f'(x) = 3x² - 6x이고...",
      "input_type": "text",
      "ai_score": 2,
      "ai_feedback": {
        "student_mistakes": [
          { "step": 2, "description": "f(2) 계산 오류" }
        ],
        "correct_approach": [...],
        "key_concept": "..."
      },
      "trust_score": 0.61,
      "trust_level": "low",
      "queue_type": "full_review",
      "sla_deadline": "2026-04-07T14:00:00Z",
      "queued_at": "2026-04-06T14:00:00Z"
    }
  ],
  "total": 1
}
```

---

### POST /api/v1/teacher/queue/{queue_id}/action

교사 액션 제출. 3가지 중 하나만 허용.

**Request — 승인**
```json
{
  "action": "approve"
}
```

**Request — 수정**
```json
{
  "action": "modify",
  "teacher_score": 2,
  "teacher_feedback": "2단계에서 f(2)를 잘못 계산했습니다. f(2) = 8 - 12 + 1 = -3이 맞습니다. 닫힌 구간 최솟값은 임계점과 양 끝점을 모두 비교해야 합니다."
}
```

**Request — 거부**
```json
{
  "action": "reject"
}
```

**Response 200**
```json
{
  "queue_id": 7,
  "action": "modify",
  "reviewed_at": "2026-04-06T15:30:00Z"
}
```

**오류**: `action`이 3가지 외 값이면 422 반환.

---

## 교사 — 피드백 현황

### GET /api/v1/teacher/feedback/summary

AI vs 교사 채점 delta 집계.

**Response 200**
```json
{
  "total_reviewed": 47,
  "approved": 35,
  "modified": 9,
  "rejected": 3,
  "approval_rate": 0.745,
  "avg_score_delta": 0.42,
  "low_trust_detection_precision": 0.82
}
```
