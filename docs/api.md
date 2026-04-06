# API 스펙

모든 엔드포인트 접두사: `/api/v1/`  
교사 엔드포인트: 헤더 `X-Teacher-Password: {TEACHER_PASSWORD}` 필수

---

## 학생 — 답변 제출

### POST /api/v1/submissions

학생 답변을 제출하고 채점 파이프라인을 시작한다.

**Request**
```json
{
  "problem_id": 3,
  "student_answer": "f'(x) = 3x² - 6x이고, f'(x) = 0에서 x = 0 또는 x = 2. f(2) = 1이므로 최솟값은 1"
}
```

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

채점 결과 폴링. 풀이 설명은 교사 승인 후에만 포함된다.

**Response 200 — 채점 완료, 교사 검토 대기 중**
```json
{
  "submission_id": 42,
  "status": "graded",
  "score": 3,
  "score_visible": true,
  "explanation": null,
  "teacher_approved": false,
  "message": "교사 검토 중입니다. 풀이 설명은 검토 완료 후 확인할 수 있습니다."
}
```

**Response 200 — 교사 승인 완료**
```json
{
  "submission_id": 42,
  "status": "approved",
  "score": 3,
  "score_visible": true,
  "explanation": "**1단계**: f(x) = x³ - 3x² + 1을 미분하면...",
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
  "explanation": null,
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

개별 문제 상세. `answer`와 `reference_solution`은 응답에 포함하지 않음 (학생에게 노출 금지).

---

## 교사 — 검토 큐

### GET /api/v1/teacher/queue

검토 대기 중인 큐 목록. `action IS NULL` 항목만 반환.

**Response 200**
```json
{
  "queue": [
    {
      "queue_id": 7,
      "submission_id": 42,
      "problem_title": "수2_미분_001",
      "student_answer": "f'(x) = 3x² - 6x이고...",
      "ai_score": 3,
      "ai_explanation": "**1단계**: ...",
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
  "teacher_explanation": "2단계 계산 오류로 1점 감점. 올바른 풀이는..."
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
