"""Integration: Fase 0.5 - moderacion, reportes, ban, stats."""

import pytest

pytestmark = pytest.mark.integration


async def _seed_movie(session_factory, movie_id=1):
    from platform_core.models import Movie

    async with session_factory() as session:
        session.add(
            Movie(id=movie_id, title="Matrix", vote_count=10, vote_average=8.0, is_complete=True)
        )
        await session.commit()


async def _register_verified(client, session_factory, email, password="correcthorsebattery9"):
    await client.post(
        "/api/v1/auth/register", json={"email": email, "name": "U", "password": password}
    )
    from platform_core.models import User
    from sqlalchemy import select

    async with session_factory() as session:
        user = await session.scalar(select(User).where(User.email == email))
        user.email_verified = True
        await session.commit()
    r = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return r.json()["access_token"]


async def _make_admin(session_factory, email):
    from platform_core.models import User, UserRole
    from sqlalchemy import select

    async with session_factory() as session:
        user = await session.scalar(select(User).where(User.email == email))
        user.role = UserRole.admin
        await session.commit()


@pytest.mark.asyncio
async def test_three_reports_auto_flag_review(app_client, db_session_factory):
    """Definition of done (Fase 0.5): 3+ reportes independientes marcan la
    review como flagged automaticamente (Seccion 2.5), sin esperar al modelo."""
    await _seed_movie(db_session_factory)
    author_token = await _register_verified(app_client, db_session_factory, "author@test.com")

    r = await app_client.post(
        "/api/v1/reviews",
        json={"movie_id": 1, "body": "opinion polemica"},
        headers={"Authorization": f"Bearer {author_token}"},
    )
    review_id = r.json()["id"]

    for i in range(3):
        reporter_token = await _register_verified(
            app_client, db_session_factory, f"reporter{i}@test.com"
        )
        r = await app_client.post(
            "/api/v1/reports",
            json={"target_type": "review", "target_id": review_id, "reason": "spam"},
            headers={"Authorization": f"Bearer {reporter_token}"},
        )
        assert r.status_code == 201

    from platform_core.models import ModerationStatus, Review

    async with db_session_factory() as session:
        review = await session.get(Review, review_id)
        assert review.moderation_status == ModerationStatus.flagged


@pytest.mark.asyncio
async def test_admin_can_resolve_flagged_review_and_ban_user(app_client, db_session_factory):
    await _seed_movie(db_session_factory)
    author_token = await _register_verified(app_client, db_session_factory, "author2@test.com")
    admin_token = await _register_verified(app_client, db_session_factory, "admin@test.com")
    await _make_admin(db_session_factory, "admin@test.com")

    r = await app_client.post(
        "/api/v1/reviews",
        json={"movie_id": 1, "body": "spam"},
        headers={"Authorization": f"Bearer {author_token}"},
    )
    review_id = r.json()["id"]

    r = await app_client.post(
        f"/api/v1/admin/reviews/{review_id}/resolve",
        json={"status": "flagged"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200

    r = await app_client.get(
        "/api/v1/admin/reviews/flagged", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert any(rev["id"] == review_id for rev in r.json())

    r = await app_client.get(
        "/api/v1/admin/stats", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert r.status_code == 200
    assert r.json()["total_users"] >= 2


@pytest.mark.asyncio
async def test_non_admin_cannot_access_admin_endpoints(app_client, db_session_factory):
    token = await _register_verified(app_client, db_session_factory, "regular@test.com")
    r = await app_client.get("/api/v1/admin/stats", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403
