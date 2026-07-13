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
async def test_search_is_typo_tolerant(app_client, db_session_factory):
    """Regresion: pg_trgm debe estar activo (ver migracion 9ec12fa70bcc). Sin
    la extension, /movies/search devuelve 500 en vez de resultados tolerantes
    a errores tipograficos - esto es justo lo que fallo en produccion."""
    await _seed_movie(db_session_factory, movie_id=1, title="Toy Story")

    r = await app_client.get("/api/v1/movies/search", params={"q": "toy stroy"})
    assert r.status_code == 200
    assert any(m["title"] == "Toy Story" for m in r.json()["items"])


@pytest.mark.asyncio
async def test_movies_pagination_pages_do_not_overlap(app_client, db_session_factory):
    """Regresion: ORDER BY sin desempate estable podia repetir o saltarse
    peliculas entre paginas con OFFSET/LIMIT (encontrado probando en real)."""
    for i in range(1, 26):
        await _seed_movie(db_session_factory, movie_id=i, title=f"Pelicula {i}", vote_count=10 + i)

    r1 = await app_client.get("/api/v1/movies", params={"page": 1, "size": 10})
    r2 = await app_client.get("/api/v1/movies", params={"page": 2, "size": 10})
    d1, d2 = r1.json(), r2.json()

    assert d1["total"] == 25
    assert d1["total_pages"] == 3
    ids1 = {m["id"] for m in d1["items"]}
    ids2 = {m["id"] for m in d2["items"]}
    assert ids1.isdisjoint(ids2)
    assert len(ids1) == 10
    assert len(ids2) == 10


@pytest.mark.asyncio
async def test_rankings_top_rated_pagination(app_client, db_session_factory):
    """Mismo regresion que arriba, pero para el ranking bayesiano (tiene su
    propio ORDER BY independiente del listado normal)."""
    for i in range(1, 16):
        await _seed_movie(
            db_session_factory, movie_id=i, title=f"Rankeada {i}", vote_count=100, vote_average=7.0
        )

    r1 = await app_client.get("/api/v1/rankings/top-rated", params={"page": 1, "size": 10})
    r2 = await app_client.get("/api/v1/rankings/top-rated", params={"page": 2, "size": 10})
    d1, d2 = r1.json(), r2.json()

    assert d1["total"] == 15
    ids1 = {m["id"] for m in d1["items"]}
    ids2 = {m["id"] for m in d2["items"]}
    assert ids1.isdisjoint(ids2)


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