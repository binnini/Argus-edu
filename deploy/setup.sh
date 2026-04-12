#!/bin/bash
# deploy/setup.sh — Argus Mac Mini M4 배포 설정 스크립트
# 사용법: bash deploy/setup.sh
# 전제: .env 파일, PostgreSQL, Node.js, Python 3.11+, Nginx, Homebrew, conda 설치 완료

set -euo pipefail

ARGUS_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOGS_DIR="$ARGUS_DIR/logs"
CONDA_BASE="$(conda info --base 2>/dev/null || echo "$HOME/miniconda3")"

echo "=== Argus 배포 설정 시작 ==="
echo "프로젝트 경로: $ARGUS_DIR"

# .env 파일 존재 확인
if [ ! -f "$ARGUS_DIR/.env" ]; then
    echo "오류: $ARGUS_DIR/.env 파일이 없습니다."
    echo "  .env.example을 복사하고 값을 채운 뒤 다시 실행하세요:"
    echo "  cp $ARGUS_DIR/.env.example $ARGUS_DIR/.env"
    exit 1
fi

# 1. 로그 디렉토리 생성
mkdir -p "$LOGS_DIR"
echo "[1/9] 로그 디렉토리 생성 완료: $LOGS_DIR"

# 2. Python 가상환경 + 의존성 (메인 FastAPI + MLX)
cd "$ARGUS_DIR"
if [ ! -d ".venv" ]; then
    python3.11 -m venv .venv
fi
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r backend/requirements.txt
echo "[2/9] Python 의존성 설치 완료 (메인 환경)"

# 2-b. GOT-OCR 전용 conda 환경 생성 (ADR-027: transformers 버전 분리)
# mlx-lm은 transformers>=5.0 필요, GOT-OCR는 4.44.2 필요 → 별도 환경으로 격리
if conda env list | grep -q "^argus-gotocr"; then
    echo "[2b/9] argus-gotocr 환경 이미 존재 — 건너뜀"
else
    echo "[2b/9] argus-gotocr conda 환경 생성 중 (GOT-OCR, transformers 4.44.2)..."
    conda create -n argus-gotocr python=3.11 -y
    "$CONDA_BASE/envs/argus-gotocr/bin/pip" install -q \
        "transformers==4.44.2" \
        "torch==2.4.0" \
        "torchvision==0.19.0" \
        "Pillow>=10.0" \
        "tiktoken>=0.7" \
        "timm==0.5.4" \
        "einops>=0.8" \
        "accelerate>=0.33" \
        "verovio"
    echo "[2b/9] argus-gotocr 환경 생성 완료"
fi

# 3. DB 마이그레이션
cd "$ARGUS_DIR/backend"
../.venv/bin/alembic upgrade head
echo "[3/9] DB 마이그레이션 완료"

# 4. AI-HUB 데이터 삽입 (seed.py)
if [ -f "$ARGUS_DIR/scripts/seed.py" ]; then
    cd "$ARGUS_DIR"
    .venv/bin/python scripts/seed.py
    echo "[4/9] 데이터 삽입 완료"
else
    echo "[4/9] seed.py 없음 — 건너뜀"
fi

# 5. 프론트엔드 빌드
cd "$ARGUS_DIR/frontend"
npm ci --quiet
npm run build
echo "[5/9] 프론트엔드 빌드 완료"

# 6. Nginx 설정 적용 (__ARGUS_DIR__ 플레이스홀더 → 실제 경로 치환)
NGINX_SITES="/opt/homebrew/etc/nginx/servers"
if [ -d "$NGINX_SITES" ]; then
    sed "s|__ARGUS_DIR__|$ARGUS_DIR|g" \
        "$ARGUS_DIR/deploy/nginx.conf" > "$NGINX_SITES/argus.conf"
    nginx -t && brew services restart nginx
    echo "[6/9] Nginx 설정 적용 완료"
else
    echo "[6/9] Nginx servers 디렉토리를 찾을 수 없음 — 수동으로 아래 명령 실행:"
    echo "  sed 's|__ARGUS_DIR__|$ARGUS_DIR|g' \\"
    echo "    $ARGUS_DIR/deploy/nginx.conf > /your/nginx/servers/argus.conf"
fi

# 7. 백엔드 launchd 서비스 등록 (__ARGUS_DIR__ 플레이스홀더 → 실제 경로 치환)
PLIST_DST="$HOME/Library/LaunchAgents/com.argus.backend.plist"
sed "s|__ARGUS_DIR__|$ARGUS_DIR|g" \
    "$ARGUS_DIR/deploy/com.argus.backend.plist" > "$PLIST_DST"
launchctl unload "$PLIST_DST" 2>/dev/null || true
launchctl load "$PLIST_DST"
echo "[7/9] 백엔드 launchd 서비스 등록 완료"

# 8. Cloudflare Tunnel 설정 안내
echo "[8/9] Cloudflare Tunnel 설정:"
echo "  1. cloudflared 설치:  brew install cloudflare/cloudflare/cloudflared"
echo "  2. 인증 + 터널 생성:  cloudflared tunnel login"
echo "                         cloudflared tunnel create argus"
echo "  3. 터널 ID + 도메인 교체:"
echo "     $ARGUS_DIR/deploy/cloudflare-tunnel.yml 에서 <TUNNEL_ID>와 도메인 수정"
echo "  4. DNS 레코드 등록:   cloudflared tunnel route dns argus argus.yourdomain.com"
echo "  5. launchd 서비스 등록:"
CFPLIST_DST="$HOME/Library/LaunchAgents/com.cloudflare.cloudflared.plist"
echo "     sed 's|__ARGUS_DIR__|$ARGUS_DIR|g' \\"
echo "       $ARGUS_DIR/deploy/com.cloudflare.cloudflared.plist > $CFPLIST_DST"
echo "     launchctl load $CFPLIST_DST"

echo "[9/9] GOT-OCR 워커 정보:"
echo "  argus-gotocr Python: $CONDA_BASE/envs/argus-gotocr/bin/python"
echo "  ocr_worker.py:       $ARGUS_DIR/backend/scripts/ocr_worker.py"
echo "  .env에 설정 필요:    GOT_OCR_WORKER_PYTHON=$CONDA_BASE/envs/argus-gotocr/bin/python"
echo "  (워커는 첫 이미지 제출 시 자동 시작됩니다)"

echo ""
echo "=== 배포 설정 완료 ==="
echo "백엔드 상태 확인: curl http://localhost:8000/health"
echo "프론트엔드 확인:  open http://localhost"
