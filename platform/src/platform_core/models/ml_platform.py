"""Fase 1 - Plataforma ML interna (el backbone): registry de modelos y feature
store minimo, compartidos por los 4 modulos de dominio (Seccion 6).

Decision de diseno (ver ADR 0004): el registry NO envuelve MLflow directamente
en esta fase. La fuente de verdad del contrato que consumen los modulos de
dominio es esta tabla en Postgres, no un servicio externo — asi el "contrato
de serving unico" (Fase 1, entregables) sigue funcionando aunque MLflow no
este levantado (profile `storage` es opcional en desarrollo). MLflow se
reserva para tracking de experimentos reales cuando exista un modelo
entrenado de verdad (Fase 2+); nada aqui impide anadir esa integracion mas
adelante sin romper el contrato ya fijado.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from platform_core.db import Base


class ModelStage(str, enum.Enum):
    """Ciclo de vida minimo de un modelo registrado. Solo puede haber un
    modelo en `production` por `name` a la vez (ver registry_service)."""

    staging = "staging"
    production = "production"
    archived = "archived"


class DummyModelKind(str, enum.Enum):
    """Tipos de modelo "dummy" que el serving generico de la Fase 1 sabe
    ejecutar sin depender de un framework de ML real (Seccion: Fase 1,
    definition of done - "registrar un modelo dummy, servirlo por la API").
    Los modulos de dominio (Fase 2+) no usan estos kinds: registran su propio
    `artifact_uri` y sirven sus predicciones desde su propio servicio,
    reutilizando solo el contrato de request/response (ver
    `platform_core.schemas.ml`) y el registry para versionado/metricas.
    """

    constant = "constant"  # siempre devuelve el mismo valor, para smoke-tests
    echo = "echo"  # devuelve el input tal cual, para probar el contrato E2E


class MLModel(Base):
    __tablename__ = "ml_models"
    __table_args__ = (UniqueConstraint("name", "version", name="uq_ml_models_name_version"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), index=True)
    version: Mapped[int] = mapped_column(Integer)
    stage: Mapped[ModelStage] = mapped_column(
        Enum(ModelStage, name="model_stage"), default=ModelStage.staging
    )
    framework: Mapped[str] = mapped_column(String(64))  # ej. "dummy", "lightfm", "sklearn"
    # Para modelos dummy (Fase 1): kind + params bastan para servir sin
    # artefacto real. Para modulos de dominio (Fase 2+): artifact_uri apunta
    # al artefacto real (MinIO/filesystem), dummy_kind queda nulo.
    dummy_kind: Mapped[DummyModelKind | None] = mapped_column(
        Enum(DummyModelKind, name="dummy_model_kind"), nullable=True
    )
    dummy_params: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    artifact_uri: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    metrics: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    registered_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class FeatureValue(Base):
    """Feature store minimo (Fase 1): almacen clave-valor por entidad, sin
    pretender ser Feast. Sirve para que el recomendador (Fase 2) y el resto de
    modulos compartan features precalculadas (ej. `avg_rating_7d` de una
    pelicula) sin que cada modulo reinvente su propia tabla."""

    __tablename__ = "feature_values"
    __table_args__ = (
        UniqueConstraint(
            "entity_type", "entity_id", "feature_name", name="uq_feature_values_entity_feature"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_type: Mapped[str] = mapped_column(String(64), index=True)  # ej. "movie", "user"
    entity_id: Mapped[str] = mapped_column(String(64), index=True)
    feature_name: Mapped[str] = mapped_column(String(128), index=True)
    value: Mapped[dict] = mapped_column(JSON)  # {"value": ...} - JSON para admitir escalar/lista
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
