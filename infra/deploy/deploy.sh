#!/usr/bin/env bash
# Proof-Forge v2 — production deploy script.
# Run this on the SERVER (not locally).
#
# First deploy:
#   curl -sO https://raw.githubusercontent.com/sidnevart/proof-forge-v2/main/infra/deploy/deploy.sh
#   chmod +x deploy.sh && ./deploy.sh
#
# Update:
#   ./deploy.sh

set -euo pipefail

REPO_URL="git@github.com:sidnevart/proof-forge-v2.git"
APP_DIR="/opt/proof-forge"
COMPOSE="docker compose -f docker-compose.prod.yml"

GREEN='\033[0;32m'; RED='\033[0;31m'; CYAN='\033[0;36m'; NC='\033[0m'
ok()   { echo -e "${GREEN}✔${NC}  $*"; }
fail() { echo -e "${RED}✘${NC}  $*"; exit 1; }
info() { echo -e "${CYAN}▸${NC}  $*"; }

# ── 1. system deps ────────────────────────────────────────────────────────────

info "Checking system dependencies..."
command -v docker  >/dev/null || fail "docker not found — install Docker first"
command -v git     >/dev/null || fail "git not found"
docker compose version >/dev/null 2>&1 || fail "docker compose plugin not found"
ok "Dependencies OK"

# ── 2. clone or update repo ───────────────────────────────────────────────────

if [[ -d "$APP_DIR/.git" ]]; then
    info "Updating repo..."
    cd "$APP_DIR"
    git fetch origin
    git reset --hard origin/main
    ok "Repo updated"
else
    info "Cloning repo to $APP_DIR..."
    git clone "$REPO_URL" "$APP_DIR"
    cd "$APP_DIR"
    ok "Repo cloned"
fi

# ── 3. .env check ─────────────────────────────────────────────────────────────

if [[ ! -f "$APP_DIR/.env.prod" ]]; then
    fail ".env.prod not found at $APP_DIR/.env.prod — create it from .env.example first"
fi

cp "$APP_DIR/.env.prod" "$APP_DIR/.env"
ok ".env set from .env.prod"

# ── 4. SSL certificates (first deploy only) ───────────────────────────────────

CERT_DIR="/etc/letsencrypt/live/api.proof-forge.ru"
if [[ ! -d "$CERT_DIR" ]]; then
    info "Requesting SSL certificates..."
    command -v certbot >/dev/null || apt-get install -y certbot

    # Start nginx on port 80 alone for the ACME challenge
    docker compose -f docker-compose.prod.yml up -d nginx 2>/dev/null || true
    sleep 3

    certbot certonly --webroot \
        -w /var/www/certbot \
        -d proof-forge.ru \
        -d api.proof-forge.ru \
        --non-interactive --agree-tos -m admin@proof-forge.ru

    ok "SSL certificates issued"
else
    info "SSL certificates already present — skipping"
fi

# ── 5. build + start ──────────────────────────────────────────────────────────

info "Building and starting services..."
cd "$APP_DIR"
$COMPOSE pull nginx postgres 2>/dev/null || true
$COMPOSE up -d --build
ok "Services started"

# ── 6. wait for backend ───────────────────────────────────────────────────────

info "Waiting for backend health check..."
MAX=60; WAITED=0
until curl -sf http://localhost:8000/health >/dev/null 2>&1; do
    [[ $WAITED -ge $MAX ]] && { $COMPOSE logs --tail=40 backend; fail "Backend did not start"; }
    sleep 3; WAITED=$((WAITED+3)); echo -n "."
done
echo ""
ok "Backend healthy (${WAITED}s)"

# ── 7. smoke tests ────────────────────────────────────────────────────────────

info "Running smoke tests..."

HEALTH=$(curl -sf http://localhost:8000/health)
echo "  /health → $HEALTH"
echo "$HEALTH" | grep -q '"ok"' || fail "/health returned unexpected response"

# POST /api/users
USER=$(curl -sf -X POST http://localhost:8000/api/users \
    -H "Content-Type: application/json" \
    -d '{"email":"deploy-check@proof-forge.ru","display_name":"Deploy Check"}' || echo "error")
echo "  POST /api/users → $USER"
echo "$USER" | grep -q '"id"' || fail "POST /api/users failed"

ok "Smoke tests passed"

# ── 8. summary ────────────────────────────────────────────────────────────────

echo ""
echo -e "${CYAN}━━━ Deploy complete ━━━${NC}"
echo -e "  API:      https://api.proof-forge.ru"
echo -e "  Docs:     https://api.proof-forge.ru/docs"
echo -e "  Health:   https://api.proof-forge.ru/health"
echo ""
echo "Useful commands:"
echo "  Logs:     cd $APP_DIR && docker compose -f docker-compose.prod.yml logs -f backend"
echo "  Update:   ./infra/deploy/deploy.sh"
echo "  Restart:  cd $APP_DIR && docker compose -f docker-compose.prod.yml restart backend"
echo "  Rollback: cd $APP_DIR && git checkout <commit> && docker compose -f docker-compose.prod.yml up -d --build"
