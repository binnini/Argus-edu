# DB 스키마 (현재 구현 기준)

DB: PostgreSQL
ORM: SQLAlchemy Async
Migration: Alembic (`backend/alembic/versions`)

## 핵심 테이블

### `problems`

문제 원본 테이블.

주요 컬럼:
- `id` (PK)
- `title` (varchar(200), not null)
- `content` (text, not null)
- `answer` (varchar(100), not null)
- `reference_solution` (text, not null)
- `rubric` (jsonb, not null)
- `domain` (varchar(50), default `수학2`)
- `school_level` (varchar(50), nullable)
- `difficulty` (smallint, nullable)
- `source` (varchar(100), nullable)
- `soft_deleted` (boolean, default false)
- `created_at` (timestamptz)

### `submissions`

학생 제출 테이블.

주요 컬럼:
- `id` (PK)
- `problem_id` (FK -> `problems.id`)
- `student_answer` (text, not null)
- `input_type` (varchar(10), default `text`)
- `ocr_raw_text` (text, nullable)
- `image_path` (varchar(500), nullable)
- `status` (varchar(20), default `pending`)
- `student_name` (varchar(50), default `""`)
- `student_id` (varchar(20), nullable)
- `submitted_at` (timestamptz)

상태값:
- `pending | graded | approved | rejected | error`

### `grading_results`

AI 채점/피드백/검증 결과 테이블.

주요 컬럼:
- `id` (PK)
- `submission_id` (FK, unique)
- `ai_score` (smallint, not null)
- `ai_feedback` (text, not null, JSON 문자열)
- `grading_steps` (text, nullable, JSON 문자열)
- `feedback_status` (varchar(10), default `pending`)
- `feedback_completed_at` (timestamptz, nullable)
- `solution_status` (varchar(40), nullable)
- `answer_verdict` (varchar(20), nullable)
- `sbert_similarity` (float, not null)
- `trust_score` (float, not null)
- `trust_level` (varchar(10), not null)
- `graded_at` (timestamptz)
- `hallucination_status` (varchar(10), default `pending`)
- `hallucination_score` (float, nullable)
- `hallucination_issues` (text, nullable, JSON 문자열)
- `hallucination_checked_at` (timestamptz, nullable)

상태값:
- `feedback_status`: `pending | running | done | failed`
- `hallucination_status`: `pending | running | done | failed`
- `trust_level`: `high | low`

### `teacher_queue`

교사 검토 큐.

주요 컬럼:
- `id` (PK)
- `submission_id` (FK, unique)
- `queue_type` (varchar(20), not null)
- `sla_deadline` (timestamptz, not null)
- `action` (varchar(10), nullable)
- `teacher_score` (smallint, nullable)
- `teacher_feedback` (text, nullable)
- `queued_at` (timestamptz)
- `reviewed_at` (timestamptz, nullable)

상태값:
- `queue_type`: `score_only | full_review`
- `action`: `approve | modify | reject | null`

### `feedback_log`

교사 리뷰 결과 로그.

주요 컬럼:
- `id` (PK)
- `submission_id` (FK)
- `ai_score` (smallint)
- `teacher_score` (smallint)
- `score_delta` (generated: `teacher_score - ai_score`)
- `action` (varchar(10))
- `trust_score` (float)
- `trust_level` (varchar(10))
- `logged_at` (timestamptz)

### `jobs`

durable background job 큐.

주요 컬럼:
- `id` (PK)
- `job_type` (varchar(30))
- `priority` (int, default 100)
- `submission_id` (int, index)
- `status` (varchar(10), default `pending`)
- `attempts` (int, default 0)
- `max_attempts` (int, default 3)
- `run_after` (timestamptz)
- `locked_at` (timestamptz, nullable)
- `locked_by` (varchar(80), nullable)
- `last_error` (text, nullable)
- `payload` (text, nullable)
- `created_at`, `updated_at` (timestamptz)

상태값:
- `job_type`: `feedback | hallucination`
- `status`: `pending | running | done | failed`

## 그룹/숙제 테이블

### `student_groups`
- `id`, `name`, `created_at`

### `group_members`
- `id`, `group_id`(FK), `student_id`, `student_name`

### `homeworks`
- `id`, `title`, `group_id`(FK, nullable), `due_date`, `created_at`

### `homework_problems`
- `id`, `homework_id`(FK), `problem_id`(FK)

## 테이블 관계 요약

- `problems` 1:N `submissions`
- `submissions` 1:1 `grading_results`
- `submissions` 1:1 `teacher_queue`
- `submissions` 1:N `feedback_log`
- `student_groups` 1:N `group_members`
- `student_groups` 1:N `homeworks`
- `homeworks` 1:N `homework_problems`

## 최신 마이그레이션

- `0007_jobs_feedback_status.py`: `jobs`, `feedback_status`, `solution_status`, `answer_verdict`
- `0008_add_feedback_completed_at.py`: `feedback_completed_at`
- `0009_add_school_level_to_problems.py` (revision id: `c5e995d403f6`): `problems.school_level`
