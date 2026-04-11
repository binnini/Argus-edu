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

### 7-7. UX 재설계 (ADR-021) `[P]` ✅

> 참고: ADR-021, docs/frontend.md, docs/api.md, docs/schema.md  
> 브랜치: `feat/phase7-ux-redesign`

#### 7-7-1. 백엔드 ✅

- [x] `backend/alembic/versions/0004_add_student_info.py` 작성
  - `submissions`: `student_name VARCHAR(50) NOT NULL`, `student_id VARCHAR(20)` 추가
  - `problems`: `soft_deleted BOOLEAN DEFAULT FALSE` 추가
  - 인덱스 추가 (student_name, problem_id, soft_deleted)
- [ ] `alembic upgrade head` 로컬/프로덕션 DB 적용 (PostgreSQL 연결 시 실행)
- [x] `backend/routers/submissions.py` 업데이트
  - `SubmissionRequest`: `student_name`, `student_id` 필드 추가
  - `POST /api/v1/submissions/image`: multipart에 `student_name`, `student_id` 파라미터 추가
- [x] `backend/routers/teacher.py` 업데이트
  - `GET /api/v1/teacher/queue`: `trust_level` 쿼리 필터, 응답에 `student_name`/`student_id` 포함
  - `GET /api/v1/teacher/submissions` 신규 (페이지네이션, 필터)
  - `GET /api/v1/teacher/problems/{id}/submissions` 신규
- [x] `backend/routers/problems.py` (교사 CRUD) 신규
  - `POST/GET/PUT/DELETE /api/v1/teacher/problems` (soft delete 포함)
- [x] `backend/schemas/` 업데이트 — SubmissionOverviewItem/Response, 문제 CRUD 스키마

#### 7-7-2. 프론트엔드 환경 세팅 ✅

- [x] Tailwind CSS v3 + postcss + autoprefixer 설치 (`tailwind.config.js`, `globals.css`)
- [x] shadcn/ui 수동 구성 (Radix UI + CVA) — button, card, tabs, input, textarea, select, dialog, badge, skeleton
- [x] Pretendard 폰트 (`@fontsource/pretendard/index.css`)
- [x] KaTeX 설치 (`react-katex`, `katex`)
- [x] `react-signature-canvas` 설치 (캔버스용)
- [x] Lucide React 설치

#### 7-7-3. 프론트엔드 학생 화면 ✅

- [x] `StudentInfoForm.tsx` — 이름·학번 입력 (sessionStorage 저장)
- [x] `AnswerInput.tsx` 3탭 — 이미지 업로드 / 카메라(`capture="environment"`) / 캔버스
- [x] `CanvasInput.tsx` — react-signature-canvas, `CANVAS_ENABLED` 플래그로 가역적 제어
- [x] `GradingStatus.tsx` — Skeleton 로딩, 점수 Badge, 교사 검토 대기 배너
- [x] `StudentPage.tsx` — 상태 머신 재작성 (info → problem → answer → submitting → polling → done)
- [x] `FeedbackPanel.tsx` — KaTeX 수식 렌더링 (`react-katex` InlineMath/BlockMath)

#### 7-7-4. 프론트엔드 교사 화면 ✅

- [x] `PasswordGate.tsx` — Tailwind Card + Input + Button
- [x] `DashboardHeader.tsx` — sticky 헤더, 다크모드 토글, 로그아웃
- [x] `ProblemManager.tsx` — 문제 목록 테이블 + 등록/수정/삭제
- [x] `ProblemFormDialog.tsx` — 등록·수정 모달 (RubricEditor 포함)
- [x] `SubmissionOverview.tsx` — 제출 현황 테이블 (필터, 페이지네이션, 상세 다이얼로그)
- [x] `SubmissionDetailDialog.tsx` — 제출 상세 모달
- [x] `ReviewQueue.tsx` — TrustFilter 토글 + ReviewCard 리스트 + 통계 카드
- [x] `ReviewCard.tsx` — Tailwind 리스타일, 피드백 접힘/펼침, 인라인 수정 폼
- [x] `TeacherPage.tsx` — 3탭 통합 (문제 관리 / 풀이 현황 / 검토 큐)

#### 7-7-5. API 레이어 ✅

- [x] `frontend/src/api/problems.ts` 신규 — 문제 조회(학생) + CRUD(교사)
- [x] `frontend/src/api/submissions.ts` — `student_name`/`student_id` 포함
- [x] `frontend/src/api/teacher.ts` — 현황 조회, trust_level 필터

#### 7-7-6. 빌드 검증

- [x] `npm run build` 빌드 성공 (614KB JS / 49KB CSS)
- [ ] 다크모드 토글 런타임 동작 확인
- [ ] KaTeX 수식 렌더링 브라우저 확인
- [ ] 캔버스 → 이미지 제출 E2E 확인 (백엔드 연동 후)

---

### 7-8. UX 2차 개선 (ADR-022/023/024) ✅

> 브랜치: `feat/phase7-ux-redesign`

#### 7-8-1. 점수 → 정답/오답 표시 (ADR-022-1) ✅

- [x] `GradingStatus.tsx` — `score > 0` → "정답" Badge, `score === 0` → "오답" Badge
- [x] `SubmissionOverview.tsx` — 헤더 "최종점수" → "결과", 정답/오답 Badge
- [x] `StudentPage.tsx` — 이력 목록 정답/오답 Badge

#### 7-8-2. ReviewCard 전면 개편 (ADR-022-2) ✅

- [x] AI 피드백 항상 표시 (토글 제거)
- [x] 문제 본문·정답 인라인 표시 (indigo 카드)
- [x] 이미지 제출 인라인 표시 + OCR 원문 2컬럼 나란히
- [x] SLA 3시간 미만 시 rose 색상 경고
- [x] 백엔드 `teacher_queue` 조회 시 `problem_content`, `problem_answer`, `ocr_raw_text` 포함
- [x] `backend/schemas/teacher.py` + `backend/routers/teacher.py` 필드 추가

#### 7-8-3. 검색 필터 (ADR-022-3) ✅

- [x] `ReviewQueue.tsx` — 학생명/문제 텍스트 검색, 문제별 필터, 정렬
- [x] `ProblemManager.tsx` — 텍스트 검색, 학교급 필터, 영역 필터, 난이도 필터, 정렬
- [x] `SubmissionDetailDialog.tsx` — 이미지 인라인 표시 추가

#### 7-8-4. 캔버스 지우개 + SVG 커서 (ADR-022-4) ✅

- [x] `CanvasInput.tsx` — `DrawMode = "pen" | "eraser"` 전환
- [x] 지우개: 흰색 펜 (effectiveWidth = penWidth × 3) 구현
- [x] SVG 동적 커서 (모드·굵기 반영)
- [x] 펜 굵기 4단계 선택 (2, 4, 6, 8)

#### 7-8-5. 학생 풀이 상세 + 답안 재제출 (ADR-023) ✅

- [x] `GET /api/v1/submissions/{id}` — `problem_title`, `problem_content` 추가 반환
- [x] `GET /api/v1/submissions?student_id=` — `image_path`, `student_answer` 추가 반환
- [x] `PUT /api/v1/submissions/{id}` — 답안 수정 재제출 (pending/graded 한정)
- [x] `StudentPage.tsx` — stage "detail" (상세 보기) + stage "editing" (수정) 추가
- [x] `frontend/src/api/submissions.ts` — `updateSubmission()` 추가

#### 7-8-6. 숙제/그룹 시스템 (ADR-024) ✅

- [x] `backend/models/group.py` — `StudentGroup`, `GroupMember` 모델
- [x] `backend/models/homework.py` — `Homework`, `HomeworkProblem` 모델
- [x] `backend/schemas/groups.py` + `backend/schemas/homeworks.py`
- [x] `backend/routers/groups.py` — 교사 그룹/숙제 CRUD API 8개
- [x] `GET /api/v1/submissions/homework?student_id=` — 학생 숙제 현황 API
- [x] `backend/main.py` — groups 라우터 등록 + `Base.metadata.create_all` 자동 마이그레이션
- [x] `GroupManager.tsx` — 그룹 생성/삭제, 멤버 추가/제거 UI
- [x] `HomeworkManager.tsx` — 숙제 생성(문제 체크박스 선택)/삭제 UI
- [x] `TeacherPage.tsx` — "그룹 관리", "숙제 관리" 탭 추가
- [x] `frontend/src/api/teacher.ts` — 그룹/숙제 API 함수 추가
- [x] `frontend/src/api/submissions.ts` — `getStudentHomework()` 추가

#### 7-8-7. 학생 UI 2단 레이아웃 (ADR-024) ✅

- [x] `StudentPage.tsx` 2단 레이아웃 전환 (flex 사이드바 + 메인)
- [x] 왼쪽 사이드바: 숙제 현황 (진행 바 + 마감일) + 풀이 현황 최근 5개
- [x] 문제 선택 "숙제" 탭 (할당 문제, 제출완료 표시) + "전체 문제" 탭
- [x] 모바일 대응: 사이드바 `hidden md:flex`
- [x] `npm run build` 빌드 성공

---

## Phase 8: E2E 재검증

**Phase 7 전체 완료 후 시작.**

- [x] 기존 통합 테스트(`tests/test_integration.py`) 업데이트
  - `explanation` → `feedback` 필드명 변경
  - 이미지 업로드 테스트 시나리오 추가 (student_name/student_id 포함)
  - 개인화 피드백 구조 검증 (student_mistakes, correct_approach, key_concept)
  - `student_name` 필드 포함 제출 시나리오
  - 교사 제출 현황 API 검증 (필터 포함)
  - 문제 CRUD API 검증 (등록·수정·삭제)
  - 학생 이력 조회 API 검증 (`GET /api/v1/submissions?student_id=...`)
  - 교사 큐 trust_level 필터 검증
  - 큐 항목 input_type/image_path 필드 검증
  - 문제 목록 페이지네이션 검증
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
- [ ] `.env` 프로덕션 설정 (docs/deployment.md 참조)
- [ ] `scripts/seed.py` 실행 — AI-HUB 변환 데이터 DB 삽입

### 9-2. 배포 파일 준비 ✅
- [x] `deploy/setup.sh` — 자동 배포 스크립트 작성
- [x] `deploy/nginx.conf` — `/api/*` → FastAPI, `/data/*` → 정적, `/*` → React SPA
- [x] `deploy/com.argus.backend.plist` — 백엔드 launchd 서비스 (Mac 부팅 자동 시작)
- [x] `deploy/com.cloudflare.cloudflared.plist` — Tunnel launchd 서비스
- [x] `deploy/cloudflare-tunnel.yml` — Cloudflare Tunnel 라우팅 설정 템플릿
- [x] `frontend/.env.production` — 프로덕션 빌드 `VITE_API_BASE=/api/v1`
- [x] `backend/main.py` — `ALLOWED_ORIGINS` 환경변수로 CORS 설정
- [x] `docs/deployment.md` — 전체 배포 가이드 작성
- [x] 이미지 URL 환경변수화 (ReviewCard `VITE_API_BASE` 기반)

### 9-3. Mac Mini 현장 실행
- [ ] `bash deploy/setup.sh` 실행
- [ ] `uvicorn` 프로덕션 동작 확인 (`curl http://localhost:8000/health`)
- [ ] Nginx 서빙 확인 (`curl http://localhost/`)

### 9-4. Cloudflare Tunnel
- [ ] `cloudflared tunnel create argus` 실행
- [ ] `deploy/cloudflare-tunnel.yml` — `<TUNNEL_ID>` + 도메인 교체
- [ ] `cloudflared tunnel route dns argus argus.yourdomain.com`
- [ ] launchd 서비스 등록 + HTTPS 최종 접속 확인

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

- [x] Canvas 직접 그리기 입력 — `CanvasInput.tsx` + `CANVAS_ENABLED` 플래그로 구현 완료 (Phase 7-7)
- [x] 숙제/그룹 시스템 — 교사 그룹 관리, 숙제 할당, 학생 숙제 현황 (Phase 7-8)
- [ ] 알림 기능 — SLA 임박 시 교사 이메일/슬랙 알림
- [ ] 학생 QA 기능 (RAG 기반)
- [ ] 프롬프트 최적화 (누적 feedback_log 활용)
- [ ] JWT 인증 시스템 (다수 교사 온보딩)
- [ ] 모바일 UI 최적화 (현재 기본 반응형 지원, 사이드바 md 이하 숨김)
