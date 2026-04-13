# 배포 가이드 (Mac Mini + Cloudflare Tunnel)

이 문서는 현재 `deploy/setup.sh` 기준의 실제 배포 절차를 설명합니다.

## 아키텍처

```text
Internet (HTTPS)
  -> Cloudflare
    -> cloudflared tunnel
      -> localhost:80 (Nginx)
        -> /api/*    -> FastAPI (127.0.0.1:8000)
        -> /uploads/* (정적)
        -> /data/*    (정적)
        -> /*         -> frontend/dist (SPA)
```

## 사전 요구사항

- macOS (Apple Silicon 권장)
- Homebrew
- Python 3.11
- Node.js 20+
- PostgreSQL 16
- nginx
- Miniconda (GOT-OCR 분리 환경)
- cloudflared

설치 예시:

```bash
brew install python@3.11 node postgresql@16 nginx
brew install --cask miniconda
brew install cloudflare/cloudflare/cloudflared
```

## 1) 코드 준비

```bash
git clone <repo-url> /path/to/argus
cd /path/to/argus
```

## 2) PostgreSQL 16 확인

```bash
brew services start postgresql@16
/opt/homebrew/opt/postgresql@16/bin/pg_isready -h localhost -p 5432
```

`setup.sh`는 5432에서 PostgreSQL 16이 동작한다고 가정합니다.

## 3) `.env` 준비

```bash
cp .env.example .env
```

`deploy/setup.sh` 기준 필수 환경변수:
- `DATABASE_URL`
- `TEACHER_PASSWORD`
- `LLM_PROVIDER`
- `GRADING_MODEL`
- `OCR_MODEL`
- `GOT_OCR_MODEL_PATH`

주의:
- `TEACHER_PASSWORD`는 `argus-dev`/`changeme` 불가
- `.env`는 절대 커밋 금지

## 4) 자동 배포 실행

```bash
bash deploy/setup.sh
```

초기 데이터 시드가 필요할 때만:

```bash
RUN_SEED=1 bash deploy/setup.sh
```

`RUN_SEED=1`은 `scripts/seed.py`를 실행하며 `problems`를 truncate 하므로 운영 DB에서는 신중히 사용하세요.

### setup.sh가 수행하는 작업

1. `.env` 로드 + 필수 env 검증
2. `.venv` 생성/의존성 설치
3. `argus-gotocr` conda 환경 생성 (없을 때)
4. DB role/database 준비 + `alembic upgrade head`
5. (옵션) seed
6. `frontend` 빌드
7. nginx 설정 배치
8. backend launchd 등록
9. cloudflared 설정 안내 출력

## 5) Cloudflare Tunnel 설정

```bash
cloudflared tunnel login
cloudflared tunnel create argus
```

`deploy/cloudflare-tunnel.yml`에서:
- `<TUNNEL_ID>` 교체
- 도메인(`argus.yourdomain.com`) 교체

DNS 연결:

```bash
cloudflared tunnel route dns argus argus.yourdomain.com
```

launchd 등록:

```bash
ARGUS_DIR="$(pwd)"
sed "s|__ARGUS_DIR__|$ARGUS_DIR|g" deploy/com.cloudflare.cloudflared.plist \
  > ~/Library/LaunchAgents/com.cloudflare.cloudflared.plist
launchctl load ~/Library/LaunchAgents/com.cloudflare.cloudflared.plist
```

## 6) 검증

```bash
curl http://localhost:8000/health
curl -I http://localhost/
launchctl list | grep com.argus.backend
launchctl list | grep com.cloudflare.cloudflared
```

`/health`는 `status`, `memory_mb`, `queues`를 반환합니다.

## 운영 명령

로그 확인:

```bash
tail -f logs/backend.log
tail -f logs/backend-error.log
tail -f logs/cloudflared.log
tail -f logs/cloudflared-error.log
```

서비스 재기동:

```bash
launchctl unload ~/Library/LaunchAgents/com.argus.backend.plist
launchctl load ~/Library/LaunchAgents/com.argus.backend.plist
brew services restart nginx
```

## 트러블슈팅

### 백엔드 미기동

```bash
tail -50 logs/backend-error.log
lsof -i :8000
cd backend && ../.venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000
```

### OCR 실패

```bash
ls -la "$GOT_OCR_WORKER_PYTHON"
conda run -n argus-gotocr pip list | grep -E "transformers|torch|timm"
$GOT_OCR_WORKER_PYTHON backend/scripts/ocr_worker.py --model-path "$GOT_OCR_MODEL_PATH"
```

### Tunnel 연결 실패

```bash
cloudflared tunnel info argus
cloudflared tunnel --config deploy/cloudflare-tunnel.yml run
```

### Nginx 503

```bash
curl http://127.0.0.1:8000/health
nginx -t
tail -20 /opt/homebrew/var/log/nginx/error.log
```
