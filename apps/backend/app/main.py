import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings

logger = logging.getLogger(__name__)

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


class CorsSafeErrorMiddleware:
    """Make UNHANDLED 500s carry CORS headers.

    Starlette's ServerErrorMiddleware sits OUTSIDE CORSMiddleware, so an unhandled
    exception produces a 500 with no Access-Control-Allow-Origin header — which the
    browser reports as a misleading "blocked by CORS policy" error that hides the
    real server error (this masked the folder-serialization 500 for days). Sitting
    just INSIDE CORSMiddleware, this catches the exception before it escapes to
    ServerErrorMiddleware and emits a normal 500 response; that response then flows
    back out through CORSMiddleware, which attaches the CORS headers as usual. So a
    backend bug shows up as a real 500 in the browser, not a phantom CORS failure.

    Pure ASGI (no body buffering) so it is safe for the SSE streaming endpoints — it
    only wraps `send` to learn whether the response already started; once a stream
    has begun it cannot rewrite the response and re-raises, exactly as before.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        started = False

        async def wrapped_send(message):
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, receive, wrapped_send)
        except Exception:
            logger.exception("Unhandled error on %s %s", scope.get("method"), scope.get("path"))
            if started:
                raise  # headers already sent (e.g. mid-stream) — can't recover
            await send({"type": "http.response.start", "status": 500,
                        "headers": [(b"content-type", b"application/json")]})
            await send({"type": "http.response.body", "body": b'{"detail":"Internal Server Error"}'})

# Order matters: add_middleware prepends, so the LAST call is outermost. CORS must be
# outermost (it owns preflight + decorates every response, including the 500 emitted
# by CorsSafeErrorMiddleware sitting just inside it).
app.add_middleware(CorsSafeErrorMiddleware)
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
