import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.db import get_db
from platform_core.models import Notification, RefreshToken, User
from platform_core.schemas.account import ChangePasswordRequest, ExportDataOut, UpdateProfileRequest
from platform_core.schemas.auth import SessionOut
from platform_core.schemas.moderation import NotificationOut
from platform_core.security.dependencies import get_current_user
from platform_core.services import account_service, moderation_service

router = APIRouter(prefix="/api/v1/users/me", tags=["account"])


@router.patch("")
async def update_profile(
    payload: UpdateProfileRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    updated = await account_service.update_profile(db, user, payload.name, payload.email)
    return {"id": str(updated.id), "email": updated.email, "name": updated.name}


@router.post("/change-password")
async def change_password(
    payload: ChangePasswordRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await account_service.change_password(db, user, payload.current_password, payload.new_password)
    return {"message": "Contrasena actualizada"}


@router.delete("")
async def delete_account(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    await account_service.delete_account(db, user)
    return {"message": "Cuenta eliminada (anonimizada)"}


@router.get("/export", response_model=ExportDataOut)
async def export_data(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await account_service.export_user_data(db, user.id)


@router.get("/sessions", response_model=list[SessionOut])
async def list_sessions(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    tokens = await db.scalars(
        select(RefreshToken).where(
            RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None)
        )
    )
    return list(tokens)


@router.delete("/sessions/{family_id}")
async def revoke_session(
    family_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    tokens = await db.scalars(
        select(RefreshToken).where(
            RefreshToken.user_id == user.id,
            RefreshToken.family_id == family_id,
            RefreshToken.revoked_at.is_(None),
        )
    )
    now = datetime.now(UTC)
    for t in tokens:
        t.revoked_at = now
    await db.commit()
    return {"message": "Sesion revocada"}


@router.get("/notifications", response_model=list[NotificationOut])
async def list_notifications(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    result = await db.scalars(
        select(Notification)
        .where(Notification.user_id == user.id)
        .order_by(Notification.created_at.desc())
    )
    return list(result)


notif_router = APIRouter(prefix="/api/v1/notifications", tags=["account"])


@notif_router.post("/{notification_id}/read")
async def mark_notification_read(
    notification_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await moderation_service.mark_notification_read(db, user.id, notification_id)
    return {"message": "Notificacion marcada como leida"}
