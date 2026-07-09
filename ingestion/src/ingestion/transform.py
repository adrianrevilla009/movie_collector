"""Transformacion bronze -> silver (ver docs/adr/0001).

Lee el ultimo registro bronze por external_id y hace upsert en las tablas
tipadas de catalogo. Nunca escribe directamente bronze->gold saltandose esta
capa (regla dura de mlops-pipelines).
"""

import structlog
from platform_core.models import BronzeEntityType, BronzeIngestion, BronzeSource, Movie
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

logger = structlog.get_logger("ingestion.transform")

# Filtro de calidad, no de cobertura (Seccion 2.1): se marca "completo" solo lo
# que tiene senal minima; el 100% de IDs se ingesta igualmente en bronze.
MIN_VOTE_COUNT_FOR_COMPLETE = 1


def _is_complete(payload: dict) -> bool:
    has_votes = payload.get("vote_count", 0) > 0
    has_overview = bool(payload.get("overview", "").strip())
    return has_votes or has_overview


async def transform_bronze_to_silver(db_session_factory: async_sessionmaker) -> dict:
    async with db_session_factory() as session:
        # Ultimo registro bronze por external_id (ventana: MAX(ingested_at) por id)
        latest_per_movie = (
            select(
                BronzeIngestion.external_id,
                func.max(BronzeIngestion.ingested_at).label("max_ts"),
            )
            .where(
                BronzeIngestion.source == BronzeSource.tmdb,
                BronzeIngestion.entity_type == BronzeEntityType.movie,
            )
            .group_by(BronzeIngestion.external_id)
            .subquery()
        )

        stmt = select(BronzeIngestion).join(
            latest_per_movie,
            (BronzeIngestion.external_id == latest_per_movie.c.external_id)
            & (BronzeIngestion.ingested_at == latest_per_movie.c.max_ts),
        )
        result = await session.scalars(stmt)

        upserted = 0
        excluded_adult = 0
        for bronze_row in result:
            payload = bronze_row.raw_payload
            if payload.get("adult", False):
                # Se excluye adult=true desde el backfill/transform (Seccion 2.7),
                # no se filtra a posteriori en la API.
                excluded_adult += 1
                continue

            movie_id = int(bronze_row.external_id)
            movie = await session.get(Movie, movie_id)
            if movie is None:
                movie = Movie(id=movie_id)
                session.add(movie)

            movie.title = payload.get("title", "")
            movie.original_title = payload.get("original_title")
            movie.overview = payload.get("overview")
            movie.release_date = payload.get("release_date") or None
            movie.popularity = payload.get("popularity")
            movie.vote_count = payload.get("vote_count", 0)
            movie.vote_average = payload.get("vote_average", 0.0)
            movie.adult = False
            movie.is_complete = _is_complete(payload)
            movie.videos = payload.get("videos", {}).get("results", [])
            movie.raw_metadata = payload
            upserted += 1

        await session.commit()

    logger.info("transform_completed", upserted=upserted, excluded_adult=excluded_adult)
    return {"upserted": upserted, "excluded_adult": excluded_adult}
