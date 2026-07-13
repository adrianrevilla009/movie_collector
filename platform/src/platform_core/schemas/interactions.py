import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class RatingRequest(BaseModel):
    movie_id: int
    score: int = Field(ge=1, le=5)


class RatingOut(BaseModel):
    movie_id: int
    score: int
    updated_at: datetime
    model_config = {"from_attributes": True}


class ReviewRequest(BaseModel):
    movie_id: int
    body: str = Field(min_length=1, max_length=5000)
    rating_id: uuid.UUID | None = None


class ReviewOut(BaseModel):
    id: uuid.UUID
    movie_id: int
    user_id: uuid.UUID
    body: str
    moderation_status: str
    created_at: datetime
    helpful_count: int = 0
    not_helpful_count: int = 0
    model_config = {"from_attributes": True}


class ReviewVoteRequest(BaseModel):
    is_helpful: bool


class ListCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    is_public: bool = False


class ListOut(BaseModel):
    id: uuid.UUID
    name: str
    is_watchlist: bool
    is_public: bool
    model_config = {"from_attributes": True}


class ListItemAddRequest(BaseModel):
    movie_id: int
