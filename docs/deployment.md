# 배포 가이드 — Mac Mini M4 + Cloudflare Tunnel

> ADR-019 참고. EC2 방안 철회 — Mac Mini M4 (24GB, Apple Silicon) 로컬 서빙으로 결정.

---

## 아키텍처 요약

```
인터넷
  └── Cloudflare (HTTPS/TLS 자동)
        └── Cloudflare Tunnel (cloudflared)
              └── Mac Mini M4 localhost:80
                    └── Nginx
                          ├── /api/*  → FastAPI uvicorn (127.0.0.1:8000)
                          ├── /data/* → 손글씨 이미지 정적 서빙
                          └── /*      → React SPA (dist/)
```

---

## 사전 요구사항

Mac Mini M4에서 아래를 설치해야 한다.

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

# Cloudflare Tunnel 클라이언트
brew install cloudflare/cloudflare/cloudflared
```

---

## 1. 환경변수 설정

프로젝트 루트에 `.env` 파일 생성:

```env
DATABASE_URL=postgresql+asyncpg://yebin@localhost/argus
ANTHROPIC_API_KEY=sk-ant-...
GRADING_MODEL=claude-sonnet-4-6
FEEDBACK_MODEL=claude-sonnet-4-6
OCR_MODEL=got_ocr
GOT_OCR_MODEL_PATH=/Users/yebin/workSpace/Argus/ocr_training/output/got_ocr_merged
TRUST_THRESHOLD=0.75
TEACHER_PASSWORD=<강력한 비밀번호>
SLA_HIGH_RISK_HOURS=12
SLA_NORMAL_HOURS=24
LLM_TIMEOUT_SECONDS=300
ALLOWED_ORIGINS=http://localhost,http://localhost:80
```

---

## 2. 자동 배포 스크립트

```bash
cd /Users/yebin/workSpace/Argus
bash deploy/setup.sh
```

스크립트가 수행하는 작업:
1. 로그 디렉토리 생성 (`logs/`)
2. Python 가상환경 + 의존성 설치
3. DB 마이그레이션 (`alembic upgrade head`)
4. AI-HUB 데이터 삽입 (`scripts/seed.py`)
5. 프론트엔드 빌드 (`npm run build`)
6. Nginx 설정 적용 + 재시작
7. 백엔드 launchd 서비스 등록 (부팅 시 자동 시작)
8. Cloudflare Tunnel 설정 안내 출력

---

## 3. Cloudflare Tunnel 설정 (수동)

```bash
# 1) Cloudflare 계정 인증
cloudflared tunnel login

# 2) 터널 생성 (1회)
cloudflared tunnel create argus
# → Tunnel ID 출력됨 (UUID 형식)

# 3) deploy/cloudflare-tunnel.yml 편집
#    <TUNNEL_ID>를 실제 UUID로, argus.yourdomain.com을 실제 도메인으로 교체

# 4) DNS CNAME 등록
cloudflared tunnel route dns argus argus.yourdomain.com

# 5) launchd 서비스 등록
cp deploy/com.cloudflare.cloudflared.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.cloudflare.cloudflared.plist
```

---

## 4. 서비스 상태 확인

```bash
# 백엔드 health check
curl http://localhost:8000/health

# 프론트엔드 (Nginx)
curl http://localhost/

# Cloudflare Tunnel 상태
cloudflared tunnel info argus

# launchd 서비스 상태
launchctl list | grep argus
launchctl list | grep cloudflared

# 로그 확인
tail -f logs/backend.log
tail -f logs/backend-error.log
tail -f logs/cloudflared.log
```

---

## 5. 서비스 수동 제어

```bash
# 백엔드 재시작
launchctl unload ~/Library/LaunchAgents/com.argus.backend.plist
launchctl load ~/Library/LaunchAgents/com.argus.backend.plist

# Nginx 재시작
brew services restart nginx

# Cloudflare Tunnel 재시작
launchctl unload ~/Library/LaunchAgents/com.cloudflare.cloudflared.plist
launchctl load ~/Library/LaunchAgents/com.cloudflare.cloudflared.plist
```

---

## 6. 업데이트 배포

코드 변경 후 재배포:

```bash
cd /Users/yebin/workSpace/Argus
git pull

# 백엔드만 변경된 경우
launchctl unload ~/Library/LaunchAgents/com.argus.backend.plist
launchctl load ~/Library/LaunchAgents/com.argus.backend.plist

# 프론트엔드 변경된 경우
cd frontend && npm run build

# DB 마이그레이션이 있는 경우
cd backend && ../.venv/bin/alembic upgrade head
```

---

## 파일 구조

```
deploy/
├── setup.sh                         자동 배포 스크립트
├── nginx.conf                        Nginx 서버 설정
├── com.argus.backend.plist          백엔드 launchd 서비스 (Mac)
├── com.cloudflare.cloudflared.plist  Tunnel launchd 서비스 (Mac)
├── argus-backend.service            백엔드 systemd 서비스 (Linux 참고용)
└── cloudflare-tunnel.yml            Cloudflare Tunnel 라우팅 설정
```
