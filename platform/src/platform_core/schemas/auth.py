import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=10, max_length=128)
    # Honeypot anti-spam (Seccion 2.5): campo oculto, invisible para humanos.
    # Si llega relleno, la peticion se descarta silenciosamente como si hubiera tenido exito.
    website: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class VerifyEmailRequest(BaseModel):
    token: str


class ResendVerificationRequest(BaseModel):
    email: EmailStr


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=10, max_length=128)


class SessionOut(BaseModel):
    family_id: uuid.UUID
    user_agent: str | None
    ip_address: str | None
    last_used_at: datetime | None
    expires_at: datetime

    model_config = {"from_attributes": True}
