#!/bin/bash
# deploy/setup.sh — Argus Mac Mini M4 배포 설정 스크립트
# 사용법: bash deploy/setup.sh
# 전제: .env 파일, PostgreSQL, Node.js, Python 3.11+, Nginx, Homebrew 설치 완료

set -euo pipefail

ARGUS_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOGS_DIR="$ARGUS_DIR/logs"

echo "=== Argus 배포 설정 시작 ==="
echo "프로젝트 경로: $ARGUS_DIR"

# 1. 로그 디렉토리 생성
mkdir -p "$LOGS_DIR"
echo "[1/8] 로그 디렉토리 생성 완료: $LOGS_DIR"

# 2. Python 가상환경 + 의존성
cd "$ARGUS_DIR"
if [ ! -d ".venv" ]; then
    python3.11 -m venv .venv
fi
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r backend/requirements.txt
echo "[2/8] Python 의존성 설치 완료"

# 3. DB 마이그레이션
cd "$ARGUS_DIR/backend"
../.venv/bin/alembic upgrade head
echo "[3/8] DB 마이그레이션 완료"

# 4. AI-HUB 데이터 삽입 (seed.py)
if [ -f "$ARGUS_DIR/scripts/seed.py" ]; then
    cd "$ARGUS_DIR"
    .venv/bin/python scripts/seed.py
    echo "[4/8] 데이터 삽입 완료"
else
    echo "[4/8] seed.py 없음 — 건너뜀"
fi

# 5. 프론트엔드 빌드
cd "$ARGUS_DIR/frontend"
npm ci --quiet
npm run build
echo "[5/8] 프론트엔드 빌드 완료"

# 6. Nginx 설정 적용
NGINX_SITES="/opt/homebrew/etc/nginx/servers"
if [ -d "$NGINX_SITES" ]; then
    cp "$ARGUS_DIR/deploy/nginx.conf" "$NGINX_SITES/argus.conf"
    nginx -t && brew services restart nginx
    echo "[6/8] Nginx 설정 적용 완료"
else
    echo "[6/8] Nginx servers 디렉토리를 찾을 수 없음 — 수동으로 $ARGUS_DIR/deploy/nginx.conf 적용 필요"
fi

# 7. 백엔드 launchd 서비스 등록
PLIST_SRC="$ARGUS_DIR/deploy/com.argus.backend.plist"
PLIST_DST="$HOME/Library/LaunchAgents/com.argus.backend.plist"
cp "$PLIST_SRC" "$PLIST_DST"
launchctl unload "$PLIST_DST" 2>/dev/null || true
launchctl load "$PLIST_DST"
echo "[7/8] 백엔드 launchd 서비스 등록 완료"

# 8. Cloudflare Tunnel 설정 안내
echo "[8/8] Cloudflare Tunnel 설정 안내:"
echo "  1. cloudflared 설치: brew install cloudflare/cloudflare/cloudflared"
echo "  2. 터널 생성: cloudflared tunnel login && cloudflared tunnel create argus"
echo "  3. deploy/cloudflare-tunnel.yml 에서 <TUNNEL_ID>와 도메인 교체"
echo "  4. DNS 설정: cloudflared tunnel route dns argus argus.yourdomain.com"
echo "  5. 서비스 등록:"
echo "     cp deploy/com.cloudflare.cloudflared.plist ~/Library/LaunchAgents/"
echo "     launchctl load ~/Library/LaunchAgents/com.cloudflare.cloudflared.plist"

echo ""
echo "=== 배포 설정 완료 ==="
echo "백엔드 상태 확인: curl http://localhost:8000/health"
echo "프론트엔드 확인: open http://localhost"
