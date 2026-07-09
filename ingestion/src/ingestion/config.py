from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class IngestionSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    tmdb_api_key: str = "changeme"
    omdb_api_key: str = "changeme"

    postgres_user: str = "changeme"
    postgres_password: str = "changeme"
    postgres_db: str = "cine_platform"
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    tmdb_base_url: str = "https://api.themoviedb.org/3"
    tmdb_requests_per_second: float = 35.0  # margen bajo el limite real (~40 rps)

    # Alcance de desarrollo (Seccion PLAN de Fase 0.1): subconjunto acotado por
    # defecto; el backfill completo real se lanza explicitamente con --full.
    dev_backfill_limit: int = 10000

    @property
    def sync_database_url(self) -> str:
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_ingestion_settings() -> IngestionSettings:
    return IngestionSettings()
