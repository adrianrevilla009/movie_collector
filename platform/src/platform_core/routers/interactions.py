import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.db import get_db
from platform_core.models import List, Review, ReviewVote, User
from platform_core.schemas.interactions import (
    ListCreateRequest,
    ListItemAddRequest,
    ListOut,
    RatingOut,
    RatingRequest,
    ReviewOut,
    ReviewRequest,
    ReviewVoteRequest,
)
from platform_core.security.dependencies import get_current_user, get_optional_user
from platform_core.services import interactions_service

router = APIRouter(prefix="/api/v1", tags=["interactions"])


@router.post("/ratings", response_model=RatingOut)
async def post_rating(
    payload: RatingRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await interactions_service.upsert_rating(db, user.id, payload.movie_id, payload.score)


@router.post("/reviews", response_model=ReviewOut, status_code=status.HTTP_201_CREATED)
async def post_review(
    payload: ReviewRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    review = await interactions_service.create_review(
        db, user, payload.movie_id, payload.body, payload.rating_id
    )
    return ReviewOut(
        id=review.id,
        movie_id=review.movie_id,
        user_id=review.user_id,
        body=review.body,
        moderation_status=review.moderation_status.value,
        created_at=review.created_at,
    )


@router.get("/movies/{movie_id}/reviews", response_model=list[ReviewOut])
async def list_reviews(movie_id: int, db: AsyncSession = Depends(get_db)):
    helpful = func.count(ReviewVote.id).filter(ReviewVote.is_helpful.is_(True))
    not_helpful = func.count(ReviewVote.id).filter(ReviewVote.is_helpful.is_(False))
    stmt = (
        select(Review, helpful.label("helpful_count"), not_helpful.label("not_helpful_count"))
        .outerjoin(ReviewVote, ReviewVote.review_id == Review.id)
        .where(Review.movie_id == movie_id, Review.deleted_at.is_(None))
        .group_by(Review.id)
        .order_by(helpful.desc(), Review.created_at.desc())
    )
    result = await db.execute(stmt)
    out = []
    for review, helpful_count, not_helpful_count in result.all():
        out.append(
            ReviewOut(
                id=review.id,
                movie_id=review.movie_id,
                user_id=review.user_id,
                body=review.body,
                moderation_status=review.moderation_status.value,
                created_at=review.created_at,
                helpful_count=helpful_count,
                not_helpful_count=not_helpful_count,
            )
        )
    return out


@router.delete("/reviews/{review_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_review(
    review_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    await interactions_service.delete_review(db, user.id, review_id)


@router.post("/reviews/{review_id}/vote")
async def vote_review(
    review_id: uuid.UUID,
    payload: ReviewVoteRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await interactions_service.vote_review(db, user.id, review_id, payload.is_helpful)
    return {"message": "Voto registrado"}


@router.post("/lists", response_model=ListOut, status_code=status.HTTP_201_CREATED)
async def create_list(
    payload: ListCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await interactions_service.create_list(db, user.id, payload.name, payload.is_public)


@router.get("/users/me/lists", response_model=list[ListOut])
async def my_lists(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.scalars(select(List).where(List.user_id == user.id))
    return list(result)


@router.post("/lists/{list_id}/items")
async def add_list_item(
    list_id: uuid.UUID,
    payload: ListItemAddRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await interactions_service.add_item_to_list(db, user.id, list_id, payload.movie_id)
    return {"message": "Anadido a la lista"}


@router.delete("/lists/{list_id}/items/{movie_id}")
async def remove_list_item(
    list_id: uuid.UUID,
    movie_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await interactions_service.remove_item_from_list(db, user.id, list_id, movie_id)
    return {"message": "Eliminado de la lista"}


@router.get("/lists/{list_id}", response_model=ListOut)
async def get_list(
    list_id: uuid.UUID,
    user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    lst = await db.get(List, list_id)
    if lst is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Lista no encontrada")
    if not lst.is_public and (user is None or lst.user_id != user.id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Lista privada")
    return lst
