#!/bin/bash
# ============================================
#  IVS - Internal Vibe Server (Start)
# ============================================
#
# Modes (selected by IVS_MODE env var, default: dev):
#   dev   – hot reload for both backend and frontend (local development)
#           Backend: uvicorn --reload     Frontend: next dev
#   prod  – production mode (use on the NAS / deploy host)
#           Backend: uvicorn (no reload)  Frontend: next start (pre-built)
#
# Example:
#   bash scripts/start-ivs.sh              # dev (default)
#   IVS_MODE=prod bash scripts/start-ivs.sh
# ============================================
clear

IVS_MODE="${IVS_MODE:-dev}"
if [ "$IVS_MODE" != "dev" ] && [ "$IVS_MODE" != "prod" ]; then
  echo "[!] Invalid IVS_MODE='$IVS_MODE' (expected: dev|prod). Falling back to dev."
  IVS_MODE="dev"
fi

echo "============================================"
echo "  IVS - Internal Vibe Server"
echo "  Enterprise Gateway for Vibe Code Apps"
echo "  Mode: $IVS_MODE"
echo "============================================"
echo ""

cd /Users/klod/IVS

# Kill existing if running
lsof -ti:8000 | xargs kill -9 2>/dev/null
lsof -ti:3000 | xargs kill -9 2>/dev/null
sleep 1

# ---- Start Backend ----
echo "[*] Starting Backend API (port 8000)..."
cd /Users/klod/IVS/backend
source venv/bin/activate
mkdir -p data deployed_apps uploads
# Auto-detect LAN IP
SERVER_IP=$(python3 -c "import socket; s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM); s.connect(('8.8.8.8',80)); print(s.getsockname()[0]); s.close()" 2>/dev/null || echo "127.0.0.1")
echo "[*] Server IP: $SERVER_IP"

# Reload only in dev mode — production should not have file-watcher overhead
UVICORN_FLAGS=""
if [ "$IVS_MODE" = "dev" ]; then
  UVICORN_FLAGS="--reload"
fi

UPLOAD_DIR=./uploads APPS_DIR=./deployed_apps COREDNS_CONFIG_PATH=../coredns SERVER_IP=$SERVER_IP \
  uvicorn app.main:app --host 0.0.0.0 --port 8000 $UVICORN_FLAGS &
BACKEND_PID=$!

# ---- Wait for Backend ----
echo "[*] Waiting for Backend..."
BACKEND_OK=false
for i in $(seq 1 30); do
  if curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/auth/login 2>/dev/null | grep -q "405\|200\|422"; then
    BACKEND_OK=true
    break
  fi
  sleep 1
  printf "."
done
echo ""

if [ "$BACKEND_OK" = true ]; then
  echo "[+] Backend API ready"
else
  echo "[!] Backend may not be ready yet (will continue anyway)"
fi

# ---- Start Frontend ----
echo "[*] Starting Frontend Dashboard (port 3000, mode=$IVS_MODE)..."
cd /Users/klod/IVS/frontend
if [ "$IVS_MODE" = "dev" ]; then
  # next dev: hot module reload, picks up file changes automatically.
  # No pre-build required.
  BACKEND_URL=http://localhost:8000 npx next dev -p 3000 &
else
  # next start: serves the pre-built .next/ directory. Build first if missing
  # or stale, then start. Production: faster runtime, no file watcher.
  if [ ! -d ".next" ] || [ ! -f ".next/BUILD_ID" ]; then
    echo "[*] No build found — running 'npm run build' first..."
    npm run build || { echo "[!] Build failed"; exit 1; }
  fi
  BACKEND_URL=http://localhost:8000 npx next start -p 3000 &
fi
FRONTEND_PID=$!

# ---- Wait for Frontend ----
echo "[*] Waiting for Frontend..."
FRONTEND_OK=false
for i in $(seq 1 20); do
  HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/login 2>/dev/null)
  if [ "$HTTP_CODE" = "200" ]; then
    FRONTEND_OK=true
    break
  fi
  sleep 1
  printf "."
done
echo ""

# ---- Final Status ----
echo ""
echo "============================================"
if [ "$BACKEND_OK" = true ] && [ "$FRONTEND_OK" = true ]; then
  echo "  IVS is running!"
else
  echo "  IVS started (some services may still be loading)"
fi
echo "============================================"
echo ""
echo "  Dashboard:  http://localhost:3000"
echo "  API:        http://localhost:8000"
echo "  API Docs:   http://localhost:8000/docs"
echo "  LAN:        http://$SERVER_IP:3000"
echo ""
echo "  Login:  admin / admin123"
echo ""

# ---- Auto-open Browser ----
if [ "$BACKEND_OK" = true ] && [ "$FRONTEND_OK" = true ]; then
  echo "[+] Opening browser..."
  open "http://localhost:3000/dashboard"
else
  echo "[!] Skipping auto-open (services not fully ready)"
  echo "    Open manually: http://localhost:3000"
fi

echo ""
echo "  Press Ctrl+C to stop all services"
echo "============================================"
echo ""

# Wait and handle Ctrl+C
trap "echo ''; echo '[*] Stopping IVS...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; echo '[+] IVS stopped.'; exit 0" INT TERM

wait
