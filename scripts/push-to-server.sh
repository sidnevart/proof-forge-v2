#!/usr/bin/env bash
# Deploys Proof-Forge v2 to the production server.
# Run this locally after making changes.
#
# Usage:
#   SERVER_HOST=your.server.ip SSH_PASS=<password> ./scripts/push-to-server.sh

set -euo pipefail

SERVER_HOST="${SERVER_HOST:?set SERVER_HOST=your.server.ip}"
SERVER_USER="${SERVER_USER:-root}"
APP_DIR="${APP_DIR:-/opt/proof-forge}"
REPO_URL="${REPO_URL:-https://github.com/sidnevart/proof-forge-v2.git}"

GREEN='\033[0;32m'; RED='\033[0;31m'; CYAN='\033[0;36m'; NC='\033[0m'
ok()   { echo -e "${GREEN}✔${NC}  $*"; }
fail() { echo -e "${RED}✘${NC}  $*"; exit 1; }
info() { echo -e "${CYAN}▸${NC}  $*"; }

SSH_PASS="${SSH_PASS:-}"
if [[ -z "$SSH_PASS" ]]; then
    echo -n "Server password for root@${SERVER_HOST}: "
    read -rs SSH_PASS
    echo ""
fi

SSH_CMD="sshpass -p '$SSH_PASS' ssh -o StrictHostKeyChecking=no ${SERVER_USER}@${SERVER_HOST}"
SCP_CMD="sshpass -p '$SSH_PASS' scp -o StrictHostKeyChecking=no"

# ── check sshpass ────────────────────────────────────────────────────────────

command -v sshpass >/dev/null || {
    info "Installing sshpass..."
    if command -v brew >/dev/null; then brew install hudochenkov/sshpass/sshpass -q
    elif command -v apt-get >/dev/null; then apt-get install -y sshpass
    else fail "sshpass not found — install it manually"; fi
}

# ── check .env.prod exists locally ───────────────────────────────────────────

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ ! -f "$ROOT/.env.prod" ]]; then
    fail ".env.prod not found. Copy .env.prod.example and fill in real values:\n  cp .env.prod.example .env.prod"
fi

echo ""
echo -e "${CYAN}━━━ Proof-Forge deploy → ${SERVER_HOST} ━━━${NC}"

# ── 1. install system deps on server ─────────────────────────────────────────

info "Installing dependencies on server..."
eval "$SSH_CMD" "
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -qq
    apt-get install -y -qq docker.io docker-compose-plugin git curl certbot sshpass 2>/dev/null
    systemctl enable docker --now 2>/dev/null || true
"
ok "Server deps ready"

# ── 2. clone or update repo ───────────────────────────────────────────────────

info "Syncing repo on server..."
eval "$SSH_CMD" "
    if [[ -d '$APP_DIR/.git' ]]; then
        cd '$APP_DIR' && git fetch origin && git reset --hard origin/main
    else
        git clone '$REPO_URL' '$APP_DIR'
    fi
"
ok "Repo synced"

# ── 3. upload .env.prod ───────────────────────────────────────────────────────

info "Uploading .env.prod..."
eval "$SCP_CMD '$ROOT/.env.prod' '${SERVER_USER}@${SERVER_HOST}:${APP_DIR}/.env.prod'"
ok ".env.prod uploaded"

# ── 4. run deploy script on server ───────────────────────────────────────────

info "Running deploy script on server..."
eval "$SSH_CMD" "
    chmod +x '$APP_DIR/infra/deploy/deploy.sh'
    '$APP_DIR/infra/deploy/deploy.sh'
"

# ── 5. verify from local ──────────────────────────────────────────────────────

info "Verifying from local..."
sleep 3

HEALTH=$(curl -sf "http://${SERVER_HOST}/health" -H "Host: api.proof-forge.ru" 2>/dev/null \
    || curl -sf "http://${SERVER_HOST}:8000/health" 2>/dev/null \
    || echo "unreachable")

echo "  /health → $HEALTH"
echo "$HEALTH" | grep -q '"ok"' && ok "Production is up!" || fail "Health check failed: $HEALTH"

echo ""
echo -e "${CYAN}━━━ Done ━━━${NC}"
echo -e "  API docs: https://api.proof-forge.ru/docs"
echo -e "  Logs:     SSH_PASS=... ./scripts/push-to-server.sh --logs"
