# Argus — 전체 구현 TODO

> 병렬 가능 항목은 `[P]` 표시. 순차 필수 항목은 표시 없음.

---

## Phase 0: 환경 세팅 (Day 1 전반)

인프라와 로컬 개발환경을 준비한다. 이후 모든 Phase의 전제조건.

- [ ] GitHub 저장소 생성 및 초기 커밋 (CLAUDE.md, docs/, TODO.md)
- [ ] 로컬 Python 가상환경 + `requirements.txt` 초안 작성
  - FastAPI, SQLAlchemy, asyncpg, anthropic, sentence-transformers, transformers
- [ ] `.env.example` 작성 (모든 환경변수 목록)
- [ ] PostgreSQL 로컬 DB 생성 (`argus_dev`)
- [ ] AWS EC2 t3.medium 인스턴스 생성
  - Ubuntu 22.04 LTS
  - 보안 그룹: 22(SSH), 80(HTTP), 443(HTTPS) 오픈
- [ ] EC2 Elastic IP 연결
- [ ] 도메인 DNS A 레코드 → Elastic IP 연결

---

## Phase 1: 데이터 기반 (Day 1 후반 ~ Day 2 전반)

**인터페이스 고정 단계. 이후 모든 Phase가 여기에 의존.**

### 1-1. 문제 데이터셋 작성
- [x] `data/problems/math2_differentiation.json` — 미분 문제 6개 작성
- [x] `data/problems/math2_integration.json` — 적분 문제 4개 작성
- [x] `data/problems/stats_probability.json` — 확률과 통계 문제 5개 작성
- [x] `data/test_answers/sample_submissions.json` — 문제당 정답/부분정답/오답 샘플
- [x] 전체 문제 수동 검수 체크리스트 완료 (docs/dataset.md 기준)

### 1-2. DB 모델 + 마이그레이션
- [x] `backend/models/` — SQLAlchemy ORM 모델 작성 (docs/schema.md 기준)
  - `Problem`, `Submission`, `GradingResult`, `TeacherQueue`, `FeedbackLog`
- [x] Alembic 초기화 + 첫 마이그레이션 파일 생성
- [ ] 로컬 DB에 마이그레이션 적용 및 검증
  > AWS/EC2/DB 마이그레이션 실행은 스킵 (코드만 작성)
- [x] `scripts/seed.py` — `data/problems/` JSON → DB 삽입 스크립트

### 1-3. Pydantic 스키마 + 설정
- [x] `backend/schemas/` — 모든 요청/응답 스키마 작성 (docs/api.md 기준)
- [x] `backend/config.py` — 환경변수 로딩 (`GRADING_MODEL`, `TRUST_THRESHOLD` 등)
- [x] `backend/db.py` — async 세션 + 의존성 주입 설정

---

## Phase 2: 핵심 서비스 레이어 (Day 2 후반 ~ Day 3)

**1-2, 1-3 완료 후 시작. grading/explanation/frontend는 병렬 가능.**

### 2-1. 채점 서비스 `[P]`
- [x] `backend/services/grading.py`
  - Claude API 채점 프롬프트 구현 (docs/prompts.md 기준)
  - 프롬프트 캐싱 (`cache_control` 블록) 적용
  - SBERT 유사도 계산 (reference_solution 비교)
  - JSON 구조화 출력 파싱 + 유효성 검증
  - 타임아웃 30초 + 실패 시 재시도 큐 적재
- [ ] 샘플 10개로 채점 결과 수동 검증
  > API 키 없이 실행 불가. Phase 4 API 연결 후 통합 검증 예정

### 2-2. 풀이 설명 서비스 `[P]`
- [x] `backend/services/explanation.py`
  - 멀티 샘플링 3회 구현 (temperature=0.7)
  - SBERT 기반 단계별 불일치율 계산
  - JSON 구조화 출력 파싱
- [ ] 샘플 5개로 불일치 탐지 수동 검증
  > API 키 없이 실행 불가. Phase 4 API 연결 후 통합 검증 예정

### 2-3. 프론트엔드 scaffold `[P]`
- [x] Vite + React + TypeScript 프로젝트 초기화
  > vite create가 기존 frontend/ 디렉토리로 취소됨 → 파일 직접 작성
- [x] React Router 설정 (`/student`, `/teacher`)
- [x] `frontend/src/api/` — API 클라이언트 함수 작성 (docs/api.md 기준)
- [x] `StudentSubmit.tsx` — 문제 목록 + 답변 입력 폼 UI
- [x] `TeacherDashboard.tsx` — 검토 큐 목록 UI (mock 데이터)

---

## Phase 3: 할루시네이션 탐지 + 신뢰도 게이트 (Day 3)

**2-1, 2-2 완료 후 시작.**

- [ ] `backend/main.py` — lifespan 이벤트에서 HHEM + SBERT 1회 로드
- [ ] `backend/services/hallucination.py`
  - HHEM-2.1-Open 팩추얼 일관성 스코어 계산
  - app.state에서 모델 참조 (요청마다 로드 금지)
- [ ] `backend/services/trust_gate.py`
  - 종합 신뢰도 계산: `0.6 * hhem_score + 0.4 * (1 - inconsistency_rate)`
  - 큐 라우팅: `high` → `score_only` / `low` → `full_review`
  - SLA 마감 시각 계산 (High: 12h, Low: 24h)
- [ ] HHEM + SBERT 동시 로드 시 메모리 사용량 측정
  - 2GB 초과 시 → Hugging Face Inference API 전환 검토

---

## Phase 4: API 라우터 연결 (Day 4 전반)

**Phase 2, 3 전체 완료 후 시작.**

- [ ] `backend/routers/submissions.py`
  - `POST /api/v1/submissions` — 제출 + 비동기 채점 파이프라인 시작
  - `GET /api/v1/submissions/{id}` — 폴링 (풀이 설명 노출 정책 적용)
  - `GET /api/v1/problems`, `GET /api/v1/problems/{id}`
- [ ] `backend/routers/teacher.py`
  - `GET /api/v1/teacher/queue` — 미처리 큐 목록
  - `POST /api/v1/teacher/queue/{id}/action` — 승인/수정/거부
  - `X-Teacher-Password` 헤더 인증 미들웨어
- [ ] `backend/routers/feedback.py`
  - `GET /api/v1/teacher/feedback/summary` — delta 집계
- [ ] `backend/main.py` — 라우터 등록 + CORS 설정

---

## Phase 5: 프론트엔드 완성 (Day 4 후반)

**Phase 4 완료 후 시작 (실제 API 연동).**

- [ ] `StudentSubmit.tsx` — mock 데이터 → 실제 API 연동
  - 제출 후 폴링 (2초 간격, 최대 60초)
  - `teacher_approved === false` 시 "검토 중" 메시지만 노출
  - `teacher_approved === true` 시 풀이 설명 노출
- [ ] `TeacherDashboard.tsx` — 실제 API 연동
  - 신뢰도 배지 (`TrustBadge.tsx`) — High/Low 시각화
  - 승인/수정/거부 폼 (3가지 액션만, 묵시적 승인 UI 없음)
  - SLA 마감까지 남은 시간 표시
- [ ] `ReviewCard.tsx` — 수정 액션 시 점수/풀이 편집 폼
- [ ] React 빌드 산출물 (`dist/`) 생성 확인

---

## Phase 6: 통합 테스트 (Day 5)

**Phase 4, 5 완료 후 시작.**

- [ ] 정상 흐름 E2E — 정답 제출 → 채점 → 교사 승인 → 학생 풀이 수령
- [ ] Low 신뢰도 케이스 — 오답 주입 → 전체 큐 라우팅 → 교사 수정 → 전달
- [ ] 풀이 설명 차단 확인 — 승인 전 `/submissions/{id}` 응답에 설명 없음
- [ ] 할루시네이션 의도 주입 — 잘못된 수식 포함 답변 → Low 신뢰도 탐지 확인
- [ ] Claude API 타임아웃 시뮬레이션 → 재시도 큐 동작 확인
- [ ] SLA 초과 케이스 — deadline 임박 항목 우선 노출 확인
- [ ] 교사 비밀번호 오류 → 401 반환 확인
- [ ] HHEM 메모리 사용량 모니터링 (정상 범위 확인)

---

## Phase 7: 배포 (Day 6)

**Phase 6 완료 후 시작.**

- [ ] EC2에 의존성 설치 (Python, Node, PostgreSQL, Nginx)
- [ ] EC2 PostgreSQL DB 생성 + 마이그레이션 적용
- [ ] `.env` 프로덕션 설정 (API 키, DB URL, 교사 비밀번호)
- [ ] `scripts/seed.py` 실행 — 문제 데이터 EC2 DB 삽입
- [ ] `systemd` 서비스 파일 작성 + 등록 (`argus-backend.service`)
  - 서버 재시작 시 FastAPI 자동 복구
- [ ] React 빌드 산출물 → EC2 `/var/www/argus/` 복사
- [ ] Nginx 설정
  - `/api/*` → FastAPI (포트 8000)
  - `/*` → React 정적 파일
- [ ] Let's Encrypt HTTPS 인증서 발급 (`certbot`)
- [ ] HTTPS 최종 접속 확인 (브라우저)
- [ ] systemd 재시작 → 서비스 자동 복구 확인

---

## Phase 8: 파일럿 (Day 7)

**Phase 7 완료 후 시작.**

- [ ] 교사 파일럿 사용자 초대 + 사용 매뉴얼 전달
- [ ] 학생 역할로 전체 문제 제출 시나리오 실행
- [ ] 교사 역할로 검토 큐 전체 처리 시나리오 실행
- [ ] `/api/v1/teacher/feedback/summary` — AI-교사 일치율 확인 (목표 ≥ 70%)
- [ ] 할루시네이션 탐지 정밀도 확인 (목표 ≥ 80%)
- [ ] 교사 피드백 수집 (검토 소요 시간, UI 불편 사항)
- [ ] 오류 로그 확인 + 핫픽스

---

## 병렬 실행 요약

```
Phase 0 → Phase 1 (순차)
               ↓
Phase 1 완료 후:
  ┌── Phase 2-1 (grading)      ┐
  ├── Phase 2-2 (explanation)  ┤ 병렬 가능
  └── Phase 2-3 (frontend)     ┘
               ↓
Phase 3 → Phase 4 → Phase 5 → Phase 6 → Phase 7 → Phase 8 (순차)
```
