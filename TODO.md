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
- [ ] `scripts/convert_aihub.py` 작성
  - TL_1(문제) + TL_2(모범답안) 병합 → Argus problems 스키마
  - `question_type1 == "서술"` 필터링
  - `answer_text` → `reference_solution` 단계 구조화 (LLM 보조)
  - rubric 자동 생성 (단계 수 기반)
- [ ] `scripts/seed.py` 업데이트 — AI-HUB 변환 데이터 삽입
- [ ] 기존 자체 생성 데이터 15개 DB에서 제거
- [ ] `data/ocr_samples/` 구성 — TL_3 손글씨 이미지 + labels.json

### 7-2. DB 마이그레이션

- [ ] `backend/alembic/versions/0002_redesign.py` 작성
  - `submissions` 테이블: `input_type`, `ocr_raw_text`, `image_path` 컬럼 추가
  - `grading_results` 테이블: `ai_explanation` → `ai_feedback` 컬럼 rename
  - `teacher_queue` 테이블: `teacher_explanation` → `teacher_feedback` 컬럼 rename
  - `problems` 테이블: `source` 컬럼 추가
- [ ] 로컬 DB에 마이그레이션 적용 (`alembic upgrade head`)

### 7-3. OCR 서비스 `[P]`

- [ ] `backend/services/ocr.py` 작성
  - `OCR_MODEL` 환경변수로 엔진 선택 (`pix2tex` | `mathpix`)
  - pix2tex 로컬 실행 구현
  - Mathpix API 연동 구현 (fallback)
  - OCR 실패 시 에러 반환 (무시하지 말 것)
- [ ] `requirements.txt` 업데이트 — pix2tex 추가
- [ ] `POST /api/v1/submissions` — `multipart/form-data` 이미지 업로드 지원 추가
- [ ] AI-HUB TL_3 손글씨 이미지로 OCR 정확도 검증

### 7-4. 개인화 피드백 서비스 `[P]`

- [ ] `backend/services/feedback.py` 작성 (기존 `explanation.py` 교체)
  - 프롬프트: 학생 오류 분석 + 교정 방향 (docs/prompts.md v2.0 기준)
  - 출력 스키마: `student_mistakes` + `correct_approach` + `key_concept`
  - 멀티 샘플링 3회 + 불일치율 계산
  - Ollama/Anthropic 양쪽 지원
- [ ] `backend/services/hallucination.py` 업데이트
  - premise: `reference_solution + grading_result`
  - hypothesis: `ai_feedback.correct_approach`
- [ ] `backend/routers/submissions.py` 업데이트
  - `explanation_service` → `feedback_service`
  - 응답 필드명: `explanation` → `feedback`
- [ ] `backend/schemas/` 업데이트 — feedback 구조 반영

### 7-5. 프론트엔드 개편 `[P]`

- [ ] `frontend/src/components/AnswerInput.tsx` 신규
  - 텍스트 입력 탭 / 이미지 업로드 탭 전환 UI
  - 이미지 업로드 시 `multipart/form-data` 전송
- [ ] `frontend/src/components/FeedbackPanel.tsx` 신규
  - `student_mistakes` 목록 렌더링
  - `correct_approach` 단계별 렌더링
  - `key_concept` 요약 표시
  - `teacher_approved === true` 일 때만 렌더링 (절대 제약)
- [ ] `frontend/src/pages/StudentSubmit.tsx` 업데이트
  - `AnswerInput` 컴포넌트 사용
  - `FeedbackPanel` 컴포넌트 연결
- [ ] `frontend/src/api/submissions.ts` 업데이트
  - `submitAnswerText()` / `submitAnswerImage()` 분리
- [ ] `npm run build` 빌드 성공 확인

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
