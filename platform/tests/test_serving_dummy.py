import uuid

import pytest
from fastapi import HTTPException
from platform_core.models import DummyModelKind, MLModel, ModelStage
from platform_core.services.serving_service import predict_with_model


def _model(dummy_kind, dummy_params=None) -> MLModel:
    return MLModel(
        id=uuid.uuid4(),
        name="test-model",
        version=1,
        stage=ModelStage.production,
        framework="dummy",
        dummy_kind=dummy_kind,
        dummy_params=dummy_params,
    )


def test_constant_model_always_returns_configured_value():
    model = _model(DummyModelKind.constant, {"value": 42})
    result = predict_with_model(model, {"anything": "ignored"})
    assert result.predictions == 42
    assert result.model_name == "test-model"
    assert result.model_version == 1
    assert result.latency_ms >= 0


def test_constant_model_defaults_to_zero_without_params():
    model = _model(DummyModelKind.constant)
    result = predict_with_model(model, {})
    assert result.predictions == 0.0


def test_echo_model_returns_input_unchanged():
    model = _model(DummyModelKind.echo)
    payload = {"movie_id": 42, "genre": "sci-fi"}
    result = predict_with_model(model, payload)
    assert result.predictions == payload


def test_model_without_dummy_kind_raises_400():
    model = _model(dummy_kind=None)
    with pytest.raises(HTTPException) as exc_info:
        predict_with_model(model, {})
    assert exc_info.value.status_code == 400
