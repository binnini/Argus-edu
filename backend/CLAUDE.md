# Backend — 개발 규칙

FastAPI + PostgreSQL 백엔드. 루트 CLAUDE.md의 제약이 모두 적용됨.

## 프로젝트 구조

```
backend/
├── main.py                  # FastAPI 앱 + lifespan 이벤트
├── config.py                # 환경변수 로딩 (모델명, 임계값 등)
├── db.py                    # PostgreSQL 세션 + 의존성 주입
├── routers/
│   ├── submissions.py       # POST /api/v1/submissions (텍스트·이미지 모두 처리)
│   ├── teacher.py           # GET/POST /api/v1/teacher/*
│   └── feedback.py          # GET /api/v1/feedback/*
├── services/
│   ├── ocr.py               # 손글씨 이미지 → 텍스트 변환
│   ├── grading.py           # LLM 채점 + SBERT 보조
│   ├── feedback.py          # 개인화 피드백 생성 (멀티 샘플링, 학생 오류 분석)
│   ├── hallucination.py     # 피드백 정확성 검증 (학생 오류를 올바르게 짚었는가)
│   └── trust_gate.py        # 신뢰도 종합 + 큐 라우팅
├── models/                  # SQLAlchemy ORM (schema.md 참조)
└── schemas/                 # Pydantic 입출력 (api.md 참조)
```

## 코딩 규칙

### ML 모델 로딩

```python
# main.py lifespan에서 1회만 로드 — 요청마다 로드하면 OOM
@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.sbert = SentenceTransformer("all-MiniLM-L6-v2")
    app.state.hhem = load_hhem_detector(sbert_model=app.state.sbert)
    app.state.grading_service = GradingService(app.state.sbert)
    app.state.feedback_service = FeedbackService(app.state.sbert)
    yield
```

SBERT 로드 시 약 327MB RAM 사용. 절대 요청 핸들러 내에서 로드하지 말 것.

### OCR 서비스

```python
# services/ocr.py
class OCRService:
    async def extract_text(self, image_bytes: bytes) -> str:
        """이미지에서 수식+텍스트 추출. OCR_MODEL 환경변수로 엔진 선택."""
```

- `OCR_MODEL=pix2tex`: 오픈소스, LaTeX 수식 특화
- `OCR_MODEL=mathpix`: 상용 API, 한국어 + 수식 혼합에 더 강함
- OCR 실패 시 원본 이미지 경로를 submission에 보존하고 에러 반환 (무시하지 말 것)

### DB 세션

```python
# 올바른 방식 — dependency injection
async def get_session() -> AsyncSession:
    async with SessionLocal() as session:
        yield session

@router.post("/submissions")
async def create_submission(db: AsyncSession = Depends(get_session)):
    ...
```

직접 `SessionLocal()` 호출 금지.

### LLM 호출

- 타임아웃: `settings.llm_timeout_seconds` (기본 300초)
- 모든 호출은 `services/` 레이어에서만 수행 (라우터에서 직접 호출 금지)
- 프롬프트 캐싱 적용 — 시스템 프롬프트는 `cache_control` 블록 사용

### 엔드포인트 규칙

- 모든 엔드포인트 접두사: `/api/v1/`
- 교사 대시보드: `X-Teacher-Password` 헤더 인증 (MVP 한정)
- 채점과 피드백은 **별도 필드**로 분리 응답 (처리 정책이 다름)
- 이미지 업로드: `multipart/form-data`, 텍스트 입력: `application/json`

### 신뢰도 게이트 임계값

```python
TRUST_THRESHOLD = float(os.getenv("TRUST_THRESHOLD", "0.75"))
SLA_HIGH_RISK_HOURS = int(os.getenv("SLA_HIGH_RISK_HOURS", "12"))
SLA_NORMAL_HOURS    = int(os.getenv("SLA_NORMAL_HOURS", "24"))
```

임계값을 코드에 직접 쓰지 말 것.

### 할루시네이션 탐지 방식

- **검증 대상**: AI가 생성한 개인화 피드백
- **검증 기준**: 피드백이 학생의 실제 오류를 정확히 짚고 올바른 교정 방향을 제시했는가
- **premise**: reference_solution + grading 결과 (어떤 단계가 틀렸는가)
- **hypothesis**: AI 생성 피드백
- **불일치율**: 3회 생성 피드백 간 오류 식별·교정 방향의 일관성
- 종합 신뢰도 = `0.6 * hhem_score + 0.4 * (1 - inconsistency_rate)`

## 환경변수 (.env)

```
DATABASE_URL=postgresql+asyncpg://user:pass@localhost/argus
ANTHROPIC_API_KEY=sk-...
GRADING_MODEL=claude-sonnet-4-6
FEEDBACK_MODEL=claude-sonnet-4-6
OCR_MODEL=pix2tex
TRUST_THRESHOLD=0.75
TEACHER_PASSWORD=...
SLA_HIGH_RISK_HOURS=12
SLA_NORMAL_HOURS=24
LLM_PROVIDER=anthropic
LLM_TIMEOUT_SECONDS=300
```
