"""Fixtures de integracion: Postgres real via testcontainers (nunca mocks para
esto, ver qa-testing), con las migraciones de Alembic aplicadas.

Requiere Docker disponible - se marcan estos tests con @pytest.mark.integration
y se excluyen del CI rapido (ver ci.yml: `pytest -m "not integration and not e2e"`).
Un job de integracion separado (con Docker disponible en el runner) los correria
sin ese filtro.
"""

import sys
from pathlib import Path

import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer

PLATFORM_ROOT = Path(__file__).resolve().parents[2] / "platform"
sys.path.insert(0, str(PLATFORM_ROOT / "src"))


@pytest.fixture(scope="session")
def postgres_container():
    with PostgresContainer("postgres:16.4") as container:
        yield container


@pytest.fixture(scope="session")
def _migrated_sync_url(postgres_container):
    sync_url = postgres_container.get_connection_url()  # postgresql+psycopg2://...
    alembic_cfg = Config(str(PLATFORM_ROOT / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(PLATFORM_ROOT / "migrations"))
    alembic_cfg.set_main_option("sqlalchemy.url", sync_url)
    command.upgrade(alembic_cfg, "head")
    return sync_url


@pytest_asyncio.fixture
async def db_session_factory(_migrated_sync_url, postgres_container):
    async_url = (
        f"postgresql+asyncpg://{postgres_container.username}:{postgres_container.password}"
        f"@{postgres_container.get_container_host_ip()}:{postgres_container.get_exposed_port(5432)}"
        f"/{postgres_container.dbname}"
    )
    engine = create_async_engine(async_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


@pytest_asyncio.fixture(autouse=True)
async def _clean_database_between_tests(db_session_factory):
    """El Postgres de testcontainers es UNICO para toda la sesion (levantarlo
    por test seria demasiado lento), pero eso significa que los datos de un
    test contaminan el siguiente si no se limpian - varios tests usan
    movie_id=1 a proposito y chocaban con "duplicate key" (encontrado
    corriendo de verdad en CI). TRUNCATE ... CASCADE antes de cada test deja
    la base vacia sin tener que rehacer el contenedor ni las migraciones."""
    async with db_session_factory() as session:
        await session.execute(
            text(
                "TRUNCATE TABLE users, movies, ratings, reviews, review_votes, "
                "lists, list_items, reports, notifications, feedback, "
                "refresh_tokens, email_verification_tokens, password_reset_tokens, "
                "auth_attempts, bronze_ingestions, credits, people, collections, "
                "genres, movie_genres, keywords, movie_keywords, watch_providers "
                "RESTART IDENTITY CASCADE"
            )
        )
        await session.commit()
    yield


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """El limitador de /auth/login (5 intentos/15min) usa almacenamiento en
    memoria compartido por TODO el proceso de pytest, no por test. Sin
    resetearlo, el test de fuerza bruta agota el cupo y arruina cualquier
    test posterior que necesite loguear de verdad (encontrado corriendo en
    CI: 429 en vez del 403/200 esperado en tests que ni tocan ese limite)."""
    from platform_core.security.rate_limit import limiter

    limiter.reset()
    yield
    limiter.reset()


@pytest_asyncio.fixture
async def app_client(db_session_factory, monkeypatch):
    """App FastAPI apuntando al Postgres de test, con envio de email
    interceptado (Mailpit no es necesario para validar la logica de negocio)."""
    import platform_core.db as db_module

    monkeypatch.setattr(db_module, "async_session_factory", db_session_factory)

    async def _get_db_override():
        async with db_session_factory() as session:
            yield session

    import platform_core.email.mailer as mailer_module

    sent_emails: dict[str, str] = {}

    def _fake_send_email(to, subject, body):
        sent_emails[to] = body

    monkeypatch.setattr(mailer_module, "send_email", _fake_send_email)

    from httpx import ASGITransport, AsyncClient
    from platform_core.app import app
    from platform_core.db import get_db

    app.dependency_overrides[get_db] = _get_db_override

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        client.sent_emails = sent_emails  # type: ignore[attr-defined]
        yield client

    app.dependency_overrides.clear()