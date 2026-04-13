# Argus 진행 현황

최종 업데이트: 2026-04-13
기준: 현재 `main` 작업 트리 코드 상태

## 현재 시스템 상태

- FastAPI 백엔드와 React 프론트엔드가 분리된 구조로 동작
- 학생 제출은 텍스트/이미지(OCR) 모두 지원
- 채점은 결정적 정오 판정 기반으로 즉시 점수 산출
- 피드백 생성과 할루시네이션 검증은 `jobs` 테이블 기반 durable worker로 비동기 처리
- 검증 결과 고신뢰도(`trust_level=high`)는 자동 승인 가능
- 저신뢰도 또는 미승인 케이스는 교사 검토 큐에서 `approve/modify/reject` 처리

## 핵심 구현 포인트

- 백엔드 엔트리: `backend/main.py`
- 채점 파이프라인: `backend/services/pipeline.py`
- durable job worker: `backend/services/job_queue.py`
- 피드백 생성: `backend/services/feedback_generation.py`
- 할루시네이션 배치 검증: `backend/services/hallucination_batch.py`
- 학생/교사 API: `backend/routers/*.py`
- 프론트 라우팅: `frontend/src/main.tsx`

## 데이터베이스

최신 구조 반영됨:
- `problems`, `submissions`, `grading_results`, `teacher_queue`, `feedback_log`
- `jobs` (background queue)
- `student_groups`, `group_members`, `homeworks`, `homework_problems`

최근 마이그레이션:
- `0007_jobs_feedback_status.py`
- `0008_add_feedback_completed_at.py`
- `0009_add_school_level_to_problems.py` (`c5e995d403f6`)

## 문서 정합성 상태

2026-04-13 기준으로 아래 문서를 현재 구조에 맞게 갱신:
- `README.md`
- `docs/api.md`
- `docs/schema.md`
- `PROGRESS.md` (본 문서)

## 남은 문서 정비 후보

- `docs/frontend.md`: 실제 UI 구성/탭 상태와 상세 동기화
- `docs/deployment.md`: 현재 운영값/필수 env 최소셋 재정리
- `docs/decisions.md`: 최근 파이프라인 결정 반영 여부 점검
