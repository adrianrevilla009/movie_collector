"""Integration: Fase 1 - definition of done: "se puede registrar un modelo
dummy, servirlo por la API y ver sus metricas basicas en el dashboard"."""

import pytest

pytestmark = pytest.mark.integration


async def _register_verified_admin(client, session_factory, email="admin@test.com"):
    from platform_core.models import User, UserRole
    from sqlalchemy import select

    password = "correcthorsebattery9"
    await client.post(
        "/api/v1/auth/register", json={"email": email, "name": "Admin", "password": password}
    )
    async with session_factory() as session:
        user = await session.scalar(select(User).where(User.email == email))
        user.email_verified = True
        user.role = UserRole.admin
        await session.commit()
    r = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return r.json()["access_token"]


@pytest.mark.asyncio
async def test_register_promote_and_serve_dummy_model(app_client, db_session_factory):
    admin_token = await _register_verified_admin(app_client, db_session_factory)
    headers = {"Authorization": f"Bearer {admin_token}"}

    # Registrar un modelo dummy (version 1, stage=staging por defecto)
    r = await app_client.post(
        "/api/v1/ml/models",
        json={
            "name": "fraud-smoke-test",
            "framework": "dummy",
            "dummy_kind": "constant",
            "dummy_params": {"value": 0.5},
        },
        headers=headers,
    )
    assert r.status_code == 201
    body = r.json()
    assert body["version"] == 1
    assert body["stage"] == "staging"

    # Servir antes de promocionar debe fallar: no hay ninguna version en produccion
    r = await app_client.post("/api/v1/ml/models/fraud-smoke-test/predict", json={"inputs": {}})
    assert r.status_code == 404

    # Promocionar a produccion
    r = await app_client.post(
        "/api/v1/ml/models/fraud-smoke-test/versions/1/stage",
        json={"stage": "production"},
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json()["stage"] == "production"

    # Ahora si se sirve, con el contrato de prediccion unico
    r = await app_client.post("/api/v1/ml/models/fraud-smoke-test/predict", json={"inputs": {}})
    assert r.status_code == 200
    body = r.json()
    assert body["predictions"] == 0.5
    assert body["model_version"] == 1

    # Registrar una segunda version y promocionarla desplaza a la primera a archived
    r = await app_client.post(
        "/api/v1/ml/models",
        json={
            "name": "fraud-smoke-test",
            "framework": "dummy",
            "dummy_kind": "constant",
            "dummy_params": {"value": 0.9},
        },
        headers=headers,
    )
    assert r.json()["version"] == 2

    await app_client.post(
        "/api/v1/ml/models/fraud-smoke-test/versions/2/stage",
        json={"stage": "production"},
        headers=headers,
    )

    r = await app_client.get("/api/v1/ml/models/fraud-smoke-test/versions/1")
    assert r.json()["stage"] == "archived"

    r = await app_client.post("/api/v1/ml/models/fraud-smoke-test/predict", json={"inputs": {}})
    assert r.json()["predictions"] == 0.9

    # Las metricas basicas del dashboard (Prometheus) reflejan el trafico servido
    r = await app_client.get("/metrics")
    assert r.status_code == 200
    assert 'ml_predictions_total{model_name="fraud-smoke-test"' in r.text


@pytest.mark.asyncio
async def test_register_model_requires_admin(app_client, db_session_factory):
    from platform_core.models import User
    from sqlalchemy import select

    email, password = "user@test.com", "correcthorsebattery9"
    await app_client.post(
        "/api/v1/auth/register", json={"email": email, "name": "U", "password": password}
    )
    async with db_session_factory() as session:
        user = await session.scalar(select(User).where(User.email == email))
        user.email_verified = True
        await session.commit()
    r = await app_client.post("/api/v1/auth/login", json={"email": email, "password": password})
    token = r.json()["access_token"]

    r = await app_client.post(
        "/api/v1/ml/models",
        json={"name": "x", "framework": "dummy", "dummy_kind": "echo"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_feature_store_set_and_get(app_client):
    r = await app_client.put(
        "/api/v1/ml/features/movie/42",
        json={"feature_name": "avg_rating_7d", "value": 4.2},
    )
    assert r.status_code == 200
    assert r.json()["value"] == 4.2

    # Upsert: recalcular la misma feature no crea una segunda fila
    r = await app_client.put(
        "/api/v1/ml/features/movie/42",
        json={"feature_name": "avg_rating_7d", "value": 4.5},
    )
    assert r.status_code == 200

    r = await app_client.get("/api/v1/ml/features/movie/42")
    assert r.status_code == 200
    features = r.json()
    assert len(features) == 1
    assert features[0]["value"] == 4.5
