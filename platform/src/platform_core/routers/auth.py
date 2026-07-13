from datetime import UTC, datetime

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.config import get_settings
from platform_core.db import get_db
from platform_core.models import User
from platform_core.schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    RegisterRequest,
    ResendVerificationRequest,
    ResetPasswordRequest,
    TokenResponse,
    VerifyEmailRequest,
)
from platform_core.security.dependencies import get_current_user
from platform_core.security.rate_limit import limiter
from platform_core.security.tokens import create_access_token
from platform_core.services import auth_service

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
settings = get_settings()

REFRESH_COOKIE_NAME = "refresh_token"
# Cookie NO httpOnly, sin nada sensible dentro (solo "1"): permite al frontend
# saber si "probablemente hay sesion" sin poder leer el refresh token real,
# para evitar una llamada a /auth/refresh en cada carga cuando claramente no
# hay sesion (evita ruido de un 401 esperado en la consola del navegador).
SESSION_MARKER_COOKIE_NAME = "has_session"


def _set_refresh_cookie(response: Response, raw_token: str) -> None:
    response.set_cookie(
        REFRESH_COOKIE_NAME,
        raw_token,
        httponly=True,
        secure=(settings.environment == "production"),
        samesite="strict",
    )
    response.set_cookie(
        SESSION_MARKER_COOKIE_NAME,
        "1",
        httponly=False,
        secure=(settings.environment == "production"),
        samesite="strict",
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(REFRESH_COOKIE_NAME)
    response.delete_cookie(SESSION_MARKER_COOKIE_NAME)


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, db: AsyncSession = Depends(get_db)):
    if payload.website:
        # Honeypot relleno = bot (Seccion 2.5). Se responde como si hubiera
        # tenido exito, sin dar pistas de que fue detectado.
        return {"message": "Registro recibido"}

    await auth_service.register_user(db, payload.email, payload.name, payload.password)
    return {"message": "Registro recibido, revisa tu email para verificar la cuenta"}


@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/15minutes")
async def login(
    request: Request, response: Response, payload: LoginRequest, db: AsyncSession = Depends(get_db)
):
    user = await auth_service.authenticate_user(db, payload.email, payload.password)
    access_token = create_access_token(user.id, user.role.value)
    raw_refresh, _ = await auth_service.issue_refresh_token(
        db,
        user.id,
        request.headers.get("user-agent"),
        request.client.host if request.client else None,
    )
    _set_refresh_cookie(response, raw_refresh)
    return TokenResponse(access_token=access_token)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    refresh_token: str | None = Cookie(default=None, alias=REFRESH_COOKIE_NAME),
):
    if refresh_token is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Falta refresh token")

    user, new_raw = await auth_service.rotate_refresh_token(
        db,
        refresh_token,
        request.headers.get("user-agent"),
        request.client.host if request.client else None,
    )
    _set_refresh_cookie(response, new_raw)
    return TokenResponse(access_token=create_access_token(user.id, user.role.value))


@router.post("/logout")
async def logout(
    response: Response,
    db: AsyncSession = Depends(get_db),
    refresh_token: str | None = Cookie(default=None, alias=REFRESH_COOKIE_NAME),
):
    if refresh_token:
        await auth_service.revoke_refresh_token(db, refresh_token)
    _clear_refresh_cookie(response)
    return {"message": "Sesion cerrada"}


@router.post("/logout-all")
async def logout_all(
    response: Response, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    await auth_service.revoke_all_sessions(db, user.id)
    _clear_refresh_cookie(response)
    return {"message": "Todas las sesiones cerradas"}


@router.post("/verify-email")
async def verify_email(payload: VerifyEmailRequest, db: AsyncSession = Depends(get_db)):
    await auth_service.verify_email(db, payload.token)
    return {"message": "Email verificado"}


@router.post("/resend-verification")
async def resend_verification(
    payload: ResendVerificationRequest, db: AsyncSession = Depends(get_db)
):
    # Mismo principio anti-enumeracion que forgot-password: respuesta generica.
    from sqlalchemy import select

    from platform_core.email.mailer import send_verification_email
    from platform_core.security.tokens import generate_one_time_token

    user = await db.scalar(select(User).where(User.email == payload.email))
    if user and not user.email_verified:
        from datetime import timedelta

        from platform_core.models import EmailVerificationToken

        raw_token, token_hash = generate_one_time_token()
        db.add(
            EmailVerificationToken(
                user_id=user.id,
                token_hash=token_hash,
                expires_at=datetime.now(UTC) + timedelta(days=2),
            )
        )
        await db.commit()
        send_verification_email(payload.email, raw_token)
    return {"message": "Si el email existe y no esta verificado, se ha reenviado el correo"}


@router.post("/forgot-password")
async def forgot_password(payload: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)):
    await auth_service.request_password_reset(db, payload.email)
    # Siempre 200, exista o no el email (Seccion 2.4)
    return {"message": "Si el email existe, se ha enviado un correo de recuperacion"}


@router.post("/reset-password")
async def reset_password(payload: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    await auth_service.reset_password(db, payload.token, payload.new_password)
    return {"message": "Contrasena actualizada"}