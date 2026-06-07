from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings

app = FastAPI(title="Grasp API", version="0.2.0")

# CORS. The web app is currently served over http://app.proof-forge.ru (the HTTPS vhost
# for the app subdomain is not enabled yet — see infra/nginx/proof-forge.conf), so the
# *http* origin MUST be allowed. Listing only the https origin made every cross-origin
# API call from a real browser fail the preflight and surface as a confusing
# "Failed to fetch" / CORS error for anyone not on localhost.
#
# allow_origin_regex matches the proof-forge.ru apex and any subdomain (app/www/…) over
# both http and https, so this stops being whack-a-mole when HTTPS is later turned on.
# Proper long-term fix: enable the HTTPS vhost for app.proof-forge.ru and redirect http→https.
_CORS_ORIGIN_REGEX = r"^https?://([a-z0-9-]+\.)*proof-forge\.ru$"
_CORS_ORIGINS = [settings.frontend_url, "http://localhost:3000", "http://127.0.0.1:3000"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_origin_regex=_CORS_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok"}


from app.routers import users, events, topics, capsules, reviews, agent_context, cards, mastery, auth, analytics, metrics, practice, chat, onboarding

app.include_router(users.router, prefix="/api")
app.include_router(events.router, prefix="/api")
app.include_router(topics.router, prefix="/api")
app.include_router(capsules.router, prefix="/api")
app.include_router(reviews.router, prefix="/api")
app.include_router(agent_context.router, prefix="/api")
app.include_router(cards.router, prefix="/api")
app.include_router(mastery.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(analytics.router, prefix="/api")
app.include_router(metrics.router, prefix="/api")
app.include_router(practice.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(onboarding.router, prefix="/api")
