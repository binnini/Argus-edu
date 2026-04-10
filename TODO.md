# Argus — 전체 구현 TODO

> 병렬 가능 항목은 `[P]` 표시. 순차 필수 항목은 표시 없음.  
> ✅ 완료 · 🔄 진행 중 · ⬜ 미시작

---

## Phase 0~6: 완료 (기본 파이프라인)

| Phase | 내용 | 상태 |
|---|---|---|
| Phase 0 | 로컬 환경 세팅, DB, 마이그레이션, seed | ✅ |
| Phase 1 | 데이터셋, ORM 모델, Pydantic 스키마 | ✅ |
| Phase 2 | grading/explanation 서비스, 프론트엔드 scaffold | ✅ |
| Phase 3 | HHEM 탐지, 신뢰도 게이트 | ✅ |
| Phase 4 | API 라우터 11개 (submissions/teacher/feedback) | ✅ |
| Phase 5 | 프론트엔드 실제 API 연동, 폴링, 교사 흐름 | ✅ |
| Phase 6 | 통합 테스트 10/10 통과 | ✅ |

---

## Phase 7: 시스템 재설계 (설계 변경 반영)

**문서 개정 완료. 코드 변경 단계.**

### 7-1. AI-HUB 데이터 변환

- [x] AI-HUB 데이터 다운로드 확인 (고등학교_공통수학 TL_1/2/3)
- [x] `scripts/convert_aihub.py` 작성
  - TL_1(문제) + TL_2(모범답안) 병합 → Argus problems 스키마
  - `question_type1 == "서술"` 필터링
  - `answer_text` → `reference_solution` 단계 구조화 (LLM 보조)
  - rubric 자동 생성 (단계 수 기반)
- [x] `scripts/seed.py` 업데이트 — AI-HUB 변환 데이터 삽입
- [x] 기존 자체 생성 데이터 15개 DB에서 제거
- [x] `data/ocr_samples/` 구성 — TL_3 손글씨 이미지 + labels.json

### 7-2. DB 마이그레이션

- [x] `backend/alembic/versions/0002_redesign.py` 작성
  - `submissions` 테이블: `input_type`, `ocr_raw_text`, `image_path` 컬럼 추가
  - `grading_results` 테이블: `ai_explanation` → `ai_feedback` 컬럼 rename
  - `teacher_queue` 테이블: `teacher_explanation` → `teacher_feedback` 컬럼 rename
  - `problems` 테이블: `source` 컬럼 추가
- [x] 로컬 DB에 마이그레이션 적용 (`alembic upgrade head`)

### 7-3. OCR 서비스 `[P]` ✅

- [x] `backend/services/ocr.py` 작성
  - `OCR_MODEL` 환경변수로 엔진 선택 (`pix2tex` | `mathpix` | `got_ocr`)
  - pix2tex 로컬 실행 구현
  - Mathpix API 연동 구현 (fallback)
  - GOT-OCR 2.0 파인튜닝 모델 지원 (`GOT_OCR_MODEL_PATH` 환경변수)
  - OCR 실패 시 에러 반환 (무시하지 말 것)
- [x] `requirements.txt` 업데이트 — pix2tex, python-multipart, httpx 추가
- [x] `POST /api/v1/submissions/image` — `multipart/form-data` 이미지 업로드 엔드포인트 추가

### 7-4. 개인화 피드백 서비스 `[P]` ✅

- [x] `backend/services/feedback.py` 작성 (기존 `explanation.py` 교체)
  - 프롬프트: 학생 오류 분석 + 교정 방향 (docs/prompts.md v2.0 기준)
  - 출력 스키마: `student_mistakes` + `correct_approach` + `key_concept`
  - 멀티 샘플링 3회 + 불일치율 계산
  - Ollama/Anthropic 양쪽 지원
- [x] `backend/services/hallucination.py` 업데이트
  - premise: `reference_solution + grading_result`
  - hypothesis: `ai_feedback.correct_approach`
- [x] `backend/routers/submissions.py` 업데이트
  - `explanation_service` → `feedback_service`
  - 응답 필드명: `explanation` → `feedback`
- [x] `backend/schemas/` 업데이트 — feedback 구조 반영

### 7-5. 프론트엔드 개편 `[P]` ✅

- [x] `frontend/src/components/AnswerInput.tsx` 신규
  - 텍스트 입력 탭 / 이미지 업로드 탭 전환 UI
  - 이미지 업로드 시 `multipart/form-data` 전송
- [x] `frontend/src/components/FeedbackPanel.tsx` 신규
  - `student_mistakes` 목록 렌더링
  - `correct_approach` 단계별 렌더링
  - `key_concept` 요약 표시
  - `teacher_approved === true` 일 때만 렌더링 (절대 제약)
- [x] `frontend/src/pages/StudentSubmit.tsx` 업데이트
  - `AnswerInput` 컴포넌트 사용
  - `FeedbackPanel` 컴포넌트 연결
- [x] `frontend/src/api/submissions.ts` 업데이트
  - `submitAnswerText()` / `submitAnswerImage()` 분리
- [x] `npm run build` 빌드 성공 확인

### 7-6. GOT-OCR 2.0 파인튜닝 (WSL2 RTX 5070Ti)

> 참고: ADR-017 (데이터셋 구성), ADR-018 (파인튜닝 전략)

**데이터 구성 (총 ~279k 이미지)**
- [x] TS_3 zip 8개 + labels.json 160,015개
- [x] 038 손글씨 zip 9개 (초4~6, 중1~3, 고1~3) 119,233개
- [x] `prepare_dataset.py` — train ~251k / test ~28k split 완료

**학습 환경**
- [x] flash-attn 미지원 (RTX 5070Ti, CUDA 13 / Blackwell sm_120) → PyTorch SDPA 사용
- [x] `batch=2, grad_accum=16` (effective 32), `MAX_LENGTH=640`

**파인튜닝**
- [x] v1 실패: 학습 포맷이 `chat()` 추론 포맷과 불일치 → degenerate 출력
- [x] v2: `train.py` 재작성 — `chat()` 대화 포맷 정렬, `OcrTrainer` 커스텀 (ADR-018)
- 🔄 **v2 학습 진행 중** (`got_ocr_finetuned_v2/`, 3 epoch, ~44시간)
  - checkpoint-4000 (epoch 0.52) 검증: 5샘플 완전 일치 2건, 수식 구조 정확 3건

**남은 작업**
- [ ] Step 4: `evaluate_ocr.py` — base vs fine-tuned CER 비교 (목표 < 5%)
- [ ] Step 5: WSL에서 `merge_lora.py` 실행 (파인튜닝 완료 후)
  ```bash
  LORA_DIR=ocr_training/output/got_ocr_finetuned_v2/checkpoint-XXXX \
      python ocr_training/scripts/merge_lora.py
  ```
- [x] Mac에서 `merge_lora.py` 실행 (checkpoint-8000.zip 기반, 검증용)
- [x] `_GotOcrEngine` 수정 — `model.chat()` 방식 + `modeling_GOT.py` device-agnostic 패치
- [ ] WSL `.env` 전환
  ```env
  OCR_MODEL=got_ocr
  GOT_OCR_MODEL_PATH=/home/yebin/projects/Argus-edu/ocr_training/output/got_ocr_merged
  ```
- [ ] OCR E2E 검증 — 손글씨 이미지 업로드 → 채점 파이프라인 통과 확인

### 7-7. UX 재설계 (ADR-021) `[P]`

> 참고: ADR-021, docs/frontend.md, docs/api.md, docs/schema.md

#### 7-7-1. 백엔드

- [ ] `backend/alembic/versions/0003_add_student_info.py` 작성
  - `submissions`: `student_name VARCHAR(50) NOT NULL`, `student_id VARCHAR(20)` 추가
  - `problems`: `soft_deleted BOOLEAN DEFAULT FALSE` 추가
  - 인덱스 추가 (student_name, problem_id, soft_deleted)
- [ ] `alembic upgrade head` 로컬 적용
- [ ] `backend/routers/submissions.py` 업데이트
  - `SubmissionRequest`: `student_name`, `student_id` 필드 추가
  - `POST /api/v1/submissions/image`: multipart에 `student_name`, `student_id` 파라미터 추가
  - `input_type`: `'canvas'` 값 추가 허용
- [ ] `backend/routers/teacher.py` 업데이트
  - `GET /api/v1/teacher/queue`: `trust_level` 쿼리 필터 추가, 응답에 `student_name`/`student_id` 포함
  - `GET /api/v1/teacher/submissions` 신규 (페이지네이션, 필터)
  - `GET /api/v1/teacher/problems/{id}/submissions` 신규
- [ ] `backend/routers/problems.py` (교사 CRUD) 신규
  - `POST /api/v1/teacher/problems`
  - `GET /api/v1/teacher/problems`
  - `PUT /api/v1/teacher/problems/{id}`
  - `DELETE /api/v1/teacher/problems/{id}` (soft delete 로직)
- [ ] `backend/schemas/` 업데이트 — 신규 엔드포인트 스키마 반영

#### 7-7-2. 프론트엔드 환경 세팅

- [ ] Tailwind CSS v3 설치 및 설정 (`tailwind.config.js`, `globals.css`)
- [ ] shadcn/ui 초기화 (`npx shadcn-ui@latest init`)
  - 필요 컴포넌트 추가: `button`, `card`, `tabs`, `input`, `textarea`, `select`, `dialog`, `badge`, `skeleton`, `toast`
- [ ] Pretendard 폰트 설정 (`@fontsource/pretendard`)
- [ ] KaTeX 설치 (`react-katex`, `katex`)
- [ ] `react-signature-canvas` 설치 (캔버스용)
- [ ] Lucide React 설치

#### 7-7-3. 프론트엔드 학생 화면 `[P]`

- [ ] `StudentInfoForm.tsx` — 이름·학번 입력 (sessionStorage 저장)
- [ ] `AnswerInput.tsx` 확장 — 3탭 구조 (이미지/카메라/캔버스)
  - `capture="environment"` 카메라 탭
  - `CanvasInput.tsx` — react-signature-canvas, CANVAS_ENABLED 플래그
- [ ] `GradingStatus.tsx` — Skeleton 로딩, ScoreBadge, PendingReviewBanner
- [ ] `StudentPage.tsx` — 상태 머신 재작성 (info → problem → answer → polling → done)
- [ ] `FeedbackPanel.tsx` — KaTeX 수식 렌더링 적용

#### 7-7-4. 프론트엔드 교사 화면 `[P]`

- [ ] `PasswordGate.tsx` — shadcn/ui Card + Input + Button
- [ ] `DashboardHeader.tsx` — 탭 외부 헤더 (통계 요약, 로그아웃)
- [ ] `ProblemManager.tsx` — 문제 목록 테이블
- [ ] `ProblemFormDialog.tsx` — 등록·수정 모달 (RubricEditor 포함)
- [ ] `SubmissionOverview.tsx` — 제출 현황 테이블 (필터, 페이지네이션)
- [ ] `SubmissionDetailDialog.tsx` — 제출 상세 모달 (이미지·OCR·채점 결과)
- [ ] `ReviewQueue.tsx` — 검토 큐 (TrustFilter + ReviewCard 재사용)
- [ ] `TeacherPage.tsx` — 탭 3개 통합

#### 7-7-5. API 레이어 `[P]`

- [ ] `frontend/src/api/problems.ts` 신규 — 문제 조회(학생) + CRUD(교사)
- [ ] `frontend/src/api/submissions.ts` 업데이트 — `student_name`/`student_id` 포함
- [ ] `frontend/src/api/teacher.ts` 업데이트 — 현황 조회, trust_level 필터

#### 7-7-6. 빌드 검증

- [ ] `npm run build` 빌드 성공 확인
- [ ] 다크모드 토글 동작 확인
- [ ] 수식 렌더링 확인 (KaTeX)
- [ ] 캔버스 → 이미지 제출 E2E 확인

---

## Phase 8: E2E 재검증

**Phase 7 전체 완료 후 시작.**

- [ ] 기존 통합 테스트(`tests/test_integration.py`) 업데이트
  - `explanation` → `feedback` 필드명 변경
  - 이미지 업로드 테스트 시나리오 추가
  - 개인화 피드백 구조 검증 (student_mistakes, correct_approach, key_concept)
  - `student_name` 필드 포함 제출 시나리오
  - 교사 제출 현황 API 검증
  - 문제 CRUD API 검증
- [ ] AI-HUB 손글씨 이미지로 OCR → 채점 → 피드백 E2E 검증
- [ ] 할루시네이션 탐지 방향 변경 검증 (피드백 정확성)
- [ ] 통합 테스트 전체 통과 확인

---

## Phase 9: 배포 (Mac Mini M4 + Cloudflare Tunnel)

> ADR-019 참고. EC2 방안 철회 — Mac Mini M4 (24GB) 로컬 서빙으로 결정.

**Phase 8 완료 후 시작.**

### 9-1. 서버 환경 준비
- [ ] Mac Mini M4에 의존성 확인 (Python 3.11, Node, PostgreSQL, Nginx)
- [ ] PostgreSQL DB 생성 + 마이그레이션 적용 (`alembic upgrade head`)
- [ ] `.env` 프로덕션 설정
  ```env
  ANTHROPIC_API_KEY=...
  DATABASE_URL=postgresql://...
  TEACHER_PASSWORD=...
  OCR_MODEL=got_ocr
  GOT_OCR_MODEL_PATH=/path/to/got_ocr_merged
  GRADING_MODEL=claude-sonnet-4-6
  FEEDBACK_MODEL=claude-sonnet-4-6
  ```
- [ ] `scripts/seed.py` 실행 — AI-HUB 변환 데이터 DB 삽입

### 9-2. 백엔드 서비스
- [ ] `systemd` 서비스 파일 작성 + 등록 (`argus-backend.service`)
  - 워킹 디렉토리, 환경변수 파일 경로, 재시작 정책 설정
- [ ] `uvicorn` 프로덕션 실행 확인 (로컬 8000포트)

### 9-3. 프론트엔드
- [ ] `npm run build` 빌드 산출물 생성
- [ ] Nginx 설정 (`/api/*` → FastAPI 8000, `/*` → React 정적)
- [ ] Nginx 서비스 등록 + 시작

### 9-4. Cloudflare Tunnel
- [ ] Cloudflare 계정 + 도메인 준비
- [ ] `cloudflared` 설치 (`brew install cloudflare/cloudflare/cloudflared`)
- [ ] Tunnel 생성 + 인증 (`cloudflared tunnel create argus`)
- [ ] `config.yml` 작성 — Tunnel → localhost:80(Nginx) 라우팅
- [ ] `cloudflared` launchd 서비스 등록 (Mac 부팅 시 자동 시작)
- [ ] Cloudflare DNS CNAME → Tunnel ID 연결
- [ ] HTTPS 최종 접속 확인 (Cloudflare 자동 TLS)

---

## Phase 10: 파일럿

**Phase 9 완료 후 시작.**

- [ ] 교사 파일럿 사용자 초대 + 사용 매뉴얼 전달
- [ ] 학생 역할로 전체 문제 제출 시나리오 실행
- [ ] 교사 역할로 검토 큐 전체 처리 시나리오 실행
- [ ] `/api/v1/teacher/feedback/summary` — AI-교사 일치율 확인 (목표 ≥ 70%)
- [ ] 피드백 오류 탐지 정밀도 확인 (목표 ≥ 80%)
- [ ] 교사 피드백 수집 (검토 소요 시간, UI 불편 사항)
- [ ] 오류 로그 확인 + 핫픽스

---

## 향후 로드맵 (파일럿 이후)

- [ ] Canvas 직접 그리기 입력 (패드/핸드폰 손글씨)
- [ ] 학생 QA 기능 (RAG 기반)
- [ ] 프롬프트 최적화 (누적 feedback_log 활용)
- [ ] JWT 인증 시스템 (다수 교사 온보딩)
- [ ] 모바일 UI 대응
