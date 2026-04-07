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

### 7-6. GOT-OCR 2.0 파인튜닝 (별도 에이전트 — WSL2 RTX 5070Ti)

> WSL2에 AI-HUB 데이터 및 labels.json 이미 존재 (`~/workSpace/Argus` 동일 경로).  
> 에이전트 프롬프트: `docs/ocr_agent_prompt.md`

**데이터 구성 (총 ~279k 이미지)**
- [x] TS_3 zip 8개 + labels.json 160,015개 (기존)
- [x] 038 손글씨 zip 9개 (손초4~6, 손중1~3, 손고1~3) — 119,233개 추가 활용 결정

**전처리 추가 작업 (038 데이터)**
- [ ] `prepare_dataset.py`에 038 파서 추가
  - 이미지당 JSON 1개 (`segments[]`) 구조 파싱
  - `type == '수식/텍스트'` segment만 필터링 (낙서기호·도형 제외)
  - `\displaystyle` 정규화 제거 (TS_3 라벨과 스타일 통일)
  - multi-segment 이미지: 각 segment의 `equation`을 줄바꿈으로 이어붙이기

**속도 최적화 (PyTorch SDPA)**
- [x] flash-attn → CUDA 13 미지원으로 포기, PyTorch 내장 SDPA로 대체
  - `attn_implementation="sdpa"` (별도 설치 불필요, 메모리 절감 효과 유사)
- [x] `per_device_train_batch_size` 4 → 8
- [x] `gradient_accumulation_steps` 4 → 2 (effective batch 16 유지)
- [x] `dataloader_num_workers` 4 → 8, `dataloader_pin_memory=True`
- 예상 학습 시간: 3 epoch 기준 **9~12시간**

**에이전트 실행 순서**
- [x] Step 0: 환경 확인 + `ocr_training/requirements.txt` + flash-attn 설치
- [x] Step 1: `ocr_training/scripts/extract_images.py` — TS_3 zip + 038 손글씨 zip → `data/ocr_samples/images/`
- [x] Step 2: `ocr_training/scripts/prepare_dataset.py` — labels.json + 038 JSON → `train.jsonl` / `test.jsonl` (~251k / ~28k)
- [ ] Step 3: `ocr_training/scripts/train.py` — QLoRA 파인튜닝 (3 epoch, Flash Attn2, batch=8)
- [ ] Step 4: `ocr_training/scripts/evaluate_ocr.py` — CER 평가 (목표 < 5%)
- [ ] Step 5: `ocr_training/scripts/merge_lora.py` — LoRA merge → `ocr_training/output/got_ocr_merged/`

**완료 후**
- [ ] `.env` 전환
  ```env
  OCR_MODEL=got_ocr
  GOT_OCR_MODEL_PATH=/home/yebin/workSpace/Argus/ocr_training/output/got_ocr_merged
  ```
- [ ] OCR E2E 검증 — AI-HUB 손글씨 이미지 업로드 → 채점 파이프라인 통과 확인

---

## Phase 8: E2E 재검증

**Phase 7 전체 완료 후 시작.**

- [ ] 기존 통합 테스트(`tests/test_integration.py`) 업데이트
  - `explanation` → `feedback` 필드명 변경
  - 이미지 업로드 테스트 시나리오 추가
  - 개인화 피드백 구조 검증 (student_mistakes, correct_approach, key_concept)
- [ ] AI-HUB 손글씨 이미지로 OCR → 채점 → 피드백 E2E 검증
- [ ] 할루시네이션 탐지 방향 변경 검증 (피드백 정확성)
- [ ] 통합 테스트 전체 통과 확인

---

## Phase 9: 배포

**Phase 8 완료 후 시작.**

- [ ] EC2 인스턴스 생성 (t3.medium, Ubuntu 22.04)
  - 보안 그룹: 22(SSH), 80(HTTP), 443(HTTPS)
- [ ] EC2 Elastic IP 연결
- [ ] EC2에 의존성 설치 (Python 3.11, Node, PostgreSQL, Nginx)
- [ ] EC2 PostgreSQL DB 생성 + 마이그레이션 적용
- [ ] `.env` 프로덕션 설정 (ANTHROPIC_API_KEY, DB URL, TEACHER_PASSWORD)
- [ ] `scripts/seed.py` 실행 — AI-HUB 변환 데이터 EC2 DB 삽입
- [ ] `systemd` 서비스 파일 작성 + 등록 (`argus-backend.service`)
- [ ] React 빌드 산출물 → EC2 `/var/www/argus/` 복사
- [ ] Nginx 설정 (`/api/*` → FastAPI, `/*` → React 정적)
- [ ] 도메인 DNS A 레코드 → Elastic IP 연결
- [ ] Let's Encrypt HTTPS 인증서 발급 (`certbot`)
- [ ] HTTPS 최종 접속 확인

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
