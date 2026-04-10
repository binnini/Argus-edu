# DB 스키마

PostgreSQL. SQLAlchemy async ORM 사용.

---

## 테이블 정의

### problems — 문제 원본

```sql
CREATE TABLE problems (
    id              SERIAL PRIMARY KEY,
    title           VARCHAR(200) NOT NULL,           -- 문제 제목 (예: "수2_미분_001")
    content         TEXT NOT NULL,                   -- 문제 본문 (LaTeX 포함 가능)
    answer          VARCHAR(100) NOT NULL,           -- 정답 (숫자 또는 식)
    reference_solution TEXT NOT NULL,               -- 단계별 참조 풀이 (채점·피드백 기준)
    rubric          JSONB NOT NULL,                  -- 채점 루브릭 (아래 형식 참조)
    domain          VARCHAR(50) DEFAULT '수학2',
    difficulty      SMALLINT CHECK (difficulty BETWEEN 1 AND 5),
    source          VARCHAR(100),                    -- 데이터 출처 (예: 'AI-HUB_수학_v1')
    soft_deleted    BOOLEAN DEFAULT FALSE,           -- 제출이 있는 문제 삭제 시 soft delete (ADR-021)
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- rubric JSONB 형식
-- {
--   "total_score": 3,
--   "steps": [
--     {"step": 1, "description": "미분 공식 적용", "score": 1},
--     {"step": 2, "description": "도함수 계산", "score": 1},
--     {"step": 3, "description": "최솟값 도출", "score": 1}
--   ]
-- }
```

### submissions — 학생 답변 제출

```sql
CREATE TABLE submissions (
    id              SERIAL PRIMARY KEY,
    problem_id      INTEGER REFERENCES problems(id) NOT NULL,
    student_name    VARCHAR(50) NOT NULL,            -- 학생 이름 (인증 없이 자유 입력, ADR-021)
    student_id      VARCHAR(20),                     -- 학번 (optional, 동명이인 구분)
    input_type      VARCHAR(10) NOT NULL DEFAULT 'text',  -- 'text' | 'image' | 'canvas'
    student_answer  TEXT NOT NULL,                   -- 최종 텍스트 답변 (OCR 결과 또는 직접 입력)
    ocr_raw_text    TEXT,                            -- OCR 원본 출력 (input_type='image'|'canvas' 시 저장)
    image_path      VARCHAR(500),                    -- 업로드 이미지 경로 (input_type='image'|'canvas' 시)
    submitted_at    TIMESTAMPTZ DEFAULT NOW(),
    status          VARCHAR(20) DEFAULT 'pending'    -- pending | graded | approved | rejected | error
);
```

> **마이그레이션**: `backend/alembic/versions/0003_add_student_info.py`

### grading_results — AI 채점 결과

```sql
CREATE TABLE grading_results (
    id                  SERIAL PRIMARY KEY,
    submission_id       INTEGER REFERENCES submissions(id) UNIQUE NOT NULL,
    ai_score            SMALLINT NOT NULL,            -- AI 채점 점수
    ai_feedback         TEXT NOT NULL,                -- AI 개인화 피드백 (교사 승인 전 비공개)
                                                     -- 학생 오류 분석 + 교정 방향 포함
    sbert_similarity    FLOAT NOT NULL,               -- SBERT 유사도 (0~1)
    hhem_score          FLOAT NOT NULL,               -- 피드백 정확성 점수 (0~1)
    inconsistency_rate  FLOAT NOT NULL,               -- 멀티샘플링 피드백 불일치율 (0~1)
    trust_score         FLOAT NOT NULL,               -- 종합 신뢰도 (0~1)
    trust_level         VARCHAR(10) NOT NULL,         -- 'high' | 'low'
    graded_at           TIMESTAMPTZ DEFAULT NOW()
);
```

### teacher_queue — 교사 검토 큐

```sql
CREATE TABLE teacher_queue (
    id              SERIAL PRIMARY KEY,
    submission_id   INTEGER REFERENCES submissions(id) UNIQUE NOT NULL,
    queue_type      VARCHAR(20) NOT NULL,             -- 'score_only' | 'full_review'
                                                     -- score_only: High 신뢰도 (피드백만 검토)
                                                     -- full_review: Low 신뢰도 (채점+피드백 검토)
    sla_deadline    TIMESTAMPTZ NOT NULL,             -- SLA 마감 시각
    action          VARCHAR(10),                      -- NULL | 'approve' | 'modify' | 'reject'
    teacher_score   SMALLINT,                         -- 수정 시 교사 확정 점수
    teacher_feedback TEXT,                            -- 수정 시 교사 작성 피드백
    reviewed_at     TIMESTAMPTZ,
    queued_at       TIMESTAMPTZ DEFAULT NOW()
);
```

### feedback_log — AI vs 교사 delta 기록

```sql
CREATE TABLE feedback_log (
    id                  SERIAL PRIMARY KEY,
    submission_id       INTEGER REFERENCES submissions(id) NOT NULL,
    ai_score            SMALLINT NOT NULL,
    teacher_score       SMALLINT NOT NULL,
    score_delta         SMALLINT GENERATED ALWAYS AS (teacher_score - ai_score) STORED,
    action              VARCHAR(10) NOT NULL,          -- 'approve' | 'modify' | 'reject'
    trust_score         FLOAT NOT NULL,
    trust_level         VARCHAR(10) NOT NULL,
    logged_at           TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 인덱스

```sql
CREATE INDEX idx_teacher_queue_action_null  ON teacher_queue(queued_at) WHERE action IS NULL;
CREATE INDEX idx_teacher_queue_sla          ON teacher_queue(sla_deadline) WHERE action IS NULL;
CREATE INDEX idx_submissions_status         ON submissions(status);
CREATE INDEX idx_submissions_student_name   ON submissions(student_name);
CREATE INDEX idx_submissions_problem_id     ON submissions(problem_id);
CREATE INDEX idx_problems_soft_deleted      ON problems(soft_deleted) WHERE soft_deleted = FALSE;
CREATE INDEX idx_feedback_log_logged_at     ON feedback_log(logged_at);
```

---

## 데이터 흐름 요약

```
submissions (text | image)
  → [OCR: image → text]   input_type='image' 시만 실행
  → grading_results (1:1)  ai_score + ai_feedback
  → teacher_queue    (1:1)  검토 대기
  → feedback_log     (1:1)  교사 액션 완료 후 생성
problems → submissions (1:N)
```
