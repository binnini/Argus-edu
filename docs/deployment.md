# 배포 가이드 — Mac Mini M4 + Cloudflare Tunnel

> ADR-019 참고. EC2 방안 철회 — Mac Mini M4 (24GB, Apple Silicon) 로컬 서빙으로 결정.

---

## 아키텍처

```
인터넷 (HTTPS)
  └── Cloudflare (TLS 자동 처리)
        └── Cloudflare Tunnel (cloudflared)
              └── Mac Mini M4 localhost:80
                    └── Nginx
                          ├── /api/*      → FastAPI (127.0.0.1:8000)
                          ├── /uploads/*  → 학생 업로드 이미지 (정적)
                          ├── /data/*     → AI-HUB 샘플 이미지 (정적)
                          └── /*          → React SPA (frontend/dist/)
```

---

## 단계 체크리스트

### Step 0. 사전 요구사항 확인

Mac Mini M4에 아래가 설치되어 있어야 합니다.

```bash
# Homebrew
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Python 3.11
brew install python@3.11

# Node.js 20+
brew install node

# PostgreSQL 16
brew install postgresql@16
brew services start postgresql@16

# Nginx
brew install nginx

# Miniconda (GOT-OCR 전용 conda 환경 필요 — ADR-027)
# 이미 설치된 경우 건너뜀
brew install --cask miniconda
conda init zsh   # 또는 conda init bash

# Cloudflare Tunnel 클라이언트
brew install cloudflare/cloudflare/cloudflared
```

설치 확인:

```bash
python3.11 --version   # Python 3.11.x
node --version         # v20.x 이상
psql --version         # psql (PostgreSQL) 16.x
nginx -v               # nginx/1.x.x
conda --version        # conda 24.x 이상
cloudflared --version  # cloudflared 2024.x.x
```

---

### Step 1. 코드 체크아웃

```bash
# 배포할 경로에 클론 (경로는 자유롭게 설정 가능)
git clone https://github.com/your-org/argus.git /path/to/argus
cd /path/to/argus

# main 브랜치 최신 상태로
git checkout main && git pull
```

---

### Step 2. PostgreSQL 16 실행 확인

```bash
# PostgreSQL 16 시작
brew services start postgresql@16

# 실행 확인
/opt/homebrew/opt/postgresql@16/bin/pg_isready -h localhost -p 5432

# 실제 5432 서버가 PostgreSQL 16인지 확인
/opt/homebrew/opt/postgresql@16/bin/psql \
  -h localhost -p 5432 -d postgres \
  -c "SELECT version();"
```

`deploy/setup.sh`가 `argus` role/database를 idempotent하게 생성하므로, 수동으로 `createuser`/`createdb`를 실행할 필요는 없습니다.
이미 `postgresql@15`가 5432 포트를 점유하고 있으면 16이 시작되지 않습니다. 이 경우 `brew services stop postgresql@15` 후 `postgresql@16`을 시작하세요.

---

### Step 3. 환경변수 설정 (.env)

```bash
cp .env.example .env
```

`.env`를 열어 아래 항목을 실제 값으로 채웁니다.

| 항목 | 설명 | 예시 |
|---|---|---|
| `DATABASE_URL` | PostgreSQL 접속 URL | `postgresql+asyncpg://argus@localhost/argus` |
| `ANTHROPIC_API_KEY` | Claude API 키 (LLM_PROVIDER=anthropic 시 필수) | `sk-ant-...` |
| `LLM_PROVIDER` | LLM 제공자 | `mlx` (Mac Mini M4 권장) |
| `MLX_MODEL_PATH` | MLX 모델 경로 또는 HuggingFace ID | `unsloth/gemma-4-E4B-it-MLX-8bit` |
| `EMBEDDING_MODEL_NAME` | 유사도 계산용 임베딩 모델 | `sentence-transformers/all-MiniLM-L6-v2` |
| `OCR_MODEL` | OCR 엔진 선택 | `got_ocr` |
| `GOT_OCR_MODEL_PATH` | GOT-OCR merged 모델 절대경로 | `/path/to/argus/ocr_training/output/got_ocr_merged` |
| `GOT_OCR_WORKER_PYTHON` | argus-gotocr conda 환경 Python | 없으면 `setup.sh`가 자동 추가 |
| `TEACHER_PASSWORD` | 교사 대시보드 비밀번호 | 테스트 배포: `argus` |
| `ALLOWED_ORIGINS` | CORS 허용 도메인 | `https://argus.yourdomain.com` |
| `VITE_API_BASE` | 프론트엔드 API 경로 | `/api/v1` |

> **주의**: `.env`는 절대 git에 커밋하지 마세요. `.gitignore`에 포함되어 있습니다.

테스트 배포용 최소 예시:

```env
DATABASE_URL=postgresql+asyncpg://argus@localhost/argus
TEACHER_PASSWORD=argus
LLM_PROVIDER=mlx
GRADING_MODEL=gemma4:e4b
FEEDBACK_MODEL=gemma4:e4b
EMBEDDING_MODEL_NAME=sentence-transformers/all-MiniLM-L6-v2
OCR_MODEL=got_ocr
GOT_OCR_MODEL_PATH=/Users/yebin/workSpace/Argus/ocr_training/output/got_ocr_merged
VITE_API_BASE=/api/v1
```

---

### Step 4. 자동 배포 스크립트 실행

```bash
bash deploy/setup.sh
```

초기 배포에서 AI-HUB 문제 데이터를 삽입해야 하면 `RUN_SEED=1`을 붙입니다.

```bash
RUN_SEED=1 bash deploy/setup.sh
```

이미 seed를 수행한 운영 DB에서는 `RUN_SEED=1` 없이 실행하세요. `scripts/seed.py`는 `problems`를 truncate cascade 하므로 운영 제출/채점 데이터가 있으면 위험합니다.

스크립트가 순서대로 수행하는 작업:

| 단계 | 내용 |
|---|---|
| 시작 | `.env` 로드 + 필수 환경변수 검증 |
| 1/9 | `logs/` 디렉토리 생성 |
| 2/9 | Python `.venv` 생성 + `backend/requirements.txt` 설치 |
| 2b/9 | `argus-gotocr` conda 환경 생성 (GOT-OCR 전용, transformers 4.44.2) |
| 2c/9 | `GOT_OCR_WORKER_PYTHON` 자동 추가/검증 |
| 3/9 | PostgreSQL 16 readiness/version 확인, `argus` role/database 생성, `alembic upgrade head` |
| 4/9 | `RUN_SEED=1`일 때만 `scripts/seed.py` 실행 |
| 5/9 | `npm ci && npm run build` — React 프론트엔드 빌드 |
| 6/9 | `nginx.conf` 경로 치환 후 Nginx 서버에 복사 + 재시작 |
| 7/9 | `com.argus.backend.plist` 경로 치환 후 launchd 등록 |
| 8/9 | Cloudflare Tunnel 설정 안내 출력 |
| 9/9 | GOT-OCR 워커 Python 경로 확인 |

`setup.sh`는 `DATABASE_URL`을 Alembic과 seed 실행에 명시적으로 주입합니다. `.env`에 `GOT_OCR_WORKER_PYTHON`이 없으면 `argus-gotocr` conda 환경의 Python 경로를 자동으로 추가합니다.

---

### Step 5. Cloudflare Tunnel 설정

```bash
# 1) Cloudflare 계정 인증 (브라우저 열림)
cloudflared tunnel login

# 2) 터널 생성 (1회만 실행)
cloudflared tunnel create argus
# → Tunnel ID (UUID) 출력됨 — 기록해 두세요
```

`deploy/cloudflare-tunnel.yml`을 열어 두 곳을 교체합니다:

```yaml
tunnel: <TUNNEL_ID>           # ← 실제 UUID로 교체
credentials-file: /Users/<your-username>/.cloudflared/<TUNNEL_ID>.json

ingress:
  - hostname: argus.yourdomain.com   # ← 실제 도메인으로 교체
    service: http://localhost:80
  - service: http_status:404
```

```bash
# 3) DNS CNAME 등록
cloudflared tunnel route dns argus argus.yourdomain.com

# 4) launchd 서비스 등록 (__ARGUS_DIR__ 치환 포함)
ARGUS_DIR="$(pwd)"
sed "s|__ARGUS_DIR__|$ARGUS_DIR|g" \
    deploy/com.cloudflare.cloudflared.plist \
    > ~/Library/LaunchAgents/com.cloudflare.cloudflared.plist

launchctl load ~/Library/LaunchAgents/com.cloudflare.cloudflared.plist
```

---

### Step 6. 최종 동작 확인

```bash
# 백엔드 health check
curl http://localhost:8000/health
# 기대 응답: {"status":"ok"}

# Nginx 서빙 확인
curl -I http://localhost/
# 기대 응답: HTTP/1.1 200 OK

# launchd 서비스 상태
launchctl list | grep argus          # com.argus.backend 항목 확인
launchctl list | grep cloudflared    # com.cloudflare.cloudflared 항목 확인

# Cloudflare Tunnel 연결 상태
cloudflared tunnel info argus

# 외부 HTTPS 접속 확인
curl https://argus.yourdomain.com/health
```

모든 확인이 통과하면 배포 완료입니다.

---

## 운영

### 로그 확인

```bash
# 백엔드 실시간 로그
tail -f logs/backend.log
tail -f logs/backend-error.log

# Cloudflare Tunnel 로그
tail -f logs/cloudflared.log
```

### 서비스 수동 재시작

```bash
# 백엔드
launchctl unload ~/Library/LaunchAgents/com.argus.backend.plist
launchctl load  ~/Library/LaunchAgents/com.argus.backend.plist

# Nginx
brew services restart nginx

# Cloudflare Tunnel
launchctl unload ~/Library/LaunchAgents/com.cloudflare.cloudflared.plist
launchctl load  ~/Library/LaunchAgents/com.cloudflare.cloudflared.plist
```

### 코드 업데이트 배포

```bash
git pull

# 백엔드 코드만 변경된 경우
launchctl unload ~/Library/LaunchAgents/com.argus.backend.plist
launchctl load  ~/Library/LaunchAgents/com.argus.backend.plist

# DB 마이그레이션이 포함된 경우
cd backend && DATABASE_URL="$DATABASE_URL" ../.venv/bin/alembic upgrade head
launchctl unload ~/Library/LaunchAgents/com.argus.backend.plist
launchctl load  ~/Library/LaunchAgents/com.argus.backend.plist

# 프론트엔드 코드가 변경된 경우
cd frontend && npm ci && npm run build
# (Nginx는 재시작 불필요 — dist/ 파일을 직접 서빙)
```

운영 업데이트에서는 보통 `bash deploy/setup.sh`를 다시 실행해도 됩니다. 문제 데이터 초기 삽입이 필요한 경우에만 `RUN_SEED=1`을 붙이세요.

---

## 트러블슈팅

### 백엔드가 시작되지 않는 경우

```bash
# 에러 로그 확인
tail -50 logs/backend-error.log

# 포트 충돌 확인
lsof -i :8000

# 수동으로 직접 실행해 에러 확인
cd backend && ../.venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000
```

### OCR 상태가 error로 나오는 경우

```bash
# GOT-OCR 워커 Python 경로 확인
ls -la "$GOT_OCR_WORKER_PYTHON"

# argus-gotocr conda 환경 패키지 확인
conda run -n argus-gotocr pip list | grep -E "transformers|torch|timm"
# transformers 4.44.2, torch 2.4.0 이어야 함

# 워커 단독 실행 테스트
$GOT_OCR_WORKER_PYTHON backend/scripts/ocr_worker.py \
    --model-path "$GOT_OCR_MODEL_PATH"
# {"ready": true} 출력되면 정상
```

### Cloudflare Tunnel이 연결되지 않는 경우

```bash
# Tunnel 상태 확인
cloudflared tunnel info argus

# credentials 파일 존재 확인
ls ~/.cloudflared/

# 수동으로 tunnel 실행해 에러 확인
cloudflared tunnel --config deploy/cloudflare-tunnel.yml run
```

### Nginx 503 오류

```bash
# FastAPI 백엔드가 실행 중인지 확인
curl http://127.0.0.1:8000/health

# Nginx 설정 검증
nginx -t

# Nginx 에러 로그
tail -20 /opt/homebrew/var/log/nginx/error.log
```

---

## 배포 파일 구조

```
deploy/
├── setup.sh                         자동 배포 스크립트 (1회 실행)
├── nginx.conf                        Nginx 설정 템플릿 (__ARGUS_DIR__ 플레이스홀더)
├── com.argus.backend.plist          백엔드 launchd 서비스 템플릿
├── com.cloudflare.cloudflared.plist  Tunnel launchd 서비스 템플릿
├── cloudflare-tunnel.yml            Cloudflare Tunnel 라우팅 설정
└── argus-backend.service            systemd 서비스 (Linux 참고용)
```

> `nginx.conf`와 두 `.plist` 파일은 **템플릿**입니다.
> `setup.sh`가 `__ARGUS_DIR__`를 실제 경로로 치환한 뒤 복사합니다.
> 직접 편집하지 마세요 — 다음 배포 시 `setup.sh`가 덮어씁니다.
