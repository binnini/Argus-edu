# Argus

Argus는 서답형 수학 풀이를 대상으로 하는 교사 중심(HITL) 채점 시스템입니다.

- 학생: 텍스트/이미지로 풀이 제출
- 백엔드: 결정적 정오 판정 + 피드백 생성 + 할루시네이션 검증
- 교사: 검토 큐에서 승인/수정/거부

## 핵심 흐름

1. 학생이 `/api/v1/submissions`(텍스트) 또는 `/api/v1/submissions/image`(이미지)로 제출
2. 결정적 채점으로 `ai_score` 산출 (`graded` 상태)
3. durable job worker가 피드백 생성(job_type=`feedback`)
4. 이어서 할루시네이션 검증(job_type=`hallucination`)
5. 고신뢰도는 자동 승인 가능, 그 외는 교사 검토 큐에서 처리

## 기술 스택

- Backend: FastAPI, SQLAlchemy Async, Alembic, PostgreSQL
- Frontend: React 18, TypeScript, Vite, Tailwind
- OCR: `pix2tex` | `mathpix` | `got_ocr`
- LLM Provider: `anthropic` | `mlx` | `ollama`

## 디렉토리 구조

```text
Argus/
├── backend/               # FastAPI, 모델, 라우터, 서비스
├── frontend/              # React 앱
├── docs/                  # 프로젝트 문서
├── scripts/               # seed/benchmark/유틸 스크립트
├── deploy/                # 배포 설정(Nginx, launchd, cloudflared)
├── tests/                 # 통합/성능/타이밍 테스트
├── data/                  # 샘플/문제/실험 데이터
└── ocr_training/          # GOT-OCR 학습/평가 스크립트
```

## 로컬 실행

### 1) 환경 준비

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
```

```bash
cd frontend
npm ci
cd ..
```

### 2) 환경변수

```bash
cp .env.example .env
```

최소 필수값(개발 기준):

- `DATABASE_URL`
- `LLM_PROVIDER`
- `OCR_MODEL`
- `TEACHER_PASSWORD`
- (`LLM_PROVIDER=anthropic`이면) `ANTHROPIC_API_KEY`

### 3) DB 마이그레이션

```bash
cd backend
../.venv/bin/alembic upgrade head
cd ..
```

### 4) 백엔드 실행

```bash
cd backend
../.venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

### 5) 프론트엔드 실행

```bash
cd frontend
npm run dev
```

기본 접속:

- 학생 화면: `http://localhost:5173/student`
- 교사 화면: `http://localhost:5173/teacher`
- 헬스체크: `http://localhost:8000/health`

## 테스트

```bash
# 서버 실행 후
../.venv/bin/python -m pytest tests/test_deterministic_grading.py
../.venv/bin/python -m pytest tests/test_integration.py
```

## 배포

운영 배포 절차는 [docs/deployment.md](docs/deployment.md)를 참고하세요.

## 문서 인덱스

- API: [docs/api.md](docs/api.md)
- DB 스키마: [docs/schema.md](docs/schema.md)
- 배포: [docs/deployment.md](docs/deployment.md)
- 데이터셋: [docs/dataset.md](docs/dataset.md)
- 프론트엔드: [docs/frontend.md](docs/frontend.md)
- ADR: [docs/decisions.md](docs/decisions.md)
