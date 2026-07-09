"""Backfill del catalogo TMDB hacia bronze (Seccion 2.1).

Idempotente y reanudable: guarda un checkpoint (ultimo indice procesado) fuera
de memoria, en un archivo local, para poder interrumpirse y reanudar sin
duplicar trabajo ni perder progreso (ver mlops-pipelines).
"""

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

import structlog
from platform_core.models import BronzeEntityType, BronzeIngestion, BronzeSource
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from ingestion.config import get_ingestion_settings
from ingestion.tmdb_client import TMDBClient

logger = structlog.get_logger("ingestion.backfill")
settings = get_ingestion_settings()

CHECKPOINT_PATH = Path(".ingestion_checkpoints/backfill.json")


def _load_checkpoint() -> dict:
    if CHECKPOINT_PATH.exists():
        return json.loads(CHECKPOINT_PATH.read_text())
    return {"last_processed_index": -1, "run_id": str(uuid.uuid4())}


def _save_checkpoint(state: dict) -> None:
    CHECKPOINT_PATH.parent.mkdir(parents=True, exist_ok=True)
    CHECKPOINT_PATH.write_text(json.dumps(state))


def load_dev_movie_ids(limit: int) -> list[int]:
    """Alcance de desarrollo (PLAN Fase 0.1): subconjunto acotado de IDs TMDB
    conocidos y populares, en vez del export diario completo (~1M titulos).
    Para el backfill --full real, se sustituye por la descarga del export
    diario de IDs de TMDB (ver Seccion 2.1) - no implementado aqui todavia,
    queda como TODO explicito para cuando se ejecute el backfill de produccion."""
    # Rango simple de IDs bajos de TMDB como placeholder de desarrollo -
    # cubre suficiente variedad (titulos antiguos y modernos) para probar
    # el pipeline sin depender del export completo.
    return list(range(1, limit + 1))


async def run_backfill(
    db_session_factory: async_sessionmaker, movie_ids: list[int], full: bool = False
) -> dict:
    checkpoint = _load_checkpoint()
    start_index = checkpoint["last_processed_index"] + 1
    run_id = checkpoint["run_id"]

    client = TMDBClient()
    processed = 0
    errors = 0

    try:
        for idx in range(start_index, len(movie_ids)):
            movie_id = movie_ids[idx]
            try:
                payload = await client.get_movie(movie_id)
            except Exception as exc:  # fallo esperable de dependencia externa
                logger.warning("backfill_movie_failed", movie_id=movie_id, error=str(exc))
                errors += 1
                continue

            async with db_session_factory() as session:
                session.add(
                    BronzeIngestion(
                        source=BronzeSource.tmdb,
                        entity_type=BronzeEntityType.movie,
                        external_id=str(movie_id),
                        raw_payload=payload,
                        ingested_at=datetime.now(UTC),
                        ingestion_run_id=run_id,
                    )
                )
                await session.commit()

            processed += 1
            checkpoint["last_processed_index"] = idx
            _save_checkpoint(checkpoint)

        logger.info("backfill_completed", processed=processed, errors=errors, full=full)
        return {"processed": processed, "errors": errors, "run_id": run_id}
    finally:
        await client.aclose()


def make_session_factory() -> async_sessionmaker:
    from platform_core.config import get_settings

    platform_settings = get_settings()
    engine = create_async_engine(platform_settings.database_url, pool_pre_ping=True)
    return async_sessionmaker(engine, expire_on_commit=False)
