#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────
#  NBP Lab — Run Script
#  Checks for / kills existing processes, then starts all
#  required services:  PostgreSQL · Redis · FastAPI · RQ Worker · Vite
# ──────────────────────────────────────────────────────────────
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

# ── Colours (no-op if not a terminal) ─────────────────────────
if [[ -t 1 ]]; then
  GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
else
  GREEN=''; YELLOW=''; RED=''; NC=''
fi

info()  { echo -e "${GREEN}[nbplab]${NC} $*"; }
warn()  { echo -e "${YELLOW}[nbplab]${NC} $*"; }
err()   { echo -e "${RED}[nbplab]${NC} $*" >&2; }

# ── 1. Kill existing NBP-related processes ────────────────────
info "Checking for existing processes…"

kill_pattern() {
  local pattern="$1"
  local pids
  pids=$(pgrep -f "$pattern" 2>/dev/null || true)
  if [[ -n "$pids" ]]; then
    warn "Killing existing process(es) matching '$pattern': $pids"
    echo "$pids" | xargs kill -9 2>/dev/null || true
    sleep 0.5
  fi
}

# Kill previous instances of our services (but not this script itself)
kill_pattern "uvicorn backend.app.main:app"
kill_pattern "rq worker"
kill_pattern "vite.*--port"

# Also free ports directly in case orphaned processes linger
for port in 8000 5173; do
  pids=$(lsof -ti:"$port" 2>/dev/null || true)
  if [[ -n "$pids" ]]; then
    warn "Freeing port $port (PIDs: $pids)"
    echo "$pids" | xargs kill -9 2>/dev/null || true
  fi
done
sleep 1

# ── 2. Ensure PostgreSQL is running ──────────────────────────
info "Checking PostgreSQL…"
if command -v pg_isready &>/dev/null; then
  if pg_isready -q 2>/dev/null; then
    info "PostgreSQL is already running."
  else
    warn "PostgreSQL not responding — attempting to start…"
    if command -v pg_ctlcluster &>/dev/null; then
      sudo pg_ctlcluster $(pg_lsclusters -h | head -1 | awk '{print $1, $2}') start 2>/dev/null || true
    elif [[ -x /usr/lib/postgresql/*/bin/pg_ctl ]]; then
      sudo -u postgres /usr/lib/postgresql/*/bin/pg_ctl start -D /var/lib/postgresql/*/main 2>/dev/null || true
    else
      sudo service postgresql start 2>/dev/null || true
    fi
    sleep 2
    if pg_isready -q 2>/dev/null; then
      info "PostgreSQL started."
    else
      err "Could not start PostgreSQL. Please start it manually."
      exit 1
    fi
  fi
else
  warn "pg_isready not found — assuming PostgreSQL is running externally."
fi

# ── 3. Ensure Redis is running ───────────────────────────────
info "Checking Redis…"
if command -v redis-cli &>/dev/null; then
  if redis-cli ping &>/dev/null; then
    info "Redis is already running."
  else
    warn "Redis not responding — attempting to start…"
    redis-server --daemonize yes 2>/dev/null || sudo service redis-server start 2>/dev/null || true
    sleep 1
    if redis-cli ping &>/dev/null; then
      info "Redis started."
    else
      err "Could not start Redis. Please start it manually."
      exit 1
    fi
  fi
else
  warn "redis-cli not found — assuming Redis is running externally."
fi

# ── 4. Run Alembic migrations ────────────────────────────────
info "Running database migrations…"
alembic -c backend/alembic.ini upgrade head 2>&1 || {
  warn "Alembic migration failed (DB may already be up-to-date)."
}

# ── 5. Install frontend dependencies if needed ───────────────
if [[ ! -d frontend/node_modules ]]; then
  info "Installing frontend dependencies…"
  (cd frontend && npm install)
fi

# ── 6. Start services in background ──────────────────────────
PIDS=()

cleanup() {
  info "Shutting down services…"
  for pid in "${PIDS[@]}"; do
    kill "$pid" 2>/dev/null || true
  done
  wait 2>/dev/null || true
  info "All services stopped."
}
trap cleanup EXIT INT TERM

# FastAPI backend
info "Starting FastAPI server (uvicorn) on :8000…"
uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000 &
PIDS+=($!)

# RQ worker
info "Starting RQ worker…"
rq worker --url "$(grep -oP 'REDIS_URL=\K.*' .env 2>/dev/null || echo redis://localhost:6379/0)" &
PIDS+=($!)

# Vite dev server
info "Starting Vite dev server on :5173…"
(cd frontend && npm run dev -- --host 0.0.0.0 --port 5173) &
PIDS+=($!)

echo ""
info "═══════════════════════════════════════════════"
info "  NBP Lab is running!"
info "  Backend API : http://localhost:8000"
info "  Frontend    : http://localhost:5173"
info "  API docs    : http://localhost:8000/docs"
info "═══════════════════════════════════════════════"
echo ""
info "Press Ctrl+C to stop all services."

# Wait for any child to exit
wait
