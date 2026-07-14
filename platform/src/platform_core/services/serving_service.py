"""Capa de serving generica (Fase 1, entregables: "contrato de serving unico
que usaran los 4 modulos"). Esta version de la Fase 1 solo sabe ejecutar
modelos "dummy" (Seccion `DummyModelKind`) para poder cerrar el
definition-of-done ("registrar un modelo dummy, servirlo por la API y ver sus
metricas basicas en el dashboard") sin depender de que exista ya un modelo de
ML real.

Los modulos de dominio (Fase 2+) NO llaman a `run_dummy_inference` - sirven
sus propias predicciones desde su propio servicio (con su framework real:
LightFM, transformers, etc.) y solo reutilizan `PredictionRequest`/
`PredictionResponse` (el sobre) y las metricas de este modulo para quedar
instrumentados igual que este endpoint dummy. Ver ADR 0004.
"""

import time

from fastapi import HTTPException, status

from platform_core.models import DummyModelKind, MLModel
from platform_core.monitoring.metrics import PREDICTION_LATENCY_SECONDS, PREDICTIONS_TOTAL
from platform_core.schemas.ml import PredictionResponse


def _run_dummy_inference(model: MLModel, inputs: dict) -> object:
    params = model.dummy_params or {}

    if model.dummy_kind == DummyModelKind.constant:
        # Siempre devuelve el mismo valor configurado al registrar el modelo -
        # util como smoke-test de que el pipeline registry->serving funciona
        # sin que el resultado dependa del input.
        return params.get("value", 0.0)

    if model.dummy_kind == DummyModelKind.echo:
        # Devuelve el input tal cual - prueba que el contrato de request/
        # response viaja intacto de punta a punta.
        return inputs

    raise HTTPException(
        status.HTTP_400_BAD_REQUEST,
        detail=f"El modelo '{model.name}' no tiene un dummy_kind ejecutable",
    )


def predict_with_model(model: MLModel, inputs: dict) -> PredictionResponse:
    start = time.perf_counter()
    status_label = "ok"
    try:
        predictions = _run_dummy_inference(model, inputs)
        return PredictionResponse(
            model_name=model.name,
            model_version=model.version,
            predictions=predictions,
            latency_ms=(time.perf_counter() - start) * 1000,
        )
    except HTTPException:
        status_label = "error"
        raise
    finally:
        elapsed = time.perf_counter() - start
        PREDICTION_LATENCY_SECONDS.labels(model_name=model.name).observe(elapsed)
        PREDICTIONS_TOTAL.labels(
            model_name=model.name, model_version=str(model.version), status=status_label
        ).inc()
