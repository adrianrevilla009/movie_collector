"""Capa bronze: append-only, nunca UPDATE ni DELETE (ver docs/adr/0001)."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Enum, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from platform_core.db import Base


class BronzeSource(str, enum.Enum):
    tmdb = "tmdb"
    omdb = "omdb"
    movielens = "movielens"


class BronzeEntityType(str, enum.Enum):
    movie = "movie"
    person = "person"
    collection = "collection"
    credit = "credit"
    genre = "genre"
    watch_provider = "watch_provider"
    keyword = "keyword"


class BronzeIngestion(Base):
    """Payload crudo tal cual llega de la fuente, con su timestamp de ingesta.
    Nunca se sobrescribe un registro; una correccion de la fuente = fila nueva."""

    __tablename__ = "bronze_ingestions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source: Mapped[BronzeSource] = mapped_column(Enum(BronzeSource, name="bronze_source"))
    entity_type: Mapped[BronzeEntityType] = mapped_column(
        Enum(BronzeEntityType, name="bronze_entity_type")
    )
    external_id: Mapped[str] = mapped_column(String(64), index=True)
    raw_payload: Mapped[dict] = mapped_column(JSON)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    ingestion_run_id: Mapped[str] = mapped_column(String(64), index=True)
