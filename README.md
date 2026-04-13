# Argus


## Live Domain

- [학생 대시보드 Live URL](https://americans-fancy-aside-handheld.trycloudflare.com/student)
- 테스트 이름 : 김민준
- 테스트 학번 : 20240001
![학생 로그인 화면](./ui/student-login.png "학생 로그인 화면")

- [교사 대시보드 Live URL](https://americans-fancy-aside-handheld.trycloudflare.com/student) (비밀번호 : argus)
![교사 로그인 화면](./ui/teacher-login.png "교사 로그인 화면")


## System Flow

1. 학생이 `/api/v1/submissions`(텍스트) 또는 `/api/v1/submissions/image`(이미지)로 제출
2. 단순 정오 판단 채점으로 `ai_score` 산출 (`graded`)
3. Gemma4:E2B가 피드백 생성 (job_type=`feedback`)
4. 이후 Gemma4:E2B가 해당 피드백에 대한 할루시네이션을 검증(job_type=`hallucination`), 풀이의 신뢰도 반환
5. 높은 신뢰도의 피드백은 자동 승인되어 학생에게 공개, 그 외는 교사가 검토 큐에서 승인 여부 처리

## Tech Stack

- Backend: FastAPI, SQLAlchemy Async, Alembic, PostgreSQL
- Frontend: React 18, TypeScript, Vite, Tailwind
- OCR: `got_ocr-2.0`
- LLM Provider: `anthropic` | `mlx` | `ollama`
- LLM : Gemma4:E2B


## OCR Data

- [AI-Hub: 수식,도형,낙서기호 OCR 데이터](https://aihub.or.kr/aihubdata/data/view.do?currMenu=115&topMenu=100&dataSetSn=479)
- [AI-Hub: 수학 과목 자동 풀이 데이터](https://aihub.or.kr/aihubdata/data/view.do?currMenu=115&topMenu=100&dataSetSn=71716)



## Directory
```text
Argus/
├── backend/               # FastAPI, 모델, 라우터, 서비스
├── data/                  # 샘플/문제/실험 데이터
├── demo/                  # MVP 정답 입력 샘플 데이터
├── frontend/              # React 앱
├── docs/                  # 프로젝트 문서
├── scripts/               # seed/benchmark/유틸 스크립트
├── deploy/                # 배포 설정(Nginx, launchd, cloudflared)
├── tests/                 # 통합/성능/타이밍 테스트
└── ocr_training/          # GOT-OCR 학습/평가 스크립트
```


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
../.venv/bin/python -m pytest tests/test_deterministic_grading.py
../.venv/bin/python -m pytest tests/test_integration.py
```

## Deployment

운영 배포 절차는 [docs/deployment.md](docs/deployment.md)를 참고하세요.

## 문서 인덱스

- API: [docs/api.md](docs/api.md)
- DB 스키마: [docs/schema.md](docs/schema.md)
- 배포: [docs/deployment.md](docs/deployment.md)
- 데이터셋: [docs/dataset.md](docs/dataset.md)
- 프론트엔드: [docs/frontend.md](docs/frontend.md)
- ADR: [docs/decisions.md](docs/decisions.md)
- 작업 관리: [./TODO.md](./TODO.md)
