"""Access tokens (JWT) y refresh tokens opacos con rotacion (Seccion 2.4)."""

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import jwt

from platform_core.config import get_settings

settings = get_settings()


def create_access_token(user_id: uuid.UUID, role: str) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_access_ttl_minutes),
        "type": "access",
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    """Lanza jwt.InvalidTokenError (o subclases) si el token es invalido/expirado."""
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])


def generate_refresh_token() -> tuple[str, str]:
    """Devuelve (token_en_claro, token_hash). Solo el hash se persiste (Seccion 2.4):
    un refresh token nunca se guarda en claro en la base de datos."""
    raw = secrets.token_urlsafe(48)
    return raw, hash_refresh_token(raw)


def hash_refresh_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def new_family_id() -> uuid.UUID:
    return uuid.uuid4()


def refresh_token_expiry() -> datetime:
    return datetime.now(UTC) + timedelta(days=settings.jwt_refresh_ttl_days)


def generate_one_time_token() -> tuple[str, str]:
    """Para verificacion de email / reset de contrasena: mismo patron que el
    refresh token (opaco + hasheado), TTL decidido por el llamante."""
    raw = secrets.token_urlsafe(32)
    return raw, hashlib.sha256(raw.encode()).hexdigest()
