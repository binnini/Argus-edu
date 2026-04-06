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
    reference_solution TEXT NOT NULL,               -- 단계별 참조 풀이 (HHEM 비교 기준)
    rubric          JSONB NOT NULL,                  -- 채점 루브릭 (아래 형식 참조)
    domain          VARCHAR(50) DEFAULT '수학2',
    difficulty      SMALLINT CHECK (difficulty BETWEEN 1 AND 5),
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
    student_answer  TEXT NOT NULL,                   -- 학생 제출 답변
    submitted_at    TIMESTAMPTZ DEFAULT NOW(),
    status          VARCHAR(20) DEFAULT 'pending'    -- pending | graded | approved | rejected
);
```

### grading_results — AI 채점 결과

```sql
CREATE TABLE grading_results (
    id                  SERIAL PRIMARY KEY,
    submission_id       INTEGER REFERENCES submissions(id) UNIQUE NOT NULL,
    ai_score            SMALLINT NOT NULL,            -- AI 채점 점수
    ai_explanation      TEXT NOT NULL,                -- AI 생성 풀이 설명 (교사 승인 전 비공개)
    sbert_similarity    FLOAT NOT NULL,               -- SBERT 유사도 (0~1)
    hhem_score          FLOAT NOT NULL,               -- HHEM 팩추얼 일관성 (0~1)
    inconsistency_rate  FLOAT NOT NULL,               -- 멀티샘플링 불일치율 (0~1)
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
                                                     -- score_only: High 신뢰도 (풀이만 검토)
                                                     -- full_review: Low 신뢰도 (채점+풀이 검토)
    sla_deadline    TIMESTAMPTZ NOT NULL,             -- SLA 마감 시각
    action          VARCHAR(10),                      -- NULL | 'approve' | 'modify' | 'reject'
    teacher_score   SMALLINT,                         -- 수정 시 교사 확정 점수
    teacher_explanation TEXT,                         -- 수정 시 교사 작성 풀이
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
CREATE INDEX idx_feedback_log_logged_at     ON feedback_log(logged_at);
```

---

## 데이터 흐름 요약

```
submissions → grading_results (1:1)
           → teacher_queue    (1:1)
           → feedback_log     (1:1, 교사 액션 완료 후 생성)
problems   → submissions      (1:N)
```
