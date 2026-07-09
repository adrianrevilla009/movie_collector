"""Envio de email en local via Mailpit (Seccion 2.4): SMTP simple, sin proveedor cloud."""

import smtplib
from email.message import EmailMessage

from platform_core.config import get_settings

settings = get_settings()


def send_email(to: str, subject: str, body: str) -> None:
    msg = EmailMessage()
    msg["From"] = "no-reply@cine-platform.local"
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as smtp:
        smtp.send_message(msg)


def send_verification_email(to: str, token: str) -> None:
    send_email(
        to,
        "Verifica tu email - Plataforma de cine",
        f"Usa este token para verificar tu cuenta: {token}\n"
        f"(o llama a POST /api/v1/auth/verify-email con este token)",
    )


def send_password_reset_email(to: str, token: str) -> None:
    send_email(
        to,
        "Restablecer contrasena - Plataforma de cine",
        f"Usa este token para restablecer tu contrasena (valido 1 hora): {token}",
    )
