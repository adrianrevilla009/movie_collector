from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from platform_core.config import get_settings

settings = get_settings()

engine = create_async_engine(settings.database_url, pool_pre_ping=True)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependencia FastAPI: sesion de DB por request, siempre cerrada al final."""
    async with async_session_factory() as session:
        yield session


async def check_db_ready() -> bool:
    """Usado por /health/ready: comprueba que Postgres es alcanzable de verdad,
    no solo que el proceso responde (ver devops-infra: health checks reales)."""
    from sqlalchemy import text

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
