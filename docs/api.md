# API 스펙 (현재 구현 기준)

기본 prefix: `/api/v1`

교사 인증이 필요한 엔드포인트는 헤더가 필요합니다.

```http
X-Teacher-Password: <TEACHER_PASSWORD>
```

## 시스템

### GET `/health`

서버 상태와 메모리/작업 큐 통계를 반환합니다.

예시 응답:

```json
{
  "status": "ok",
  "memory_mb": 324.14,
  "queues": {
    "feedback": {"pending": 1, "running": 0, "done": 32},
    "hallucination": {"pending": 0, "running": 0, "done": 31}
  }
}
```

## 학생 API

### GET `/problems`

문제 목록 조회(페이지네이션/필터).

쿼리 파라미터:
- `page` (default: 1)
- `page_size` (default: 10, max: 100)
- `domain` (부분 일치)
- `school_level` (부분 일치)
- `has_sample_answer` (optional, 샘플 정답 이미지 존재 여부)
- `difficulty` (1~5)
- `q` (제목/도메인 검색)

### GET `/problems/domains`

도메인 목록 조회.

쿼리 파라미터:
- `school_level` (optional)

### GET `/problems/{problem_id}`

문제 상세 조회.

주의:
- `answer`, `reference_solution`은 학생 API 응답에 포함되지 않습니다.

### POST `/submissions`

텍스트 답안 제출.

요청 본문:

```json
{
  "problem_id": 1,
  "student_answer": "풀이 본문",
  "student_name": "홍길동",
  "student_id": "20260001",
  "final_answer": "-3"
}
```

응답(202):

```json
{
  "submission_id": 101,
  "status": "pending",
  "message": "채점이 시작되었습니다. 결과는 잠시 후 확인할 수 있습니다."
}
```

### POST `/submissions/image`

이미지 제출 + OCR.

`multipart/form-data` 필드:
- `problem_id` (required)
- `image` (required)
- `student_name` (optional, 기본값 빈 문자열)
- `student_id` (optional)
- `student_final_answer` (optional)

### GET `/submissions/{submission_id}`

제출 상태/점수/피드백 조회.

핵심 필드:
- `status`: `pending | graded | approved | rejected | error`
- `score`, `max_score`, `score_visible`
- `feedback`, `feedback_visible`, `feedback_status`
- `solution_status`
- `hallucination_status`
- `teacher_approved`, `auto_approved`

### GET `/submissions`

학생 제출 이력 조회.

쿼리 파라미터:
- `student_id` (required)

### GET `/submissions/homework`

학생 숙제 현황 조회.

쿼리 파라미터:
- `student_id` (required)

### GET `/students/verify`

이름/학번 검증.

쿼리 파라미터:
- `student_id` (required)
- `student_name` (required)

## 프로토타입 샘플 이미지 API

`PROTOTYPE_SAMPLE_IMAGES_ENABLED=true`일 때 사용.

### GET `/prototype/sample-images`

샘플 목록(학교급/도메인 단위) 조회.

쿼리 파라미터:
- `school_level` (optional)
- `domain` (optional)

### GET `/prototype/problem-sample-images`

문제 선택용 샘플 이미지 후보 조회.

쿼리 파라미터:
- `problem_id` (optional)
- `school_level` (required)
- `domain` (required)

응답 항목에는 샘플이 정답 이미지인 경우 `answer_text`가 포함될 수 있습니다.

### GET `/prototype/sample-images/{sample_id}/content`

샘플 이미지 바이너리 반환.

## 교사 API

### GET `/teacher/queue`

검토 큐 조회.

쿼리 파라미터:
- `trust_level` (optional)
- `review_status`: `pending | approved | modify | reject | reviewed | all`
- `sort`: `sla | latest`
- `page`, `page_size`

### GET `/teacher/queue/health`

작업 큐(feedback/hallucination) 카운트 조회.

### POST `/teacher/queue/{queue_id}/action`

교사 액션 제출.

요청 본문:

```json
{
  "action": "approve"
}
```

또는

```json
{
  "action": "modify",
  "teacher_score": 2,
  "teacher_feedback": "2단계 계산에서 부호가 바뀌었습니다."
}
```

`action` 값:
- `approve`
- `modify` (`teacher_score`, `teacher_feedback` 필수)
- `reject`

### GET `/teacher/submissions`

제출 현황 목록 조회.

쿼리 파라미터:
- `problem_id`, `status`, `student_name`, `page`, `page_size`

### GET `/teacher/problems/{problem_id}/submissions`

특정 문제의 제출 현황 조회.

쿼리 파라미터:
- `page`, `page_size`

### GET `/teacher/feedback/summary`

교사 검토 로그 집계 조회.

## 교사 문제 관리 API

### POST `/teacher/problems`

문제 생성.

### GET `/teacher/problems`

문제 목록 조회.

쿼리 파라미터:
- `page`, `page_size`, `has_submissions`, `school_level`

### PUT `/teacher/problems/{problem_id}`

문제 수정.

### DELETE `/teacher/problems/{problem_id}`

문제 삭제.

동작:
- 제출이 없으면 hard delete
- 제출이 있으면 `soft_deleted=true`

## 그룹/숙제 API

### GET `/teacher/groups`
### POST `/teacher/groups`
### DELETE `/teacher/groups/{group_id}`
### POST `/teacher/groups/{group_id}/members`
### DELETE `/teacher/groups/{group_id}/members/{student_id}`

### GET `/teacher/homeworks`
### POST `/teacher/homeworks`
### DELETE `/teacher/homeworks/{homework_id}`

## 상태 값 요약

- `submissions.status`: `pending | graded | approved | rejected | error`
- `grading_results.feedback_status`: `pending | running | done | failed`
- `grading_results.hallucination_status`: `pending | running | done | failed`
- `teacher_queue.action`: `approve | modify | reject | null`
