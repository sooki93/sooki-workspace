#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
PROJECT_ROOT="$PWD"
STUDIO_URL="http://127.0.0.1:${STUDIO_PORT:-3011}"
if curl --silent --max-time 2 "http://127.0.0.1:${STUDIO_BACKEND_PORT:-8011}/health" | grep -q 'attheroom-studio'; then
  printf '이미 실행 중인 작업실: %s\n' "$STUDIO_URL"
  if command -v open >/dev/null; then open "$STUDIO_URL"; fi
  exit 0
fi
if [[ -z "${PYTHON_BIN:-}" ]]; then
  if command -v python3.12 >/dev/null; then PYTHON_BIN=python3.12
  elif [[ -x "$HOME/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3" ]]; then PYTHON_BIN="$HOME/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3"
  else PYTHON_BIN=python3; fi
fi
"$PYTHON_BIN" -c 'import sys; assert sys.version_info >= (3,12), "Python 3.12 이상이 필요합니다."'
if [[ ! -d .venv ]]; then "$PYTHON_BIN" -m venv .venv; fi
.venv/bin/python -m pip install -q -r backend/requirements.lock.txt
(cd frontend && npm ci --cache "$PROJECT_ROOT/.local-cache/npm" --no-audit --no-fund)
export FRONTEND_ORIGIN="http://127.0.0.1:${STUDIO_PORT:-3011}"
export BACKEND_URL="http://127.0.0.1:${STUDIO_BACKEND_PORT:-8011}"
export DEMO_MODE=true APP_ENV=development STORAGE_BACKEND=local
export AI_PROVIDER=codex DEMO_AI_ENABLED="${DEMO_AI_ENABLED:-true}"
export DATABASE_URL="sqlite:///$PROJECT_ROOT/.local-cache/demo.db"
export UPLOAD_DIR="$PROJECT_ROOT/.local-cache/uploads"
mkdir -p .local-cache/uploads
(cd backend && "$PROJECT_ROOT/.venv/bin/python" -m uvicorn app.main:app --no-access-log --host 127.0.0.1 --port "${STUDIO_BACKEND_PORT:-8011}") & API_PID=$!
WORKER_PID=''; FRONT_PID=''
cleanup(){ kill "$API_PID" ${WORKER_PID:+"$WORKER_PID"} ${FRONT_PID:+"$FRONT_PID"} 2>/dev/null || true; }
trap cleanup EXIT INT TERM
for i in $(seq 1 30); do
  if curl --silent --fail "$BACKEND_URL/health" >/dev/null; then break; fi
  sleep 1
done
if ! kill -0 "$API_PID" 2>/dev/null; then
  printf '작업실을 열지 못했습니다. 사용 중인 실행 포트를 확인해주세요.\n'
  exit 1
fi
(cd backend && "$PROJECT_ROOT/.venv/bin/python" -m app.worker) & WORKER_PID=$!
(cd frontend && WATCHPACK_POLLING=true npm run dev -- --port "${STUDIO_PORT:-3011}") & FRONT_PID=$!
printf '\n상품 작업실: %s\n체험 모드이며 실제 쇼핑몰에 등록되지 않습니다.\n종료하려면 Control+C를 누르세요.\n' "$FRONTEND_ORIGIN"
for i in $(seq 1 30); do
  if curl --silent --fail "$FRONTEND_ORIGIN" >/dev/null; then
    if command -v open >/dev/null; then open "$FRONTEND_ORIGIN"; fi
    break
  fi
  sleep 1
done
wait "$FRONT_PID"
