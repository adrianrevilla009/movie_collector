"""Gestion de cuenta: perfil, cambio de password, borrado logico, portabilidad (Seccion 2.5)."""

import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.models import List, ListItem, Notification, Rating, Review, User
from platform_core.security.passwords import (
    WeakPasswordError,
    hash_password,
    validate_password_strength,
    verify_password,
)
from platform_core.services.auth_service import revoke_all_sessions


async def update_profile(db: AsyncSession, user: User, name: str | None, email: str | None) -> User:
    if name is not None:
        user.name = name
    if email is not None and email != user.email:
        existing = await db.scalar(select(User).where(User.email == email))
        if existing is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, detail="El email ya esta en uso")
        user.email = email
        user.email_verified = False  # cambio de email exige re-verificar
    await db.commit()
    return user


async def change_password(
    db: AsyncSession, user: User, current_password: str, new_password: str
) -> None:
    if not verify_password(current_password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Contrasena actual incorrecta")
    try:
        validate_password_strength(new_password, user_inputs=[user.email, user.name])
    except WeakPasswordError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="; ".join(exc.reasons)) from exc

    user.password_hash = hash_password(new_password)
    await revoke_all_sessions(db, user.id)
    await db.commit()


async def delete_account(db: AsyncSession, user: User) -> None:
    """Borrado logico: se anonimiza email/nombre, se conservan ratings/reviews
    de forma agregada y anonima (Seccion 2.5) - no se borran para no romper
    el entrenamiento del recomendador."""
    user.email = f"deleted-{user.id}@anon.local"
    user.name = "Usuario eliminado"
    user.password_hash = ""
    user.deleted_at = datetime.now(UTC)
    await revoke_all_sessions(db, user.id)
    await db.commit()


async def export_user_data(db: AsyncSession, user_id: uuid.UUID) -> dict:
    ratings = await db.scalars(select(Rating).where(Rating.user_id == user_id))
    reviews = await db.scalars(select(Review).where(Review.user_id == user_id))
    lists = await db.scalars(select(List).where(List.user_id == user_id))
    notifications = await db.scalars(select(Notification).where(Notification.user_id == user_id))

    lists_data = []
    for lst in lists:
        items = await db.scalars(select(ListItem).where(ListItem.list_id == lst.id))
        lists_data.append(
            {
                "id": str(lst.id),
                "name": lst.name,
                "is_public": lst.is_public,
                "movie_ids": [i.movie_id for i in items],
            }
        )

    return {
        "ratings": [{"movie_id": r.movie_id, "score": r.score} for r in ratings],
        "reviews": [{"movie_id": r.movie_id, "body": r.body} for r in reviews],
        "lists": lists_data,
        "notifications": [
            {"type": n.type, "payload": n.payload, "created_at": n.created_at.isoformat()}
            for n in notifications
        ],
    }
