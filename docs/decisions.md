# 의사결정 기록 (ADR)

주요 기술/정책 결정을 기록한다.  
**가역성** 기준: 🔴 비가역 (변경 시 큰 비용) · 🟡 준가역 (변경 가능하나 작업 필요) · 🟢 가역 (언제든 변경 가능)

---

## 시스템 정책

---

### ADR-001 개인화 피드백 자동 승인 금지
**날짜**: 2026-04-06 (ADR-014에 의해 범위 확장, 2026-04-07)  
**가역성**: 🔴 비가역

**결정**: 신뢰도 High여도 AI 생성 개인화 피드백은 반드시 교사 승인 후에만 학생에게 노출한다.

**근거**: 학생의 오류를 잘못 짚은 피드백은 잘못된 개념을 강화하는 역효과를 낳는다. HITL의 존재 이유 자체가 이 정책에 있다.

**트레이드오프**: 교사 검토 병목이 발생할 수 있으나, SLA와 알림으로 관리한다.

**변경 조건**: 파일럿 데이터에서 AI-교사 피드백 일치율이 95% 이상이고, 교사가 명시적으로 완화를 요청한 경우에 한해 재검토.

---

### ADR-002 채점 점수와 개인화 피드백 분리 처리
**날짜**: 2026-04-06  
**가역성**: 🔴 비가역

**결정**: 채점 점수(숫자)와 개인화 피드백(교육 콘텐츠)을 별도 정책으로 처리한다.
- 채점 점수: 신뢰도 High(≥0.75) 시 즉시 노출
- 개인화 피드백: 신뢰도 무관, 항상 교사 승인 후 노출

**근거**: 점수 지연은 불편이지만, 학생의 오류를 잘못 분석한 피드백은 교육적 해악이다.

**영향**: DB 스키마(`score_visible` 필드), API 응답 구조, 프론트엔드 렌더링 조건 모두 이 결정에 의존한다.

---

## AI 모델

---

### ADR-003 AI 모델을 환경변수로 분리
**날짜**: 2026-04-06  
**가역성**: 🟢 가역

**결정**: 모델명을 코드에 하드코딩하지 않고 `GRADING_MODEL`, `FEEDBACK_MODEL`, `OCR_MODEL` 환경변수로 분리한다.

**근거**: 비용 최적화 또는 성능 개선을 위해 모델 교체가 필요할 수 있다.

**현재 기본값**: `claude-sonnet-4-6` (채점·피드백), `pix2tex` (OCR)

**모델 교체 시 필수 검증**:
- 한국어 수학 풀이 JSON 구조화 출력 정확도
- 학생 오류 식별 정확도 (개인화 피드백)
- 멀티 샘플링 불일치율 변화

---

### ADR-004 로컬 LLM 미채택 (MVP)
**날짜**: 2026-04-06  
**가역성**: 🟡 준가역

**결정**: Gemma 4 27B 등 로컬 LLM을 MVP에서 제외하고 Claude API를 사용한다.

**근거**:
- GPU 인스턴스(g4dn.xlarge) 비용: 월 $376 이상
- t3.medium CPU 추론: 문제 1개당 2~5분 (실사용 불가)
- 한국어 수학 오류 분석 피드백의 할루시네이션 발생률이 Claude 대비 높음

**비용 예측**: 프롬프트 캐싱 적용 시 Claude API 월 $5~15, EC2 포함 총 월 $40~50.

**재검토 조건**: 누적 피드백 데이터로 파인튜닝이 가능해지는 2개월차.

---

## 할루시네이션 탐지

---

### ADR-005 신뢰도 계산식 결정
**날짜**: 2026-04-06  
**가역성**: 🟡 준가역

**결정**: `trust_score = 0.6 * hhem_score + 0.4 * (1 - inconsistency_rate)`

**근거**: HHEM은 피드백이 reference_solution 기준으로 사실적으로 정확한지 측정하고, 불일치율은 AI 자체의 확신도를 나타낸다.

**현재 임계값**: 0.75 (`TRUST_THRESHOLD` 환경변수로 조정 가능)

**변경 조건**: 파일럿 데이터에서 탐지 정밀도가 80% 미달 시 가중치·임계값 재조정.

---

### ADR-006 멀티 샘플링 3회 (개인화 피드백만)
**날짜**: 2026-04-06  
**가역성**: 🟡 준가역

**결정**: 개인화 피드백 생성 시 동일 프롬프트를 3회 호출하여 불일치 구간을 탐지한다. 채점은 단일 호출.

**근거**: 채점은 HHEM + SBERT로 충분히 검증 가능하나, 개인화 피드백은 서술형이라 오류 식별이 문장 내에 숨어있을 수 있다. 멀티 샘플링으로 AI의 확신도를 간접 측정한다.

**비용 영향**: feedback 호출이 grading의 3배. 프롬프트 캐싱으로 입력 토큰 절감.

---

### ADR-016 할루시네이션 탐지 방향 변경 — 피드백 정확성 검증
**날짜**: 2026-04-07  
**가역성**: 🟡 준가역

**결정**: HHEM 검증 대상을 "일반 풀이 설명 vs 참조 풀이"에서 "개인화 피드백이 학생의 실제 오류를 올바르게 짚었는가"로 변경한다.

**근거**: 피드백이 reference_solution과 일치하는지보다, 피드백이 채점 결과(어떤 단계가 틀렸는가)와 일치하는지가 더 중요하다.

**구현**:
- premise: `reference_solution + grading_result (감점 단계)`
- hypothesis: `ai_feedback.correct_approach`
- 불일치율: 3회 피드백 간 오류 식별 및 교정 방향의 일관성

---

## 인프라

---

### ADR-007 단일 EC2 인스턴스 구성
**날짜**: 2026-04-06  
**가역성**: 🟡 준가역

**결정**: FastAPI, Nginx, PostgreSQL, SBERT를 단일 t3.medium 인스턴스에서 운영한다.

**근거**: MVP 단계에서 비용 최소화.

**위험**: SBERT 로드 시 ~327MB. OCR 엔진 추가 시 메모리 검토 필요.

**변경 조건**: 파일럿 이후 사용자 수 증가 시 DB 분리(RDS) 및 오토스케일링 검토.

---

### ADR-008 PostgreSQL 선택 (SQLite 미채택)
**날짜**: 2026-04-06  
**가역성**: 🔴 비가역

**결정**: SQLite 대신 PostgreSQL을 사용한다.

**근거**: `JSONB` 타입(rubric, feedback 저장)과 Generated Column(`score_delta`) 등 PostgreSQL 기능이 필요하다.

---

## MVP 범위

---

### ADR-009 데이터 소스 — AI-HUB 채택 + 전과정 확장
**날짜**: 2026-04-07 (기존 ADR-009 교체, 재개정)  
**가역성**: 🟢 가역

**결정**: 자체 생성 문제 데이터(Claude 생성 15개)를 폐기하고 AI-HUB 수학 데이터셋 전과정(초3~6학년, 중1~3학년, 고등학교 공통수학)으로 전면 교체한다.

**근거**: 자체 생성 데이터의 품질 문제(수식 오류, reference_solution 불일치) 확인. AI-HUB 데이터는 검수된 공개 데이터셋. OCR 파인튜닝 데이터 다양성을 위해 전 학년 손글씨 이미지 활용.

**변환 작업**: `scripts/convert_aihub.py`로 AI-HUB 원본 → Argus 스키마 변환 (전 학년 GRADE_SETS 루프).

---

### ADR-010 교사 인증을 단순 비밀번호 1개로 제한 (MVP)
**날짜**: 2026-04-06  
**가역성**: 🟢 가역

**결정**: 교사 대시보드 인증을 `X-Teacher-Password` 헤더의 단일 비밀번호로 처리한다.

**변경 조건**: 3개월차 다수 교사 온보딩 시 JWT 기반 인증 시스템으로 교체.

---

### ADR-011 HHEM 로컬 실행 → HF Inference API 전환
**날짜**: 2026-04-06  
**가역성**: 🟡 준가역

**결정**: HHEM-2.1-Open을 로컬 실행하지 않고 HF Inference API 호출. HF_TOKEN 미설정 시 SBERT fallback.

**근거**: HHEM 커스텀 코드가 transformers 4.x/5.x 모두에서 AutoTokenizer 인식 오류 발생.

---

### ADR-012 Python 3.11 사용 (3.14 미지원)
**날짜**: 2026-04-06  
**가역성**: 🟢 가역

**결정**: asyncpg, pydantic-core의 Python 3.14 미지원으로 3.11 사용.

---

### ADR-013 LLM 클라이언트 추상화 + Ollama 지원
**날짜**: 2026-04-06  
**가역성**: 🟢 가역

**결정**: `services/llm_client.py`로 Anthropic API와 Ollama를 동일 인터페이스로 추상화. `LLM_PROVIDER` 환경변수로 전환.

---

### ADR-014 개인화 피드백으로 전환 (일반 풀이 설명 폐기)
**날짜**: 2026-04-07  
**가역성**: 🟡 준가역

**결정**: "모범 풀이를 단계별로 설명하는" 방식에서 "학생이 틀린 부분을 분석하고 교정 방향을 제시하는" 개인화 피드백 방식으로 전환한다.

**근거**: 일반 풀이 설명은 학생이 어디서 왜 틀렸는지 직접적으로 알려주지 않는다. 학생 오류에 집중한 피드백이 교육적으로 더 효과적이다.

**변경 범위**:
- `services/feedback.py` (기존 `explanation.py` 대체)
- 프롬프트 템플릿 전면 교체 (docs/prompts.md v2.0)
- API 응답 필드명: `explanation` → `feedback`
- DB 컬럼명: `ai_explanation` → `ai_feedback`, `teacher_explanation` → `teacher_feedback`

---

### ADR-015 OCR 전략 — MVP: AI-HUB 데이터, 미래: Canvas 직접 입력
**날짜**: 2026-04-07  
**가역성**: 🟡 준가역

**결정**:
- **MVP**: AI-HUB 손글씨 수식 인식 데이터로 이미지 업로드 파이프라인 검증. OCR 엔진은 `pix2tex` (오픈소스).
- **미래**: 패드/핸드폰 Canvas 직접 그리기 → 실시간 OCR (현재 MVP 범위 외).

**근거**: 실시간 손글씨 입력은 수식 OCR 정확도(한국어+수식 혼합) 문제로 MVP 적합하지 않음. 기술 난이도: Canvas UI(낮음) + 수식 OCR(매우 높음).

**OCR 엔진 선택 기준**:
- `pix2tex`: 오픈소스, LaTeX 수식 특화, 한국어 텍스트 혼합 약함
- `mathpix`: 상용 API ($0.004/req), 한국어+수식 혼합 강함
- `OCR_MODEL` 환경변수로 전환 (코드 변경 불필요)

**마이그레이션 경로**: pix2tex → Mathpix API → AI-HUB 데이터 파인튜닝 모델

---

---

### ADR-017 OCR 파인튜닝 데이터셋 — AI-HUB TS_3 + 038 손글씨 혼합
**날짜**: 2026-04-09  
**가역성**: 🟡 준가역

**결정**: GOT-OCR 2.0 파인튜닝에 AI-HUB의 두 데이터셋을 혼합하여 사용한다.
- **TS_3** (수식 인식): 손글씨 수식 이미지 + LaTeX 라벨 160,015개
- **038 손글씨** (초4~6, 중1~3, 고1~3): 손글씨 텍스트/수식 혼합 이미지 119,233개
- 최종 split: train ~251k / test ~28k

**근거**:
- TS_3만으로는 수식 전용 편향이 강해, 한국어 텍스트(예: "직선", "합동")와 수식 혼합 답안 인식이 약함
- 038 데이터가 초중고 전 학년 실제 손글씨 스타일을 포함하여 도메인 다양성 확보
- 혼합 결과 train 약 251k → 3 epoch 기준 약 44시간 학습

**038 데이터 전처리 규칙**:
- `type == '수식/텍스트'` segment만 사용 (낙서·기호·도형 제외)
- multi-segment 이미지: 각 segment의 `equation` 값을 줄바꿈으로 연결
- `\displaystyle` 접두사 제거 (TS_3 라벨 스타일 통일)

**트레이드오프**: 데이터 이질성으로 인한 학습 복잡도 증가. 단, 실제 수학 답안은 수식+텍스트 혼합이 일반적이므로 허용.

---

### ADR-018 GOT-OCR 2.0 파인튜닝 전략 — chat() 포맷 정렬 + LoRA
**날짜**: 2026-04-10  
**가역성**: 🟡 준가역

**결정**: GOT-OCR 2.0을 LoRA로 파인튜닝할 때, 학습 입력을 모델의 `chat()` 메서드가 실제로 사용하는 대화 포맷과 동일하게 구성한다.

**학습 입력 포맷**:
```
<|im_start|>system
        You should follow the instructions...<|im_end|>
<|im_start|>user
<img><imgpad>×256</img>
OCR: <|im_end|>
<|im_start|>assistant
{ground_truth}<|im_end|>
```
- `input_ids`: 위 전체 시퀀스 토크나이즈 (MAX_LENGTH=640)
- `labels`: `<|im_start|>assistant\n` 이전 구간은 `-100`으로 마스킹 → ground_truth 부분만 loss 계산
- `images`: `list[Tensor(1, 3, 1024, 1024)]`, `bfloat16`

**이전 학습(v1)의 실패 원인**:
- 학습 시: `images 텐서 + ground_truth 토큰`만 입력 (대화 포맷 없음)
- 추론 시: `chat()`이 system/user 프롬프트를 앞에 붙여 전달 → 포맷 불일치
- 결과: 이미지 무시하고 `$$$$의수의수...` 같은 degenerate 출력 생성

**LoRA 설정**:
- `r=16, lora_alpha=32, dropout=0.05`
- target: `q_proj, k_proj, v_proj, o_proj, gate_proj, up_proj, down_proj`
- Vision encoder는 model forward 내 `set_grad_enabled(False)`로 자동 동결 → LoRA 불필요

**기타 학습 설정**:
- `batch=2, grad_accum=16` (effective 32), `MAX_LENGTH=640`
- `attn_implementation="sdpa"` (flash-attn은 CUDA 13/Blackwell 미지원)
- `OcrTrainer`: `_prepare_inputs` override로 `images` list를 GPU로 수동 이동

**검증**: checkpoint-4000 (epoch 0.52) 시점에서 5개 샘플 테스트 결과 LaTeX 수식 구조 정상 출력 확인. 완전 일치 2건, 수식 구조 정확 3건.

---

### ADR-019 배포 전략 — Mac Mini M4 직접 서빙 + Cloudflare Tunnel (ADR-007 대체)
**날짜**: 2026-04-10  
**가역성**: 🟡 준가역  
**대체**: ADR-007 (단일 EC2 인스턴스 구성) 철회

**결정**: EC2 인스턴스 대신 Mac Mini M4(24GB)를 서버로 직접 사용하고 Cloudflare Tunnel로 공개한다.

**실측 근거**:

| 항목 | 수치 |
|------|------|
| GOT-OCR MPS 추론 속도 | 1.5~2.5초/이미지 |
| 모델 로딩 시간 | 1.2초 (서버 기동 시 1회) |
| 모델 로드 후 메모리 | 16.2 GB / 24 GB (여유 7.8 GB) |
| 모델 메모리 세부 | GOT-OCR 2.1 GB + SBERT 90 MB + OS+FastAPI ~2 GB |

**동시 사용자 수용 한계**:
- 텍스트 제출: **30~50명** (Claude API 비동기 병렬)
- 이미지 제출 혼합: **10~15명** 쾌적 (OCR MPS 직렬 큐잉)
- 학교 교실 1개(30명) 동시 수업 대응 가능

**비용 비교**:
- EC2 t3.xlarge + RDS: 월 ~$145
- Mac Mini 직접 서빙: Claude API 사용료만 (월 $5~20 추정)

**구성**:
```
Mac Mini M4 (24GB)
├── FastAPI + PostgreSQL
├── GOT-OCR 2.0 (MPS, float32)
├── SBERT all-MiniLM-L6-v2 (CPU)
└── HHEM → HF Inference API
Cloudflare Tunnel → 외부 공개 (DDoS 보호, SSL 자동)
LLM → Claude API (외부)
```

**트레이드오프**:
- 단점: 가정용 인터넷 의존, 단일 장애점
- 완화: Cloudflare Tunnel(가용성 보강), UPS 전원 관리 권장

**변경 조건**: 파일럿 이후 학교 수 3개 이상 or 동시 접속 50명 초과 시 AWS 이전 검토.

---

### ADR-020 GOT-OCR 서빙 전략 — Mac Mini MPS + model.chat()
**날짜**: 2026-04-10  
**가역성**: 🟡 준가역

**결정**: merge된 GOT-OCR 2.0 모델을 Mac Mini M4 MPS에서 float32로 서빙하고, 추론은 `model.chat()` 방식을 사용한다.

**근거**:
- 학습(train.py)의 입력 포맷이 `model.chat()`의 내부 포맷과 동일하게 설계됨(ADR-018)
- LoRA merge 후에는 커스텀 텐서 전처리 없이 `chat()`으로 올바른 추론 가능
- MPS는 bfloat16 미지원 → float32 사용 (성능 패널티 허용 범위 내)

**구현 사항**:
- `modeling_GOT.py`의 `.cuda()` 하드코딩을 `next(self.parameters()).device`로 패치 (Mac/WSL 겸용)
- `_GotOcrEngine.recognize()`: image_bytes → 임시 파일 → `model.chat(path, ocr_type='ocr')`
- 모델 로드: `get_class_from_dynamic_module` 사용 (GOT-OCR 커스텀 모듈 필수)
- 디바이스 자동 선택: CUDA → float32/bfloat16, MPS → float32, CPU → float32

**WSL(CUDA) 환경**: `model.chat()` 내부 `.cuda()` 호출이 그대로 동작하므로 패치 불필요.

**제약**:
- OCR 요청은 MPS 단일 컨텍스트로 직렬 처리 → 동시 이미지 요청 시 내부 큐잉 필요
- 임시 파일 I/O 포함 (image_bytes → tmpfile → chat()) — SSD 환경에서 무시 가능한 오버헤드

---

---

### ADR-021 UX 전면 재설계 — 학생 신원·교사 탭·문제 관리·캔버스·모던 디자인
**날짜**: 2026-04-10  
**가역성**: 🟡 준가역

**배경**: Phase 5까지의 프론트엔드는 기능 검증 중심의 최소 UI였다. 파일럿 준비 단계에서 실제 교사·학생 사용 시나리오를 충족하기 위해 UX 전면 재설계가 필요하다.

---

#### 21-1. 학생 신원 추가 (student_name / student_id)

**결정**: 회원가입 없이 제출 시 이름·학번을 입력받아 `submissions` 테이블에 저장한다.

**근거**: 교사가 "누가 어떤 문제를 풀었는지"를 확인하려면 최소한의 신원 정보가 필요하다. JWT 인증 시스템은 MVP 범위 외(ADR-010)이므로, 이름+학번 자유 입력으로 대체한다.

**DB 변경**: `submissions` 테이블에 `student_name VARCHAR(50) NOT NULL`, `student_id VARCHAR(20)` 컬럼 추가 (마이그레이션 `0003_add_student_info.py`).

**제약**: 동명이인 구분은 학번으로만 한다. 인증이 없으므로 학번 위조 가능 — MVP 단계에서 허용.

---

#### 21-2. 학생 입력 방식 확장 — 이미지 업로드·카메라·캔버스

**결정**: `AnswerInput.tsx`를 3-탭 구조로 확장한다.
- **Tab 1 — 이미지 업로드**: 기존 파일 선택 (유지)
- **Tab 2 — 카메라 촬영**: `<input type="file" accept="image/*" capture="environment">` — 모바일에서 카메라 직접 호출
- **Tab 3 — 캔버스 드로잉**: 마우스/터치 손글씨 입력 (신규, 가역적)

**캔버스 구현 전략**:
- `CanvasInput.tsx`를 독립 컴포넌트로 분리 (제거 시 탭 1개만 숨기면 됨)
- 라이브러리: `react-signature-canvas` (경량, 터치 지원)
- 출력: `canvas.toBlob()` → PNG → 기존 `POST /api/v1/submissions/image` 재사용 (백엔드 변경 없음)
- Feature flag: `AnswerInput.tsx` 상단 `const CANVAS_ENABLED = true` 한 줄로 제거 가능

**근거**: 카메라 입력은 `capture` 속성만으로 구현 가능(코스트 0). 캔버스는 별도 백엔드 없이 기존 이미지 파이프라인을 재사용하므로 리스크가 낮다. 수식 OCR 정확도는 파인튜닝 모델 성능에 의존하므로 별도 검증 필요.

---

#### 21-3. 교사 대시보드 탭 기반 재설계

**결정**: `TeacherDashboard.tsx`를 3-탭 구조로 재설계한다.

| 탭 | 컴포넌트 | 내용 |
|---|---|---|
| 문제 관리 | `ProblemManager.tsx` | 문제 등록·수정·삭제 |
| 풀이 현황 | `SubmissionOverview.tsx` | 학생별·문제별 제출 현황 테이블 |
| 검토 큐 | `ReviewQueue.tsx` (기존 `ReviewCard.tsx` 재사용) | 할루시네이션 가능성 높은 피드백 검토 |

**근거**: 현재 교사 화면이 큐 전용이라 문제 관리와 현황 파악이 불가능하다. 탭 구조는 컴포넌트 간 독립성을 유지하면서 화면 전환 비용을 최소화한다.

---

#### 21-4. 문제 관리 API 추가

**결정**: 교사 전용 문제 CRUD API를 추가한다 (`X-Teacher-Password` 인증 동일 적용).

```
POST   /api/v1/teacher/problems          # 문제 등록
GET    /api/v1/teacher/problems          # 교사용 문제 목록 (정답·루브릭 포함)
PUT    /api/v1/teacher/problems/{id}     # 문제 수정
DELETE /api/v1/teacher/problems/{id}     # 문제 삭제 (제출이 있으면 soft delete)
GET    /api/v1/teacher/submissions       # 전체 제출 현황 (문제·학생별 필터)
GET    /api/v1/teacher/problems/{id}/submissions  # 문제별 제출 현황
```

**근거**: seed.py로만 문제를 등록하면 파일럿 교사가 직접 문제를 추가할 수 없다.

---

#### 21-5. 모던 디자인 시스템 도입

**결정**: Tailwind CSS + shadcn/ui + KaTeX를 디자인 시스템으로 채택한다.

| 선택 | 이유 |
|---|---|
| **Tailwind CSS** | 유틸리티 클래스, 빠른 iteration, 커스터마이징 용이 |
| **shadcn/ui** | Radix UI 기반, 접근성 보장, 컴포넌트를 프로젝트 내 코드로 소유 (번들 최소화) |
| **KaTeX** | LaTeX 수식 렌더링 (문제 본문·풀이 과정 수식 지원) |
| **Lucide React** | 아이콘 라이브러리 (shadcn/ui 기본 채택) |

**디자인 방향**:
- 색상: Zinc(중립) + Indigo(액센트) 팔레트
- 다크모드: Tailwind `dark:` 클래스 + `next-themes` 방식 (shadcn/ui 권장)
- 타이포그래피: Pretendard (한국어 최적화 고딕체) + 시스템 monospace

**트레이드오프**: 기존 인라인 스타일·CSS 모듈을 Tailwind로 전면 교체해야 함. 기존 코드가 소규모이므로 비용 낮음.

---

### ADR-022 UX 2차 개선 — 점수 제거·리뷰카드 개편·검색 필터·캔버스 지우개
**날짜**: 2026-04-11  
**가역성**: 🟢 가역

**결정**: 파일럿 준비 과정에서 발생한 UX 문제들을 일괄 해소한다.

#### 22-1. 점수 → 정답/오답 표시 전환

**결정**: 학생·교사 모든 화면에서 숫자 점수(1점, 2점)를 "정답/오답" Badge로 대체한다.

**근거**: 채점 기준이 맞았는지 여부가 학생에게 더 직관적이다. 세부 점수는 교사 수정 시만 필요하다.

**영향 파일**: `GradingStatus.tsx`, `SubmissionOverview.tsx`, `StudentPage.tsx`

---

#### 22-2. ReviewCard 전면 개편

**결정**: 교사 검토 카드를 아래와 같이 개선한다.
- 토글 없이 AI 피드백 항상 표시 (펼침/접힘 제거)
- 문제 본문·정답 인라인 표시 (별도 조회 불필요)
- 이미지 제출의 경우 학생 답변 이미지 인라인 표시
- OCR 원문이 있으면 답변 이미지와 나란히(2컬럼) 표시
- SLA 3시간 미만 시 경고 강조

**근거**: 교사가 검토 카드 1개를 처리하는 데 평균 3분 목표 달성을 위해, 외부 이동 없이 카드 내에서 모든 정보 확인이 가능해야 한다.

**DB 변경**: `teacher_queue` 조회 시 `problem.content`, `problem.answer`, `ocr_raw_text` 포함 반환.

---

#### 22-3. 검토 큐 / 문제 관리 검색 필터 추가

**결정**: ReviewQueue와 ProblemManager에 텍스트 검색 + 정렬 + 카테고리 필터를 추가한다.

| 컴포넌트 | 추가 필터 |
|---|---|
| ReviewQueue | 학생명/문제 검색, 문제별 필터, 정렬(SLA/학생/문제) |
| ProblemManager | 텍스트 검색, 학교급(초중고) 필터, 영역 필터, 난이도 필터, 정렬 |

**구현**: 모두 클라이언트 측 `useMemo` 필터링 (추가 API 없음).

---

#### 22-4. 캔버스 지우개 + SVG 커서

**결정**: `CanvasInput.tsx`에 `DrawMode = "pen" | "eraser"` 전환 기능을 추가한다.

- 지우개: 흰색 펜(penColor white, effectiveWidth = penWidth × 3)으로 구현
- SVG 동적 커서: 모드·굵기에 따라 원형 커서 크기/색이 실시간 반영
- 펜 굵기 선택: 2, 4, 6, 8 (4단계)

**근거**: 캔버스 전체 지우기만으로는 세부 수정이 불가능하다. react-signature-canvas의 흰색 펜 우회 방식으로 추가 의존성 없이 구현 가능.

---

### ADR-023 학생 풀이 상세 조회 및 답안 재제출
**날짜**: 2026-04-11  
**가역성**: 🟡 준가역

**결정**: 학생이 제출 이력에서 개별 풀이를 클릭해 상세 내용을 확인하고, 미승인 상태에서 답안을 수정 재제출할 수 있도록 한다.

**API 변경**:
- `GET /api/v1/submissions/{id}` — `problem_title`, `problem_content` 필드 추가 반환
- `GET /api/v1/submissions?student_id=` — `image_path`, `student_answer` 필드 추가 반환
- `PUT /api/v1/submissions/{id}` — 답안 수정 (pending/graded 상태 한정, 교사 처리 후 불가)

**재제출 처리 규칙**:
1. `teacher_queue` 레코드 삭제
2. `grading_result` 레코드 삭제
3. `status = "pending"` 리셋
4. 채점 파이프라인 재실행 (`_run_grading_pipeline`)

**근거**: 학생이 오타 등 단순 실수를 수정할 수 있어야 하나, 교사가 이미 검토한 건은 재제출 불가(데이터 무결성).

**프론트엔드 스테이지**: `history → detail → editing → polling → done`

---

### ADR-024 숙제/그룹 시스템 + 학생 대시보드 2단 레이아웃
**날짜**: 2026-04-11  
**가역성**: 🟡 준가역

**결정**: 교사가 학생 그룹을 관리하고 그룹별로 숙제를 할당하는 기능을 추가한다. 학생 화면은 사이드바 + 메인의 2단 레이아웃으로 전환한다.

#### 24-1. 그룹/숙제 데이터 모델

**새 테이블**:

| 테이블 | 역할 |
|---|---|
| `student_groups` | 학생 그룹 (이름, 생성일) |
| `group_members` | 그룹 멤버 (group_id, student_id, student_name) |
| `homeworks` | 숙제 (제목, group_id, due_date) |
| `homework_problems` | 숙제-문제 연결 (homework_id, problem_id) |

**DB 자동 마이그레이션**: `main.py` lifespan에서 `Base.metadata.create_all`로 개발 환경 자동 생성.

**인증 없는 그룹 연결 방식**: `GroupMember.student_id = Submission.student_id` 문자열 매칭. JWT 도입 전 MVP 허용 범위.

#### 24-2. 교사 API 추가

```
GET    /api/v1/teacher/groups                           # 그룹 목록
POST   /api/v1/teacher/groups                           # 그룹 생성
DELETE /api/v1/teacher/groups/{id}                      # 그룹 삭제
POST   /api/v1/teacher/groups/{id}/members              # 멤버 추가
DELETE /api/v1/teacher/groups/{id}/members/{student_id} # 멤버 제거
GET    /api/v1/teacher/homeworks                        # 숙제 목록
POST   /api/v1/teacher/homeworks                        # 숙제 생성 (문제 일괄 할당)
DELETE /api/v1/teacher/homeworks/{id}                   # 숙제 삭제
```

#### 24-3. 학생 숙제 현황 API

```
GET /api/v1/submissions/homework?student_id=xxx
```

반환: 학생이 속한 그룹의 숙제 목록 + 각 문제별 제출 완료 여부(`submitted: bool`).

완료 판정: 해당 student_id + problem_id 조합의 Submission이 1건 이상 존재 (status 무관).

#### 24-4. 학생 UI 2단 레이아웃

**결정**: 로그인 후 화면을 왼쪽 사이드바(w-72) + 오른쪽 메인의 flex 레이아웃으로 전환한다.

**사이드바 항목**:
- **숙제 현황**: 숙제별 진행 바 (완료 문제 수/전체), 마감일 (초과 시 빨간색), 클릭 시 숙제 탭으로 이동
- **풀이 현황**: 최근 5개 이력, 클릭 시 상세 보기
- **"새 문제 풀기" 버튼**: 전체 문제 탭으로 이동

**문제 선택 탭 구조**:
- "숙제" 탭: 할당된 숙제의 문제 목록, 이미 제출한 문제는 비활성화 + "제출 완료" 표시
- "전체 문제" 탭: 기존 `ProblemSelector` 컴포넌트 유지

**모바일 대응**: 사이드바 `hidden md:flex` (모바일에서 숨김, 전체 화면 메인).

**기존 "history" 스테이지 제거**: 별도 이력 페이지 없이 사이드바에 통합.


### ADR-025 로컬 채점 LLM 모델 선정 (gemma4:e4b)
**날짜**: 2026-04-12  
**가역성**: 🟢 가역 (`.env` `GRADING_MODEL` 변경으로 즉시 교체 가능)

**결정**: Argus 채점 엔진의 로컬 LLM 모델로 `gemma4:e4b` (Ollama 태그)를 채택한다.

**배경**: Claude API 의존성을 줄이고 Mac Mini M4에서 완전 로컬 서빙을 구현하기 위해(ADR-019) 후보 모델 9종을 2단계 벤치마크로 평가했다.

**벤치마크 개요**:

| 단계 | 문항 수 | 후보 | 도구 |
|---|---|---|---|
| 예선 (5-문제 스크리닝) | 5 | gemma4:e4b, gemma4:e2b, qwen2.5:7b, qwen2.5:14b, mathstral:7b, deepseek-r1:7b, deepseek-r1:14b, phi4:14b, exaone3.5:7.8b | MLX (`mlx_lm`) |
| 본선 (30-문제 최종) | 30 | gemma4:e4b, gemma4:e2b, qwen2.5:7b | MLX (`mlx_lm`) |

벤치마크 결과 파일: `benchmark_consolidated.csv` (예선), `benchmark_30q_final.csv` (본선)  
벤치마크 스크립트: `scripts/benchmark_models.py`

**30-문제 최종 결과**:

| 모델 | 정확도 (전체) | 파싱 성공률 | 파싱 기준 정확도 | 평균 응답속도 |
|---|---|---|---|---|
| **gemma4:e4b** | **93.3%** (28/30) | 96.7% | **96.6%** | 26.8s |
| gemma4:e2b | 90.0% (27/30) | 100% | 90.0% | **10.4s** |
| qwen2.5:7b | 73.3% (22/30) | 86.7% | 84.6% | 21.4s |

레벨별 분석 (gemma4:e4b 기준):
- 초등3–6: 8/8 (100%)
- 중1–3: 10/10 (100%)
- 고1–3: 10/11 (91%) — H04 1건 오답 (두 Gemma 모델 모두 동일하게 틀림, 루브릭 모호성 의심)

**선택 근거**:
- gemma4:e4b: 최고 정확도 93.3%, 중·고등 전 구간에서 고른 성능, 단일 파싱 오류는 재시도 로직으로 흡수 가능
- gemma4:e2b 탈락 이유: 초등6·중3 구간에서 비교적 높은 오답률, 정확도 3.3%p 차이
- qwen2.5:7b 탈락 이유: 파싱오류 13.3% (4/30), 고3 구간 33%로 신뢰도 부족
- 예선 탈락 모델: deepseek-r1:7b (파싱오류 60%), deepseek-r1:14b (응답 61.5s), exaone3.5:7.8b (40%), mathstral:7b (60%), phi4:14b (60%), qwen2.5:14b (80% + 33s)

**기술 선택 사항**:
- Gemma 4 모델 thinking 모드: `apply_chat_template(enable_thinking=False)` 로 비활성화 (JSON 출력 안정성)
- 4-bit mlx-community 버전의 PLE 양자화 버그로 인해 8-bit unsloth 변환본(`unsloth/gemma-4-E4B-it-MLX-8bit`) 사용
- 프로덕션 서빙: Ollama (`gemma4:e4b`) — MLX는 벤치마크 전용

**트레이드오프**:
- 응답 속도 26.8s/문제 — gemma4:e2b(10.4s) 대비 2.6배 느림. 단, 클래스룸 환경에서 허용 가능한 수준이며 Mac Mini M4의 동시 처리 능력으로 부분 보상
- 정확도 우선: MVP 단계에서는 교사 검토 비율보다 AI-교사 일치율이 중요

**변경 조건**: 파일럿 데이터에서 AI-교사 일치율이 70% 미만이면 프롬프트 튜닝 또는 gemma4:27b 등 대형 모델로 재검토.

---

---

### ADR-026 할루시네이션 검증 전략 변경 (HHEM → LLM 배치)
**날짜**: 2026-04-12  
**가역성**: 🟡 준가역 (DB 컬럼 마이그레이션 필요)

**결정**: HHEM + 다중 샘플링 방식을 폐기하고, LLM 배치 호출 기반 비동기 할루시네이션 검증으로 전환한다.

**기존 방식 (폐기)**:
- 피드백 3회 멀티샘플링 → SBERT 불일치율 계산
- HF Inference API (HHEM-2.1-Open) 호출 → 팩추얼 일관성 스코어
- 문제점: 동기 블로킹으로 응답 레이턴시에 직접 영향 / HF API 장애 시 fallback / 실효성 의문

**신규 방식**:
```
제출 → 채점+피드백(1회) → DB 저장(hallucination_status=pending) → 즉시 응답
                                                                       ↓
[APScheduler, 5분 간격]  grading_results WHERE status='pending' LIMIT 8
→ LLM 배치 프롬프트 1회 호출 (구조화 JSON 입력 → JSON 배열 출력)
→ hallucination_score / hallucination_issues / hallucination_status 갱신
→ 교사 큐에서 할루시네이션 의심 항목 식별 가능
```

**LLM 판단 기준**:
1. `student_mistakes`가 채점 오답 단계와 일치하는가
2. `correct_approach`가 `reference_solution`을 근거로 수학적으로 올바른가
3. `key_concept`이 실제 오류 원인을 정확히 설명하는가

**검증 모델**: 현재 `GRADING_MODEL` (gemma4:e4b MLX) 사용. 검증 정확도 파일럿 후 Claude API 전환 검토.

**DB 변경** (마이그레이션 `0005_hallucination_batch.py`):
- `grading_results` 테이블: `hhem_score`, `inconsistency_rate` 제거
- `grading_results` 테이블: `hallucination_status`, `hallucination_score`, `hallucination_issues`, `hallucination_checked_at` 추가

**트레이드오프**:
- 채점 결과는 즉시 응답, 할루시네이션 검증은 최대 5분 지연 → 교사 큐 진입 시점엔 대부분 검증 완료
- 같은 모델(gemma4:e4b)이 생성+검증을 모두 담당하는 bias 위험 → 파일럿 정확도 측정 후 판단

---

## 변경 이력

| ADR | 날짜 | 변경 내용 |
|---|---|---|
| - | 2026-04-06 | 초안 작성 (ADR-001 ~ ADR-010) |
| ADR-011 | 2026-04-06 | HHEM 로컬 실행 불가 → HF Inference API 전환 |
| ADR-012 | 2026-04-06 | Python 3.11 사용 결정 |
| ADR-013 | 2026-04-06 | LLM 추상화 레이어 + Ollama 지원 추가 |
| ADR-009 | 2026-04-07 | 자체 생성 데이터 → AI-HUB 데이터로 교체 |
| ADR-014 | 2026-04-07 | 일반 풀이 설명 → 개인화 피드백으로 전환 |
| ADR-015 | 2026-04-07 | OCR 전략 결정 (MVP: AI-HUB + pix2tex) |
| ADR-016 | 2026-04-07 | 할루시네이션 탐지 방향 변경 (피드백 정확성 검증) |
| ADR-017 | 2026-04-09 | OCR 파인튜닝 데이터셋 구성 (TS_3 + 038 혼합) |
| ADR-018 | 2026-04-10 | GOT-OCR2 파인튜닝 전략 (chat() 포맷 정렬 + LoRA) |
| ADR-007 | 2026-04-10 | **철회** — ADR-019로 대체 (EC2 → Mac Mini) |
| ADR-019 | 2026-04-10 | Mac Mini M4 직접 서빙 + Cloudflare Tunnel 배포 결정 |
| ADR-020 | 2026-04-10 | GOT-OCR 서빙 전략 (Mac Mini MPS + model.chat()) |
| ADR-021 | 2026-04-10 | UX 전면 재설계 (학생 신원, 교사 탭, 문제 관리, 캔버스, 모던 디자인) |
| ADR-022 | 2026-04-11 | UX 2차 개선 (점수→정답/오답, 리뷰카드 개편, 검색 필터, 캔버스 지우개) |
| ADR-023 | 2026-04-11 | 학생 풀이 상세 조회 + 답안 재제출 기능 (PUT /submissions/{id}) |
| ADR-024 | 2026-04-11 | 숙제/그룹 시스템 + 학생 대시보드 2단 레이아웃 |
| ADR-025 | 2026-04-12 | 로컬 채점 LLM 모델 선정 (gemma4:e4b, 30-문제 벤치마크 기반) |
| ADR-026 | 2026-04-12 | 할루시네이션 검증 전략 변경 (HHEM+다중샘플링 → LLM 배치 비동기) |
