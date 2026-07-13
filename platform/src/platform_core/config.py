from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# config.py vive en platform/src/platform_core/config.py; la raiz del repo
# (donde vive el .env real) esta 3 niveles arriba. Se resuelve como ruta
# absoluta a proposito: pydantic-settings resuelve env_file relativo al
# directorio de trabajo (CWD) del proceso, no al de este archivo, asi que un
# ".env" relativo se rompe en cuanto alguien ejecuta el comando desde otro
# directorio (ej. `cd platform && alembic upgrade head`) - eso paso de verdad
# probando en Windows y hizo que las credenciales cayeran silenciosamente a
# los valores por defecto ("changeme").
_REPO_ROOT_ENV = Path(__file__).resolve().parents[3] / ".env"


class Settings(BaseSettings):
    """Configuracion central de la plataforma, cargada desde variables de entorno.

    Nunca hardcodear secretos aqui (ver skill security-antipatterns /
    devops-infra): todo llega via .env en desarrollo, o via el gestor de
    secretos que se decida via ADR cuando exista despliegue en cloud.
    """

    model_config = SettingsConfigDict(env_file=_REPO_ROOT_ENV, extra="ignore")

    # Postgres
    postgres_user: str = "changeme"
    postgres_password: str = "changeme"
    postgres_db: str = "cine_platform"
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Auth
    jwt_secret: str = "changeme"
    jwt_algorithm: str = "HS256"
    jwt_access_ttl_minutes: int = 15
    jwt_refresh_ttl_days: int = 7

    # Email (Mailpit en dev)
    smtp_host: str = "localhost"
    smtp_port: int = 1025

    # CORS
    cors_allowed_origin: str = "http://localhost:5173"

    # Entorno: controla si la cookie de refresh lleva el flag Secure. En dev
    # local (Vite + FastAPI sobre HTTP, sin TLS) Secure=True impediria que el
    # navegador reenviara la cookie nunca - se detecto probando el flujo real
    # de /auth/refresh (ver docs/adr/0002). En production siempre debe ser True.
    environment: str = "development"

    # Region por defecto para watch providers (Seccion 2.3)
    default_region: str = "ES"

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()