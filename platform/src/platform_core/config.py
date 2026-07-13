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

    # Seed de admin (Seccion 2.4, `make seed-admin`): se leen aqui via
    # pydantic-settings (igual que el resto de la config) en vez de pasarse
    # como argumentos de shell desde el Makefile - `make` en Windows invoca
    # cmd.exe por defecto, que no entiende sintaxis POSIX (`set -a`, `. ./.env`),
    # asi que cualquier logica de carga de .env debia vivir en Python, no en
    # el Makefile, para funcionar igual en Windows/Mac/Linux.
    admin_email: str = "admin@cine-platform.local"
    admin_password: str = "changeme"
    admin_name: str = "Admin"

    # Tracing (Tempo, profile `observability`): el backend corre en el host
    # (uvicorn --reload, ver Makefile/README), no dentro de la red `core` de
    # Docker - por eso el endpoint por defecto es `localhost`, aprovechando
    # que el puerto 4317 de Tempo ya se publica al host en docker-compose.dev.yml
    # (igual que el ajuste de Prometheus->host.docker.internal, pero en sentido
    # inverso: aqui es la app quien sale hacia el contenedor, no al reves).
    otel_service_name: str = "platform-core"
    otel_exporter_otlp_endpoint: str = "localhost:4317"
    # Apagable explicitamente (ej. en tests o si no se ha levantado el
    # profile observability): el exporter falla en silencio si Tempo no esta
    # arriba (BatchSpanProcessor es best-effort), pero evita el overhead/ruido
    # de intentarlo cuando se sabe de antemano que no hace falta.
    otel_enabled: bool = True

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()