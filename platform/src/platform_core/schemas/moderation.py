import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ReportRequest(BaseModel):
    target_type: str  # "review" | "user"
    target_id: str
    reason: str = Field(min_length=1, max_length=2000)


class ReportResolveRequest(BaseModel):
    status: str  # "resolved"


class ReviewResolveRequest(BaseModel):
    status: str  # "approved" | "flagged"


class BanRequest(BaseModel):
    banned_until: datetime | None = None  # None = permanente


class NotificationOut(BaseModel):
    id: uuid.UUID
    type: str
    payload: dict
    read_at: datetime | None
    created_at: datetime
    model_config = {"from_attributes": True}


class FeedbackRequest(BaseModel):
    category: str  # "bug" | "sugerencia" | "otro"
    body: str = Field(min_length=1, max_length=5000)


class AdminStatsOut(BaseModel):
    total_users: int
    new_users_last_7_days: int
    total_ratings: int
    total_reviews: int
    pending_reviews: int
    open_reports: int
