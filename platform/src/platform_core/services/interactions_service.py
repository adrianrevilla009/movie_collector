"""Ratings, reviews, votos y listas (Seccion 2.3/2.4)."""

import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.models import (
    List,
    ListItem,
    ModerationStatus,
    Rating,
    RatingSource,
    Review,
    ReviewVote,
    User,
)


async def upsert_rating(db: AsyncSession, user_id: uuid.UUID, movie_id: int, score: int) -> Rating:
    existing = await db.scalar(
        select(Rating).where(Rating.movie_id == movie_id, Rating.user_id == user_id)
    )
    now = datetime.now(UTC)
    if existing:
        existing.score = score
        existing.updated_at = now
        await db.commit()
        return existing

    rating = Rating(
        movie_id=movie_id,
        user_id=user_id,
        score=score,
        source=RatingSource.live,
        created_at=now,
        updated_at=now,
    )
    db.add(rating)
    await db.commit()
    return rating


async def create_review(
    db: AsyncSession, user: User, movie_id: int, body: str, rating_id: uuid.UUID | None
) -> Review:
    if not user.email_verified:
        # Publicar reviews requiere email_verified=true (Seccion 2.4): dificulta
        # granjas de cuentas falsas y ayuda al modulo anti-fraude de la Fase 4.
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, detail="Debes verificar tu email para publicar resenas"
        )

    review = Review(
        movie_id=movie_id,
        user_id=user.id,
        rating_id=rating_id,
        body=body,
        moderation_status=ModerationStatus.approved,  # default hasta que exista Fase 4
    )
    db.add(review)
    await db.commit()
    return review


async def delete_review(db: AsyncSession, user_id: uuid.UUID, review_id: uuid.UUID) -> None:
    review = await db.get(Review, review_id)
    if review is None or review.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Resena no encontrada")
    if review.user_id != user_id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, detail="Solo el autor puede borrar su resena"
        )
    review.deleted_at = datetime.now(UTC)
    await db.commit()


async def vote_review(
    db: AsyncSession, user_id: uuid.UUID, review_id: uuid.UUID, is_helpful: bool
) -> None:
    existing = await db.scalar(
        select(ReviewVote).where(ReviewVote.review_id == review_id, ReviewVote.user_id == user_id)
    )
    if existing:
        existing.is_helpful = is_helpful
    else:
        db.add(ReviewVote(review_id=review_id, user_id=user_id, is_helpful=is_helpful))
    await db.commit()


async def create_list(db: AsyncSession, user_id: uuid.UUID, name: str, is_public: bool) -> List:
    lst = List(user_id=user_id, name=name, is_watchlist=False, is_public=is_public)
    db.add(lst)
    await db.commit()
    return lst


async def add_item_to_list(
    db: AsyncSession, user_id: uuid.UUID, list_id: uuid.UUID, movie_id: int
) -> None:
    lst = await db.get(List, list_id)
    if lst is None or lst.user_id != user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Lista no encontrada")
    existing = await db.scalar(
        select(ListItem).where(ListItem.list_id == list_id, ListItem.movie_id == movie_id)
    )
    if existing is None:
        db.add(ListItem(list_id=list_id, movie_id=movie_id))
        await db.commit()


async def remove_item_from_list(
    db: AsyncSession, user_id: uuid.UUID, list_id: uuid.UUID, movie_id: int
) -> None:
    lst = await db.get(List, list_id)
    if lst is None or lst.user_id != user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Lista no encontrada")
    item = await db.scalar(
        select(ListItem).where(ListItem.list_id == list_id, ListItem.movie_id == movie_id)
    )
    if item is not None:
        await db.delete(item)
        await db.commit()
