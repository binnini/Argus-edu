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
