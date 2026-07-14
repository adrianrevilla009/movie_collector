from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.db import get_db
from platform_core.models import User
from platform_core.schemas.ml import (
    FeatureOut,
    FeatureSetRequest,
    ModelOut,
    ModelRegisterRequest,
    PredictionRequest,
    PredictionResponse,
    StageTransitionRequest,
)
from platform_core.security.dependencies import require_admin
from platform_core.services import feature_store_service, registry_service, serving_service

router = APIRouter(prefix="/api/v1/ml", tags=["ml-platform"])


@router.post("/models", response_model=ModelOut, status_code=status.HTTP_201_CREATED)
async def register_model(
    payload: ModelRegisterRequest,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Registrar un modelo requiere `role=admin`: es una operacion de
    plataforma, no de usuario final - igual de sensible que el resto del
    panel de moderacion (Seccion 2.5)."""
    return await registry_service.register_model(
        db,
        name=payload.name,
        framework=payload.framework,
        dummy_kind=payload.dummy_kind,
        dummy_params=payload.dummy_params,
        artifact_uri=payload.artifact_uri,
        metrics=payload.metrics,
        registered_by=admin.id,
    )


@router.get("/models", response_model=list[ModelOut])
async def list_models(name: str | None = None, db: AsyncSession = Depends(get_db)):
    return await registry_service.list_models(db, name=name)


@router.get("/models/{name}/versions/{version}", response_model=ModelOut)
async def get_model_version(name: str, version: int, db: AsyncSession = Depends(get_db)):
    return await registry_service.get_model_version(db, name, version)


@router.post("/models/{name}/versions/{version}/stage", response_model=ModelOut)
async def transition_stage(
    name: str,
    version: int,
    payload: StageTransitionRequest,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    return await registry_service.transition_stage(db, name, version, payload.stage)


@router.post("/models/{name}/predict", response_model=PredictionResponse)
async def predict(name: str, payload: PredictionRequest, db: AsyncSession = Depends(get_db)):
    """Sirve siempre la version en `production` de `name` (Seccion registry_service) -
    el contrato no expone el numero de version en la URL a proposito, para que
    promocionar una version nueva no rompa a los clientes existentes."""
    model = await registry_service.get_production_model(db, name)
    return serving_service.predict_with_model(model, payload.inputs)


@router.put("/features/{entity_type}/{entity_id}", response_model=FeatureOut)
async def set_feature(
    entity_type: str,
    entity_id: str,
    payload: FeatureSetRequest,
    db: AsyncSession = Depends(get_db),
):
    feature = await feature_store_service.set_feature(
        db, entity_type, entity_id, payload.feature_name, payload.value
    )
    return FeatureOut(
        entity_type=feature.entity_type,
        entity_id=feature.entity_id,
        feature_name=feature.feature_name,
        value=feature.value.get("value"),
        computed_at=feature.computed_at,
    )


@router.get("/features/{entity_type}/{entity_id}", response_model=list[FeatureOut])
async def get_features(entity_type: str, entity_id: str, db: AsyncSession = Depends(get_db)):
    features = await feature_store_service.get_features(db, entity_type, entity_id)
    return [
        FeatureOut(
            entity_type=f.entity_type,
            entity_id=f.entity_id,
            feature_name=f.feature_name,
            value=f.value.get("value"),
            computed_at=f.computed_at,
        )
        for f in features
    ]
