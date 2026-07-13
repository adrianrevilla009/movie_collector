"""Registry de modelos (Fase 1, entregables): API interna de registro/consulta
de modelos, compartida por los 4 modulos de dominio."""

import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.models import MLModel, ModelStage
from platform_core.monitoring.metrics import MODELS_IN_PRODUCTION


async def register_model(
    db: AsyncSession,
    name: str,
    framework: str,
    dummy_kind=None,
    dummy_params: dict | None = None,
    artifact_uri: str | None = None,
    metrics: dict | None = None,
    registered_by: uuid.UUID | None = None,
) -> MLModel:
    """Registra una nueva version de `name`. El versionado es automatico
    (siguiente entero) - el cliente nunca elige el numero de version, para
    evitar colisiones/carreras entre registros concurrentes del mismo modelo."""
    current_max = await db.scalar(
        select(func.max(MLModel.version)).where(MLModel.name == name)
    )
    next_version = (current_max or 0) + 1

    model = MLModel(
        name=name,
        version=next_version,
        framework=framework,
        dummy_kind=dummy_kind,
        dummy_params=dummy_params,
        artifact_uri=artifact_uri,
        metrics=metrics,
        registered_by=registered_by,
        stage=ModelStage.staging,
    )
    db.add(model)
    await db.commit()
    await db.refresh(model)
    return model


async def list_models(db: AsyncSession, name: str | None = None) -> list[MLModel]:
    stmt = select(MLModel).order_by(MLModel.name, MLModel.version.desc())
    if name is not None:
        stmt = stmt.where(MLModel.name == name)
    result = await db.scalars(stmt)
    return list(result)


async def get_model_version(db: AsyncSession, name: str, version: int) -> MLModel:
    model = await db.scalar(
        select(MLModel).where(MLModel.name == name, MLModel.version == version)
    )
    if model is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Modelo/version no encontrado")
    return model


async def get_production_model(db: AsyncSession, name: str) -> MLModel:
    """El contrato de serving siempre sirve la version en `production` salvo
    que se pida una version explicita - asi los 4 modulos de dominio pueden
    promocionar una version nueva sin que el endpoint de prediccion cambie."""
    model = await db.scalar(
        select(MLModel)
        .where(MLModel.name == name, MLModel.stage == ModelStage.production)
        .order_by(MLModel.version.desc())
    )
    if model is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail=f"No hay ninguna version de '{name}' en stage=production",
        )
    return model


async def transition_stage(
    db: AsyncSession, name: str, version: int, new_stage: ModelStage
) -> MLModel:
    """Solo puede haber una version en `production` por `name` a la vez: al
    promocionar una, cualquier otra version de ese `name` en `production` pasa
    a `archived` automaticamente - sin esto, `get_production_model` podria
    devolver una version antigua de forma no deterministica."""
    model = await get_model_version(db, name, version)

    if new_stage == ModelStage.production:
        others = await db.scalars(
            select(MLModel).where(
                MLModel.name == name,
                MLModel.stage == ModelStage.production,
                MLModel.id != model.id,
            )
        )
        for other in others:
            other.stage = ModelStage.archived

    model.stage = new_stage
    await db.commit()
    await db.refresh(model)

    is_in_production = 1 if new_stage == ModelStage.production else 0
    MODELS_IN_PRODUCTION.labels(name=name).set(is_in_production)
    return model
