import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from platform_core.models.ml_platform import DummyModelKind, ModelStage


class ModelRegisterRequest(BaseModel):
    """Registro de un modelo. Los modulos de dominio (Fase 2+) rellenan
    `framework`/`artifact_uri`/`metrics` con datos reales y dejan `dummy_kind`
    a None; los modelos dummy de la Fase 1 hacen lo contrario."""

    name: str = Field(min_length=1, max_length=255)
    framework: str = Field(min_length=1, max_length=64)
    dummy_kind: DummyModelKind | None = None
    dummy_params: dict[str, Any] | None = None
    artifact_uri: str | None = None
    metrics: dict[str, float] | None = None


class ModelOut(BaseModel):
    id: uuid.UUID
    name: str
    version: int
    stage: ModelStage
    framework: str
    dummy_kind: DummyModelKind | None
    artifact_uri: str | None
    metrics: dict[str, Any] | None
    created_at: datetime
    model_config = {"from_attributes": True}


class StageTransitionRequest(BaseModel):
    stage: ModelStage


class PredictionRequest(BaseModel):
    """Contrato de serving unico (Fase 1, entregables): todo modulo que sirva
    predicciones a traves de la plataforma recibe/devuelve esta forma, sin
    importar el framework real por debajo. `inputs` es deliberadamente
    generico (dict) porque cada modulo define su propio esquema de features
    (recomendador != anti-fraude); lo que se fija aqui es el sobre
    (envelope), no el contenido."""

    inputs: dict[str, Any]


class PredictionResponse(BaseModel):
    model_name: str
    model_version: int
    predictions: Any
    latency_ms: float


class FeatureSetRequest(BaseModel):
    feature_name: str
    value: Any


class FeatureOut(BaseModel):
    entity_type: str
    entity_id: str
    feature_name: str
    value: Any
    computed_at: datetime
