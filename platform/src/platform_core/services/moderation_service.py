"""Reportes, moderacion, cuenta, notificaciones y stats (Seccion 2.5)."""

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.models import (
    Feedback,
    ModerationStatus,
    Notification,
    Rating,
    Report,
    ReportStatus,
    ReportTargetType,
    Review,
    User,
)

# 3+ reportes independientes marcan la review como flagged automaticamente
AUTO_FLAG_THRESHOLD = 3


async def create_report(
    db: AsyncSession, reporter_id: uuid.UUID, target_type: str, target_id: str, reason: str
) -> Report:
    report = Report(
        reporter_id=reporter_id,
        target_type=ReportTargetType(target_type),
        target_id=target_id,
        reason=reason,
    )
    db.add(report)
    await db.flush()

    if target_type == "review":
        count = await db.scalar(
            select(func.count(Report.id)).where(
                Report.target_type == ReportTargetType.review,
                Report.target_id == target_id,
                Report.status == ReportStatus.open,
            )
        )
        if count >= AUTO_FLAG_THRESHOLD:
            review = await db.get(Review, uuid.UUID(target_id))
            if review is not None:
                review.moderation_status = ModerationStatus.flagged
                await notify_user(
                    db,
                    review.user_id,
                    "review_flagged",
                    {"review_id": target_id, "reason": "multiples_reportes"},
                )

    await db.commit()
    return report


async def resolve_report(db: AsyncSession, report_id: uuid.UUID) -> Report:
    report = await db.get(Report, report_id)
    if report is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Reporte no encontrado")
    report.status = ReportStatus.resolved
    await db.commit()
    return report


async def resolve_flagged_review(db: AsyncSession, review_id: uuid.UUID, new_status: str) -> Review:
    review = await db.get(Review, review_id)
    if review is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Resena no encontrada")
    review.moderation_status = ModerationStatus(new_status)
    await notify_user(
        db,
        review.user_id,
        "review_moderation_updated",
        {"review_id": str(review_id), "new_status": new_status},
    )
    await db.commit()
    return review


async def ban_user(db: AsyncSession, user_id: uuid.UUID, banned_until: datetime | None) -> User:
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")
    user.is_banned = True
    user.banned_until = banned_until
    await db.commit()
    return user


async def unban_user(db: AsyncSession, user_id: uuid.UUID) -> User:
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")
    user.is_banned = False
    user.banned_until = None
    await db.commit()
    return user


async def notify_user(db: AsyncSession, user_id: uuid.UUID, type_: str, payload: dict) -> None:
    db.add(Notification(user_id=user_id, type=type_, payload=payload))
    # No se hace commit aqui a proposito: se deja al llamante para que la
    # notificacion forme parte de la misma transaccion que el evento que la origina.


async def mark_notification_read(
    db: AsyncSession, user_id: uuid.UUID, notification_id: uuid.UUID
) -> None:
    notif = await db.get(Notification, notification_id)
    if notif is None or notif.user_id != user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Notificacion no encontrada")
    notif.read_at = datetime.now(UTC)
    await db.commit()


async def submit_feedback(
    db: AsyncSession, user_id: uuid.UUID | None, category: str, body: str
) -> Feedback:
    fb = Feedback(user_id=user_id, category=category, body=body)
    db.add(fb)
    await db.commit()
    return fb


async def admin_stats(db: AsyncSession) -> dict:
    seven_days_ago = datetime.now(UTC) - timedelta(days=7)
    total_users = await db.scalar(select(func.count(User.id)))
    new_users = await db.scalar(
        select(func.count(User.id)).where(User.created_at >= seven_days_ago)
    )
    total_ratings = await db.scalar(select(func.count(Rating.id)))
    total_reviews = await db.scalar(select(func.count(Review.id)))
    pending_reviews = await db.scalar(
        select(func.count(Review.id)).where(Review.moderation_status == ModerationStatus.pending)
    )
    open_reports = await db.scalar(
        select(func.count(Report.id)).where(Report.status == ReportStatus.open)
    )

    return {
        "total_users": total_users or 0,
        "new_users_last_7_days": new_users or 0,
        "total_ratings": total_ratings or 0,
        "total_reviews": total_reviews or 0,
        "pending_reviews": pending_reviews or 0,
        "open_reports": open_reports or 0,
    }
