## Local Setting

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

## Test

```bash
# 서버 실행 후
.venv/bin/python -m pytest tests/test_deterministic_grading.py
.venv/bin/python -m pytest tests/test_integration.py
```
