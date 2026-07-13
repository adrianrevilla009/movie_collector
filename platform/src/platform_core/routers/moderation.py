import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.db import get_db
from platform_core.models import ModerationStatus, Report, ReportStatus, Review, User
from platform_core.schemas.moderation import (
    AdminStatsOut,
    BanRequest,
    FeedbackRequest,
    ReportRequest,
    ReviewResolveRequest,
)
from platform_core.security.dependencies import get_current_user, get_optional_user, require_admin
from platform_core.services import moderation_service

router = APIRouter(prefix="/api/v1", tags=["moderation"])


@router.get("/admin/reviews/flagged")
async def flagged_reviews(
    db: AsyncSession = Depends(get_db), _admin: User = Depends(require_admin)
):
    result = await db.scalars(
        select(Review).where(Review.moderation_status == ModerationStatus.flagged)
    )
    return list(result)


@router.post("/admin/reviews/{review_id}/resolve")
async def resolve_review(
    review_id: uuid.UUID,
    payload: ReviewResolveRequest,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    return await moderation_service.resolve_flagged_review(db, review_id, payload.status)


@router.post("/reports", status_code=201)
async def create_report(
    payload: ReportRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await moderation_service.create_report(
        db, user.id, payload.target_type, payload.target_id, payload.reason
    )


@router.get("/admin/reports")
async def list_reports(db: AsyncSession = Depends(get_db), _admin: User = Depends(require_admin)):
    result = await db.scalars(select(Report).where(Report.status == ReportStatus.open))
    return list(result)


@router.post("/admin/reports/{report_id}/resolve")
async def resolve_report(
    report_id: uuid.UUID, db: AsyncSession = Depends(get_db), _admin: User = Depends(require_admin)
):
    return await moderation_service.resolve_report(db, report_id)


@router.post("/admin/users/{user_id}/ban")
async def ban_user(
    user_id: uuid.UUID,
    payload: BanRequest,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    await moderation_service.ban_user(db, user_id, payload.banned_until)
    return {"message": "Usuario suspendido"}


@router.post("/admin/users/{user_id}/unban")
async def unban_user(
    user_id: uuid.UUID, db: AsyncSession = Depends(get_db), _admin: User = Depends(require_admin)
):
    await moderation_service.unban_user(db, user_id)
    return {"message": "Usuario reactivado"}


@router.get("/admin/stats", response_model=AdminStatsOut)
async def admin_stats(db: AsyncSession = Depends(get_db), _admin: User = Depends(require_admin)):
    return await moderation_service.admin_stats(db)


@router.post("/feedback", status_code=201)
async def submit_feedback(
    payload: FeedbackRequest,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    return await moderation_service.submit_feedback(
        db, user.id if user else None, payload.category, payload.body
    )


@router.get("/admin/feedback")
async def list_feedback(db: AsyncSession = Depends(get_db), _admin: User = Depends(require_admin)):
    from platform_core.models import Feedback

    result = await db.scalars(select(Feedback).order_by(Feedback.created_at.desc()))
    return list(result)
