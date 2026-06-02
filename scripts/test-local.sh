#!/usr/bin/env bash
# Local test runner for Proof-Forge v2.
# Starts Docker (postgres + backend), runs unit tests and evals against localhost.
# Prod defaults are overridden only for the duration of this script.
#
# Usage:
#   ./scripts/test-local.sh              # unit tests + evals
#   ./scripts/test-local.sh --no-evals   # unit tests only (no Ollama needed)
#   ./scripts/test-local.sh --keep-up    # don't stop Docker after tests

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV="$ROOT/apps/backend/.venv/bin/python"

# ── options ──────────────────────────────────────────────────────────────────

RUN_EVALS=true
KEEP_UP=false

for arg in "$@"; do
  case $arg in
    --no-evals) RUN_EVALS=false ;;
    --keep-up)  KEEP_UP=true   ;;
  esac
done

# ── colors ───────────────────────────────────────────────────────────────────

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

ok()   { echo -e "${GREEN}✔${NC}  $*"; }
fail() { echo -e "${RED}✘${NC}  $*"; }
info() { echo -e "${CYAN}▸${NC}  $*"; }
warn() { echo -e "${YELLOW}!${NC}  $*"; }

# ── local overrides (prod defaults stay in .env) ──────────────────────────────

export BACKEND_URL="http://localhost:8000"
export DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/proofforge"
export OLLAMA_BASE_URL="http://localhost:11434/v1"

# Load OLLAMA_API_KEY and OLLAMA_MODEL from .env if not already set
if [[ -f "$ROOT/.env" ]]; then
  while IFS='=' read -r key value; do
    [[ "$key" =~ ^#.*$ || -z "$key" ]] && continue
    key="${key// /}"
    # Only load keys not already exported above
    if [[ "$key" == "OLLAMA_API_KEY" || "$key" == "OLLAMA_MODEL" ]]; then
      export "$key"="${value}"
    fi
  done < "$ROOT/.env"
fi

OLLAMA_MODEL="${OLLAMA_MODEL:-glm-5:cloud}"
OLLAMA_API_KEY="${OLLAMA_API_KEY:-ollama}"

echo ""
echo -e "${CYAN}━━━ Proof-Forge local test runner ━━━${NC}"
echo -e "  backend  → ${BACKEND_URL}"
echo -e "  ollama   → ${OLLAMA_BASE_URL}  model=${OLLAMA_MODEL}"
echo ""

# ── pre-flight checks ─────────────────────────────────────────────────────────

info "Checking dependencies..."

if ! command -v docker &>/dev/null; then
  fail "docker not found"
  exit 1
fi

if ! docker info &>/dev/null; then
  fail "Docker daemon is not running — start Docker Desktop first"
  exit 1
fi

if [[ ! -f "$VENV" ]]; then
  fail "venv not found at $VENV"
  info "Run: uv venv apps/backend/.venv && uv pip install -e 'apps/backend[test]' --python apps/backend/.venv/bin/python"
  exit 1
fi

ok "Dependencies OK"

# ── cleanup on exit ───────────────────────────────────────────────────────────

cleanup() {
  if [[ "$KEEP_UP" == "false" ]]; then
    echo ""
    info "Stopping Docker services..."
    cd "$ROOT" && docker compose down -v --remove-orphans 2>/dev/null || true
    ok "Docker stopped"
  else
    warn "Docker left running (--keep-up). Stop with: docker compose down"
  fi
}
trap cleanup EXIT

# ── start Docker ──────────────────────────────────────────────────────────────

echo ""
info "Starting Docker services..."
cd "$ROOT"
docker compose up -d --build 2>&1 | grep -E "(Started|Created|Building|Error|error)" || true

# ── wait for backend ──────────────────────────────────────────────────────────

info "Waiting for backend at ${BACKEND_URL}/health..."
MAX_WAIT=60
WAITED=0
until curl -sf "${BACKEND_URL}/health" >/dev/null 2>&1; do
  if [[ $WAITED -ge $MAX_WAIT ]]; then
    fail "Backend did not start within ${MAX_WAIT}s"
    echo ""
    warn "Docker logs:"
    docker compose logs --tail=30 backend
    exit 1
  fi
  sleep 2
  WAITED=$((WAITED + 2))
  echo -n "."
done
echo ""
ok "Backend is up (${WAITED}s)"

# ── unit + integration tests ──────────────────────────────────────────────────

echo ""
echo -e "${CYAN}━━━ Unit / integration tests ━━━${NC}"

cd "$ROOT"
if "$VENV" -m pytest tests/backend/ -v --tb=short 2>&1; then
  ok "All backend tests passed"
  UNIT_OK=true
else
  fail "Backend tests failed"
  UNIT_OK=false
fi

# ── evals ─────────────────────────────────────────────────────────────────────

EVALS_OK=true

if [[ "$RUN_EVALS" == "true" ]]; then
  echo ""
  echo -e "${CYAN}━━━ Evals (Ollama / ${OLLAMA_MODEL}) ━━━${NC}"

  if ! curl -sf "http://localhost:11434/api/tags" >/dev/null 2>&1; then
    warn "Ollama not running at localhost:11434 — skipping evals"
    warn "Start Ollama and run: ollama pull ${OLLAMA_MODEL}"
    EVALS_OK=skipped
  else
    if OLLAMA_API_KEY="$OLLAMA_API_KEY" OLLAMA_BASE_URL="$OLLAMA_BASE_URL" OLLAMA_MODEL="$OLLAMA_MODEL" \
       "$VENV" tests/evals/run_evals.py 2>&1; then
      ok "All evals passed"
    else
      fail "Evals failed — see tests/evals/results/latest.json"
      EVALS_OK=false
    fi
  fi
fi

# ── summary ───────────────────────────────────────────────────────────────────

echo ""
echo -e "${CYAN}━━━ Summary ━━━${NC}"
[[ "$UNIT_OK" == "true" ]]    && ok "Unit tests" || fail "Unit tests"

if [[ "$RUN_EVALS" == "true" ]]; then
  [[ "$EVALS_OK" == "true" ]]    && ok "Evals" \
  || [[ "$EVALS_OK" == "skipped" ]] && warn "Evals skipped (Ollama offline)" \
  || fail "Evals"
fi

echo ""

# Exit code: 0 only if everything that ran passed
[[ "$UNIT_OK" == "true" && ("$EVALS_OK" == "true" || "$EVALS_OK" == "skipped" || "$RUN_EVALS" == "false") ]]
