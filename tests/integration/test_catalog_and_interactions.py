"""Integration: Fase 0.3/0.4 - catalogo, ratings, reviews, listas."""

import pytest

pytestmark = pytest.mark.integration


async def _seed_movie(
    session_factory, movie_id=1, title="Matrix", vote_count=1000, vote_average=8.5
):
    from platform_core.models import Movie

    async with session_factory() as session:
        session.add(
            Movie(
                id=movie_id,
                title=title,
                overview="Una simulacion...",
                vote_count=vote_count,
                vote_average=vote_average,
                is_complete=True,
                release_date="1999-03-31",
            )
        )
        await session.commit()


async def _register_and_login(client, email="ana@test.com", password="correcthorsebattery9"):
    await client.post(
        "/api/v1/auth/register", json={"email": email, "name": "Ana", "password": password}
    )
    r = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return r.json()["access_token"]


@pytest.mark.asyncio
async def test_catalog_navigation_without_login(app_client, db_session_factory):
    await _seed_movie(db_session_factory)

    r = await app_client.get("/api/v1/movies/1")
    assert r.status_code == 200
    assert r.json()["title"] == "Matrix"

    r = await app_client.get("/api/v1/movies/search", params={"q": "Matrix"})
    assert r.status_code == 200
    assert len(r.json()["items"]) == 1

    r = await app_client.get("/api/v1/rankings/top-rated")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_rating_upsert_no_duplicates(app_client, db_session_factory):
    await _seed_movie(db_session_factory)
    token = await _register_and_login(app_client)
    headers = {"Authorization": f"Bearer {token}"}

    r = await app_client.post("/api/v1/ratings", json={"movie_id": 1, "score": 3}, headers=headers)
    assert r.status_code == 200

    r = await app_client.post("/api/v1/ratings", json={"movie_id": 1, "score": 5}, headers=headers)
    assert r.status_code == 200
    assert r.json()["score"] == 5

    from platform_core.models import Rating
    from sqlalchemy import func, select

    async with db_session_factory() as session:
        count = await session.scalar(select(func.count(Rating.id)).where(Rating.movie_id == 1))
    assert count == 1  # upsert, no duplicado (Seccion 2.3)


@pytest.mark.asyncio
async def test_review_requires_verified_email(app_client, db_session_factory):
    await _seed_movie(db_session_factory)
    token = await _register_and_login(app_client)
    headers = {"Authorization": f"Bearer {token}"}

    r = await app_client.post(
        "/api/v1/reviews", json={"movie_id": 1, "body": "Genial"}, headers=headers
    )
    assert r.status_code == 403  # email_verified=False por defecto


@pytest.mark.asyncio
async def test_list_creation_and_watchlist_auto_created(app_client, db_session_factory):
    await _seed_movie(db_session_factory)
    token = await _register_and_login(app_client)
    headers = {"Authorization": f"Bearer {token}"}

    r = await app_client.get("/api/v1/users/me/lists", headers=headers)
    assert r.status_code == 200
    assert any(lst["is_watchlist"] for lst in r.json())  # watchlist automatica al registrarse

    r = await app_client.post(
        "/api/v1/lists", json={"name": "Mi lista", "is_public": True}, headers=headers
    )
    assert r.status_code == 201
    list_id = r.json()["id"]

    r = await app_client.post(
        f"/api/v1/lists/{list_id}/items", json={"movie_id": 1}, headers=headers
    )
    assert r.status_code == 200
