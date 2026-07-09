"""Seed historico de ratings desde MovieLens, mapeado a IDs TMDB via links.csv
(Seccion 2.2/0.1).

Los usuarios de MovieLens no son cuentas reales de la plataforma: se
modelan como usuarios "seed" sintéticos (rol `user`, sin login posible,
password_hash vacio) para poder respetar la FK de `ratings.user_id` sin
inventar un esquema paralelo. Esto se documenta aqui explicitamente para que
no se confunda con datos de usuarios reales.
"""

import csv
import uuid
from pathlib import Path

import structlog
from platform_core.models import Movie, Rating, RatingSource, User
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

logger = structlog.get_logger("ingestion.movielens_seed")

SEED_USER_NAMESPACE = uuid.UUID("00000000-0000-0000-0000-000000000000")


def _seed_user_id(movielens_user_id: str) -> uuid.UUID:
    """UUID deterministico por userId de MovieLens (mismo input -> mismo UUID),
    para que el seed sea idempotente sin necesitar tabla de mapeo aparte."""
    return uuid.uuid5(SEED_USER_NAMESPACE, f"movielens-{movielens_user_id}")


def load_links_map(links_csv_path: Path) -> dict[str, int]:
    """movieId (MovieLens) -> tmdbId, desde links.csv."""
    mapping: dict[str, int] = {}
    with links_csv_path.open() as f:
        for row in csv.DictReader(f):
            if row.get("tmdbId"):
                mapping[row["movieId"]] = int(row["tmdbId"])
    return mapping


async def seed_ratings_from_movielens(
    db_session_factory: async_sessionmaker,
    ratings_csv_path: Path,
    links_csv_path: Path,
    limit: int | None = None,
) -> dict:
    if not ratings_csv_path.exists() or not links_csv_path.exists():
        raise FileNotFoundError(
            "Archivos de MovieLens no encontrados. Descargalos desde "
            "https://grouplens.org/datasets/movielens/ y coloca ratings.csv y "
            "links.csv en la ruta configurada (esta descarga no es automatica: "
            "GroupLens no forma parte de las APIs con backfill programado)."
        )

    links_map = load_links_map(links_csv_path)

    inserted = 0
    skipped_no_tmdb_mapping = 0
    skipped_movie_not_in_catalog = 0

    async with db_session_factory() as session:
        seen_users: set[uuid.UUID] = set()

        with ratings_csv_path.open() as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                if limit is not None and i >= limit:
                    break

                ml_movie_id = row["movieId"]
                tmdb_id = links_map.get(ml_movie_id)
                if tmdb_id is None:
                    skipped_no_tmdb_mapping += 1
                    continue

                movie = await session.get(Movie, tmdb_id)
                if movie is None:
                    skipped_movie_not_in_catalog += 1
                    continue

                user_id = _seed_user_id(row["userId"])
                if user_id not in seen_users:
                    existing_user = await session.get(User, user_id)
                    if existing_user is None:
                        session.add(
                            User(
                                id=user_id,
                                email=f"movielens-seed-{row['userId']}@seed.local",
                                name=f"Usuario seed {row['userId']}",
                                password_hash="",  # sin login posible
                                email_verified=False,
                            )
                        )
                    seen_users.add(user_id)

                existing_rating = await session.scalar(
                    select(Rating).where(Rating.movie_id == tmdb_id, Rating.user_id == user_id)
                )
                if existing_rating is None:
                    # MovieLens usa escala 0.5-5.0; se redondea a entero 1-5 (Seccion 2.3)
                    score = max(1, min(5, round(float(row["rating"]))))
                    session.add(
                        Rating(
                            movie_id=tmdb_id, user_id=user_id, score=score, source=RatingSource.seed
                        )
                    )
                    inserted += 1

        await session.commit()

    logger.info(
        "movielens_seed_completed",
        inserted=inserted,
        skipped_no_tmdb_mapping=skipped_no_tmdb_mapping,
        skipped_movie_not_in_catalog=skipped_movie_not_in_catalog,
    )
    return {
        "inserted": inserted,
        "skipped_no_tmdb_mapping": skipped_no_tmdb_mapping,
        "skipped_movie_not_in_catalog": skipped_movie_not_in_catalog,
    }
