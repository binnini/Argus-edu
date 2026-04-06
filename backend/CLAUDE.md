# Backend — 개발 규칙

FastAPI + PostgreSQL 백엔드. 루트 CLAUDE.md의 제약이 모두 적용됨.

## 프로젝트 구조

```
backend/
├── main.py                  # FastAPI 앱 + lifespan 이벤트
├── config.py                # 환경변수 로딩 (모델명, 임계값 등)
├── db.py                    # PostgreSQL 세션 + 의존성 주입
├── routers/
│   ├── submissions.py       # POST /api/v1/submissions
│   ├── teacher.py           # GET/POST /api/v1/teacher/*
│   └── feedback.py          # GET /api/v1/feedback/*
├── services/
│   ├── grading.py           # Claude API 채점 + SBERT 보조
│   ├── explanation.py       # 풀이 설명 생성 (멀티 샘플링)
│   ├── hallucination.py     # HHEM-2.1-Open 탐지
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
    app.state.hhem = pipeline("text-classification", model="vectara/hallucination_evaluation_model")
    app.state.sbert = SentenceTransformer("all-MiniLM-L6-v2")
    yield
```

HHEM + SBERT 동시 로드 시 약 2GB RAM 사용 (t3.medium 한계). 절대 요청 핸들러 내에서 로드하지 말 것.

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

### Claude API 호출

- 타임아웃: 30초
- 실패 시 재시도 큐에 적재 (즉시 에러 반환 금지)
- 모든 호출은 `services/` 레이어에서만 수행 (라우터에서 직접 호출 금지)
- 프롬프트 캐싱 적용 — 시스템 프롬프트는 `cache_control` 블록 사용

### 엔드포인트 규칙

- 모든 엔드포인트 접두사: `/api/v1/`
- 교사 대시보드: `X-Teacher-Password` 헤더 인증 (MVP 한정)
- 채점과 풀이 설명은 **별도 필드**로 분리 응답 (처리 정책이 다름)

### 신뢰도 게이트 임계값

```python
TRUST_THRESHOLD = float(os.getenv("TRUST_THRESHOLD", "0.75"))
SLA_HIGH_RISK_HOURS = int(os.getenv("SLA_HIGH_RISK_HOURS", "12"))
SLA_NORMAL_HOURS    = int(os.getenv("SLA_NORMAL_HOURS", "24"))
```

임계값을 코드에 직접 쓰지 말 것.

### 할루시네이션 탐지 방식

- **채점**: HHEM 스코어 + SBERT 유사도 → reference_solution과 비교
- **풀이 설명**: 동일 문제 3회 생성 → 불일치 구간 탐지 → 불일치율을 신뢰도에 반영
- 종합 신뢰도 = `0.6 * hhem_score + 0.4 * (1 - inconsistency_rate)`

## 환경변수 (.env)

```
DATABASE_URL=postgresql+asyncpg://user:pass@localhost/argus
ANTHROPIC_API_KEY=sk-...
GRADING_MODEL=claude-sonnet-4-6
EXPLANATION_MODEL=claude-sonnet-4-6
TRUST_THRESHOLD=0.75
TEACHER_PASSWORD=...
SLA_HIGH_RISK_HOURS=12
SLA_NORMAL_HOURS=24
```
