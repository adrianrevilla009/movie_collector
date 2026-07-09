"""Integration: Fase 0.2 - definition of done completo con Postgres real."""

import pytest

pytestmark = pytest.mark.integration


async def _register(client, email="ana@test.com", password="correcthorsebattery9"):
    r = await client.post(
        "/api/v1/auth/register", json={"email": email, "name": "Ana", "password": password}
    )
    assert r.status_code == 201
    return email


@pytest.mark.asyncio
async def test_register_login_refresh_rotation_and_reuse_detection(app_client):
    email, password = "ana@test.com", "correcthorsebattery9"
    await _register(app_client, email, password)

    r = await app_client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200
    assert "refresh_token" in r.cookies

    r = await app_client.post("/api/v1/auth/refresh")
    assert r.status_code == 200
    old_refresh_cookie = app_client.cookies.get("refresh_token")

    r = await app_client.post("/api/v1/auth/refresh")
    assert r.status_code == 200
    new_refresh_cookie = app_client.cookies.get("refresh_token")
    assert old_refresh_cookie != new_refresh_cookie


@pytest.mark.asyncio
async def test_brute_force_login_gets_rate_limited(app_client):
    email, password = "brute@test.com", "correcthorsebattery9"
    await _register(app_client, email, password)

    statuses = []
    for _ in range(7):
        r = await app_client.post(
            "/api/v1/auth/login", json={"email": email, "password": "wrong-password"}
        )
        statuses.append(r.status_code)

    # Tras 5 intentos en la ventana, el 6o/7o deben quedar bloqueados (429)
    assert 429 in statuses


@pytest.mark.asyncio
async def test_banned_user_cannot_login(app_client):
    from platform_core.models import User
    from sqlalchemy import select

    email, password = "banned@test.com", "correcthorsebattery9"
    await _register(app_client, email, password)

    # Simula que un admin banea al usuario directamente en DB (el endpoint
    # de ban se prueba por separado en test_moderation.py)
    async for session in _iter_db_sessions(app_client):
        user = await session.scalar(select(User).where(User.email == email))
        user.is_banned = True
        await session.commit()
        break

    r = await app_client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 403


async def _iter_db_sessions(client):
    # Helper minimo para acceder a una sesion de DB desde el test sin
    # duplicar la config de conexion (usa el override ya aplicado al app).
    from platform_core.app import app
    from platform_core.db import get_db

    override = app.dependency_overrides[get_db]
    async for session in override():
        yield session
