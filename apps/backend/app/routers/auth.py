from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.repositories import user_repo, auth_repo
from app.services import jwt as jwt_service, email as email_service
from app.schemas.auth import SendLinkRequest, SendLinkResponse, VerifyRequest, VerifyResponse, MeResponse

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

    user = await user_repo.find_or_create(db, email)
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
