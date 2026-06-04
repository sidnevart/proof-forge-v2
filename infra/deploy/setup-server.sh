#!/usr/bin/env bash
# Run on server: bash <(curl -sL https://raw.githubusercontent.com/sidnevart/proof-forge-v2/main/infra/deploy/setup-server.sh)
set -euo pipefail

APP_DIR=/opt/proof-forge
REPO_URL=https://github.com/sidnevart/proof-forge-v2.git

GREEN='\033[0;32m'; CYAN='\033[0;36m'; RED='\033[0;31m'; NC='\033[0m'
ok()   { echo -e "${GREEN}✔${NC}  $*"; }
info() { echo -e "${CYAN}▸${NC}  $*"; }
fail() { echo -e "${RED}✘${NC}  $*"; exit 1; }

# ── 1. Docker ──────────────────────────────────────────────────────────────────
if ! command -v docker &>/dev/null; then
    info "Installing Docker..."
    curl -fsSL https://get.docker.com | sh
    systemctl enable --now docker
    ok "Docker installed"
else
    ok "Docker already installed"
fi
docker compose version &>/dev/null || fail "docker compose plugin not found"

# ── 2. Clone / pull repo ───────────────────────────────────────────────────────
if [[ -d "$APP_DIR/.git" ]]; then
    info "Pulling latest code..."
    git -C "$APP_DIR" fetch origin && git -C "$APP_DIR" reset --hard origin/main
else
    info "Cloning repo..."
    git clone "$REPO_URL" "$APP_DIR"
fi
ok "Code at $APP_DIR"

# ── 3. .env.prod guard ────────────────────────────────────────────────────────
if [[ ! -f "$APP_DIR/.env.prod" ]]; then
    cat > "$APP_DIR/.env.prod" << 'ENVTEMPLATE'
# PostgreSQL
POSTGRES_DB=proofforge
POSTGRES_USER=postgres
POSTGRES_PASSWORD=FILL_DB_PASSWORD

# Auth
JWT_SECRET=FILL_JWT_SECRET

# Email (Resend — from address must match verified domain or use onboarding@resend.dev for testing)
RESEND_API_KEY=FILL_RESEND_KEY
FROM_EMAIL=onboarding@resend.dev
FRONTEND_URL=https://app.proof-forge.ru

# AI — Ollama runs locally, LLM_API_KEY can be anything
LLM_API_KEY=ollama
LLM_BASE_URL=http://ollama:11434/v1
LLM_MODEL=llama3.2:3b
ENVTEMPLATE
    echo ""
    echo -e "${RED}  ⚠  Edit $APP_DIR/.env.prod with real values, then re-run.${NC}"
    exit 0
fi

# Check none of the placeholders remain
if grep -q "FILL_" "$APP_DIR/.env.prod"; then
    fail "Fill in FILL_* placeholders in $APP_DIR/.env.prod before continuing"
fi

cp "$APP_DIR/.env.prod" "$APP_DIR/.env"
ok ".env ready"

# ── 4. SSL certificates ───────────────────────────────────────────────────────
if [[ ! -d /etc/letsencrypt/live/proof-forge.ru ]]; then
    info "Getting SSL certificates..."
    apt-get install -y certbot 2>/dev/null || true
    docker run --rm -d --name tmp-nginx -p 80:80 \
        -v /var/www/certbot:/usr/share/nginx/html:ro nginx:alpine 2>/dev/null || true
    sleep 2
    certbot certonly --webroot -w /var/www/certbot \
        -d proof-forge.ru -d api.proof-forge.ru -d app.proof-forge.ru \
        --non-interactive --agree-tos -m admin@proof-forge.ru \
        || info "SSL request failed — check DNS, continuing anyway"
    docker stop tmp-nginx 2>/dev/null || true
fi
ok "SSL done"

# ── 5. Build + start ──────────────────────────────────────────────────────────
cd "$APP_DIR"
info "Building images (may take 5-10 min)..."
docker compose -f docker-compose.prod.yml build --parallel
docker compose -f docker-compose.prod.yml up -d
ok "Services started"

# ── 6. Pull Ollama model ──────────────────────────────────────────────────────
OLLAMA_MODEL="${LLM_MODEL:-llama3.2:3b}"
info "Pulling Ollama model: $OLLAMA_MODEL (this may take a few minutes)..."
for i in $(seq 1 15); do
    docker compose -f docker-compose.prod.yml exec -T ollama ollama pull "$OLLAMA_MODEL" 2>&1 && break || true
    sleep 5
done
ok "Ollama model ready"

# ── 8. Health check ───────────────────────────────────────────────────────────
info "Waiting for backend..."
for i in $(seq 1 30); do
    curl -sf http://localhost:8000/health &>/dev/null && { ok "Backend healthy"; break; }
    sleep 3
done
curl -sf http://localhost:8000/health | grep -q '"ok"' || { docker compose -f docker-compose.prod.yml logs --tail=30 backend; fail "Backend not healthy"; }

info "Waiting for web app..."
for i in $(seq 1 20); do
    curl -sf http://localhost:3000 &>/dev/null && { ok "Web app healthy"; break; }
    sleep 3
done

# ── 9. SSH deploy key for GitHub Actions ─────────────────────────────────────
KEY=/root/.ssh/grasp_deploy_ed25519
if [[ ! -f "$KEY" ]]; then
    ssh-keygen -t ed25519 -f "$KEY" -N "" -C "grasp-deploy"
    cat "${KEY}.pub" >> /root/.ssh/authorized_keys
    chmod 600 /root/.ssh/authorized_keys
    echo ""
    echo "════════════════════════════════════════════"
    echo "  ADD THIS TO GitHub Secrets → SSH_PRIVATE_KEY:"
    echo "════════════════════════════════════════════"
    cat "$KEY"
    echo "════════════════════════════════════════════"
fi

# ── 8. Summary ────────────────────────────────────────────────────────────────
echo ""
echo -e "${CYAN}━━━ Deploy complete ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "  🌐 Landing:  https://proof-forge.ru"
echo -e "  🚀 Web App:  https://app.proof-forge.ru"
echo -e "  ⚡ API:      https://api.proof-forge.ru/docs"
echo -e "  Logs:  docker compose -f $APP_DIR/docker-compose.prod.yml logs -f"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
