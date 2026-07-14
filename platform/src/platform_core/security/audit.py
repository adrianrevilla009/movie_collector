"""Auditoria de eventos de auth (Seccion 2.4): login (exito/fallo), cambio de
contrasena y logout se registran en un logger dedicado `auth.audit`,
consultable en Loki - separado de logica operacional/de dominio a proposito
(no se guarda en Postgres, ver Seccion 2.4)."""

import uuid

import structlog

audit_logger = structlog.get_logger("auth.audit")


def log_login_success(user_id: uuid.UUID, email: str, ip_address: str | None) -> None:
    audit_logger.info("login_success", user_id=str(user_id), email=email, ip=ip_address)


def log_login_failure(email: str, ip_address: str | None, reason: str) -> None:
    audit_logger.warning("login_failure", email=email, ip=ip_address, reason=reason)


def log_logout(user_id: uuid.UUID, all_sessions: bool, ip_address: str | None) -> None:
    audit_logger.info(
        "logout", user_id=str(user_id), all_sessions=all_sessions, ip=ip_address
    )


def log_password_change(user_id: uuid.UUID, ip_address: str | None) -> None:
    audit_logger.info("password_change", user_id=str(user_id), ip=ip_address)
