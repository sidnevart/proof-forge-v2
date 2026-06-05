from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.repositories import user_repo, auth_repo
from app.services import jwt as jwt_service, email as email_service
from app.schemas.auth import SendLinkRequest, SendLinkResponse, VerifyRequest, VerifyResponse, MeResponse
from app.models.learning_event import LearningEvent

router = APIRouter(prefix="/auth", tags=["auth"])
bearer_scheme = HTTPBearer(auto_error=False)


@router.post("/send-link", response_model=SendLinkResponse)
async def send_magic_link(data: SendLinkRequest, db: AsyncSession = Depends(get_db)):
    await user_repo.find_or_create(db, data.email, data.display_name)
    token = await auth_repo.create_token(db, data.email)
    email_service.send_magic_link(data.email, token, data.display_name)
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
