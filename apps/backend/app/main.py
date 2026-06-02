from fastapi import FastAPI

app = FastAPI(title="Proof-Forge API", version="0.1.0")


@app.get("/health")
async def health():
    return {"status": "ok"}


from app.routers import users, events, topics, capsules, reviews, agent_context, cards, mastery

app.include_router(users.router, prefix="/api")
app.include_router(events.router, prefix="/api")
app.include_router(topics.router, prefix="/api")
app.include_router(capsules.router, prefix="/api")
app.include_router(reviews.router, prefix="/api")
app.include_router(agent_context.router, prefix="/api")
app.include_router(cards.router, prefix="/api")
app.include_router(mastery.router, prefix="/api")
