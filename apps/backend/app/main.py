from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings

app = FastAPI(title="Grasp API", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url, "http://localhost:3000", "https://proof-forge.ru"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok"}


from app.routers import users, events, topics, capsules, reviews, agent_context, cards, mastery, auth, analytics, metrics, practice

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
