"""Logica de dominio de auth, separada de la capa API (ver backend-development:
handler nunca construye la logica directamente)."""

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.email.mailer import send_password_reset_email, send_verification_email
from platform_core.models import (
    EmailVerificationToken,
    List,
    PasswordResetToken,
    RefreshToken,
    User,
)
from platform_core.security.passwords import (
    WeakPasswordError,
    hash_password,
    validate_password_strength,
    verify_password,
)
from platform_core.security.tokens import (
    generate_one_time_token,
    generate_refresh_token,
    hash_refresh_token,
    new_family_id,
    refresh_token_expiry,
)


async def register_user(db: AsyncSession, email: str, name: str, password: str) -> User:
    existing = await db.scalar(select(User).where(User.email == email))
    if existing is not None:
        # No filtrar si el email ya existe evitaria enumeracion, pero el registro
        # SI necesita distinguir este caso (UX); el que no filtra es forgot-password.
        raise HTTPException(status.HTTP_409_CONFLICT, detail="El email ya esta registrado")

    try:
        validate_password_strength(password, user_inputs=[email, name])
    except WeakPasswordError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="; ".join(exc.reasons)) from exc

    user = User(email=email, name=name, password_hash=hash_password(password))
    db.add(user)
    await db.flush()

    # Watchlist automatica al registrarse (Seccion 2.3)
    db.add(List(user_id=user.id, name="Mi watchlist", is_watchlist=True, is_public=False))

    raw_token, token_hash = generate_one_time_token()
    db.add(
        EmailVerificationToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=datetime.now(UTC) + timedelta(days=2),
        )
    )
    await db.commit()

    send_verification_email(email, raw_token)
    return user


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User:
    user = await db.scalar(select(User).where(User.email == email))
    if (
        user is None
        or user.deleted_at is not None
        or not verify_password(password, user.password_hash)
    ):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Credenciales invalidas")
    if user.is_banned:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Cuenta suspendida")
    return user


async def issue_refresh_token(
    db: AsyncSession,
    user_id: uuid.UUID,
    user_agent: str | None,
    ip_address: str | None,
    family_id: uuid.UUID | None = None,
) -> tuple[str, uuid.UUID]:
    raw, token_hash = generate_refresh_token()
    family = family_id or new_family_id()
    db.add(
        RefreshToken(
            user_id=user_id,
            token_hash=token_hash,
            family_id=family,
            expires_at=refresh_token_expiry(),
            user_agent=user_agent,
            ip_address=ip_address,
            last_used_at=datetime.now(UTC),
        )
    )
    await db.commit()
    return raw, family


async def rotate_refresh_token(
    db: AsyncSession,
    raw_token: str,
    user_agent: str | None,
    ip_address: str | None,
) -> tuple[User, str]:
    """Rotacion con deteccion de reuso (Seccion 2.4): si el token presentado ya
    fue usado/revocado antes, se revoca TODA la familia y se fuerza re-login."""
    token_hash = hash_refresh_token(raw_token)
    stored = await db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash))

    if stored is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Refresh token invalido")

    if stored.revoked_at is not None:
        # Reuso detectado -> revocar toda la familia
        family_tokens = await db.scalars(
            select(RefreshToken).where(
                RefreshToken.family_id == stored.family_id, RefreshToken.revoked_at.is_(None)
            )
        )
        now = datetime.now(UTC)
        for t in family_tokens:
            t.revoked_at = now
        await db.commit()
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail="Sesion comprometida detectada, se requiere volver a iniciar sesion",
        )

    if stored.expires_at < datetime.now(UTC):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Refresh token expirado")

    stored.revoked_at = datetime.now(UTC)
    user = await db.get(User, stored.user_id)
    if user is None or user.is_banned or user.deleted_at is not None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Usuario no valido")

    new_raw, _ = await issue_refresh_token(
        db, user.id, user_agent, ip_address, family_id=stored.family_id
    )
    await db.commit()
    return user, new_raw


async def revoke_refresh_token(db: AsyncSession, raw_token: str) -> None:
    token_hash = hash_refresh_token(raw_token)
    stored = await db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    if stored is not None and stored.revoked_at is None:
        stored.revoked_at = datetime.now(UTC)
        await db.commit()


async def revoke_all_sessions(db: AsyncSession, user_id: uuid.UUID) -> None:
    tokens = await db.scalars(
        select(RefreshToken).where(
            RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None)
        )
    )
    now = datetime.now(UTC)
    for t in tokens:
        t.revoked_at = now
    await db.commit()


async def verify_email(db: AsyncSession, raw_token: str) -> None:
    token_hash = hash_refresh_token(raw_token)
    record = await db.scalar(
        select(EmailVerificationToken).where(EmailVerificationToken.token_hash == token_hash)
    )
    if record is None or record.used_at is not None or record.expires_at < datetime.now(UTC):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail="Token de verificacion invalido o expirado"
        )

    user = await db.get(User, record.user_id)
    user.email_verified = True
    record.used_at = datetime.now(UTC)
    await db.commit()


async def request_password_reset(db: AsyncSession, email: str) -> None:
    """Siempre se comporta igual exista o no el email (Seccion 2.4/2.5):
    mitigacion de enumeracion de usuarios."""
    user = await db.scalar(select(User).where(User.email == email))
    if user is not None:
        raw_token, token_hash = generate_one_time_token()
        db.add(
            PasswordResetToken(
                user_id=user.id,
                token_hash=token_hash,
                expires_at=datetime.now(UTC) + timedelta(hours=1),
            )
        )
        await db.commit()
        send_password_reset_email(email, raw_token)
    # si no existe, no se hace nada pero se responde 200 igualmente desde el router


async def reset_password(db: AsyncSession, raw_token: str, new_password: str) -> None:
    token_hash = hash_refresh_token(raw_token)
    record = await db.scalar(
        select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash)
    )
    if record is None or record.used_at is not None or record.expires_at < datetime.now(UTC):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail="Token de reset invalido o expirado"
        )

    try:
        validate_password_strength(new_password)
    except WeakPasswordError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="; ".join(exc.reasons)) from exc

    user = await db.get(User, record.user_id)
    user.password_hash = hash_password(new_password)
    record.used_at = datetime.now(UTC)
    await revoke_all_sessions(db, user.id)  # fuerza re-login en todos los dispositivos
    await db.commit()
