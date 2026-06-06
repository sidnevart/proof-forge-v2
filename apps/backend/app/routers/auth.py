from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db, async_session_factory
from app.repositories import user_repo, auth_repo, api_key_repo
from app.services import jwt as jwt_service, email as email_service
from app.schemas.auth import (
    SendLinkRequest, SendLinkResponse, VerifyRequest, VerifyResponse, MeResponse,
    ApiKeyCreateResponse, ApiKeyOut,
)
from app.models.learning_event import LearningEvent

router = APIRouter(prefix="/auth", tags=["auth"])
bearer_scheme = HTTPBearer(auto_error=False)


async def require_auth(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> str:
    """Return the authenticated user_id, using either a Bearer JWT or an X-Api-Key header.

    Attach as a FastAPI dependency on endpoints that need authentication.
    ``user_id`` is also stored on ``request.state.user_id`` so endpoints can
    access it without an explicit parameter.
    """
    # 1. Bearer JWT (web frontend)
    if credentials:
        payload = jwt_service.decode_token(credentials.credentials)
        if payload:
            uid = payload["sub"]
            request.state.user_id = uid
            return uid

    # 2. X-Api-Key header (IDE plugins / programmatic access)
    raw = request.headers.get("X-Api-Key")
    if raw:
        async with async_session_factory() as db:
            uid = await api_key_repo.validate_key(db, raw)
        if uid:
            request.state.user_id = uid
            return uid

    raise HTTPException(status_code=401, detail="Не авторизован")


@router.post("/send-link", response_model=SendLinkResponse)
async def send_magic_link(data: SendLinkRequest, db: AsyncSession = Depends(get_db)):
    await user_repo.find_or_create(db, data.email, data.display_name)
    token = await auth_repo.create_token(db, data.email)
    # Mail delivery must never crash the request: a transport failure would
    # otherwise surface in the browser as a misleading CORS error (the 500
    # response is emitted outside the CORS middleware and carries no headers).
    sent = email_service.send_magic_link(data.email, token, data.display_name)
    if not sent:
        raise HTTPException(
            status_code=502,
            detail="Не удалось отправить письмо. Попробуй позже или напиши в поддержку.",
        )
    return SendLinkResponse(message="Ссылка для входа отправлена на почту")


@router.post("/verify", response_model=VerifyResponse)
async def verify_magic_link(data: VerifyRequest, db: AsyncSession = Depends(get_db)):
    email = await auth_repo.consume_token(db, data.token)
    if not email:
        raise HTTPException(status_code=401, detail="Ссылка недействительна или уже использована")

    is_new, user = await user_repo.find_or_create_with_flag(db, email)
    db.add(LearningEvent(
        user_id=user.id,
        event_type="user_login",
        payload={"email": email, "first_login": is_new},
    ))
    await db.commit()

    access_token = jwt_service.create_access_token(user.id, user.email)
    return VerifyResponse(
        access_token=access_token,
        user_id=user.id,
        email=user.email,
        display_name=user.display_name,
    )


@router.get("/me", response_model=MeResponse)
async def get_me(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    if not credentials:
        raise HTTPException(status_code=401, detail="Не авторизован")
    payload = jwt_service.decode_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=401, detail="Невалидный токен")
    return MeResponse(user_id=payload["sub"], email=payload["email"], display_name=payload.get("display_name", ""))


@router.post("/dev-token", response_model=VerifyResponse)
async def dev_token(data: SendLinkRequest, db: AsyncSession = Depends(get_db)):
    """Create (or fetch) a user and return an access token directly — bypasses the
    magic-link email flow. Available ONLY outside production, for E2E tests and local dev.
    """
    if settings.app_env == "production":
        raise HTTPException(status_code=404, detail="Not found")

    _, user = await user_repo.find_or_create_with_flag(db, data.email)
    if data.display_name and not user.display_name:
        user.display_name = data.display_name
    db.add(LearningEvent(
        user_id=user.id,
        event_type="user_login",
        payload={"email": data.email, "dev_token": True},
    ))
    await db.commit()

    access_token = jwt_service.create_access_token(user.id, user.email)
    return VerifyResponse(
        access_token=access_token,
        user_id=user.id,
        email=user.email,
        display_name=user.display_name,
    )


# ── API keys (IDE plugins) ─────────────────────────────────────────────────

@router.post("/api-keys", response_model=ApiKeyCreateResponse, status_code=201)
async def create_api_key(
    data: dict,
    user_id: str = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Generate a new API key. The raw key is returned ONCE — save it now."""
    key, raw = await api_key_repo.create_key(db, user_id, data.get("name", ""))
    return ApiKeyCreateResponse(
        id=key.id,
        name=key.name,
        raw_key=raw,
        created_at=key.created_at,
    )


@router.get("/api-keys", response_model=list[ApiKeyOut])
async def list_api_keys(
    user_id: str = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    keys = await api_key_repo.list_keys(db, user_id)
    return [
        ApiKeyOut(id=k.id, name=k.name, created_at=k.created_at, last_used_at=k.last_used_at)
        for k in keys
    ]


@router.delete("/api-keys/{key_id}", status_code=204)
async def revoke_api_key(
    key_id: str,
    user_id: str = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    ok = await api_key_repo.revoke_key(db, key_id, user_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Ключ не найден")
