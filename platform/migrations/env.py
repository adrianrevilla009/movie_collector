import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from platform_core import models  # noqa: E402,F401  (registra todas las tablas en Base.metadata)
from platform_core.config import get_settings  # noqa: E402
from platform_core.db import Base  # noqa: E402

config = context.config
settings = get_settings()

sync_url = settings.database_url.replace("+asyncpg", "")
config.set_main_option("sqlalchemy.url", sync_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from platform_core import models  # noqa: E402,F401  (registra todas las tablas en Base.metadata)
from platform_core.config import get_settings  # noqa: E402
from platform_core.db import Base  # noqa: E402

config = context.config
settings = get_settings()

# alembic.ini trae un placeholder por defecto (Config.set_main_option nunca
# devuelve None una vez leido el .ini). Si alguien ya fijo una URL real de
# forma programatica ANTES de invocar alembic (ej. los tests de integracion,
# que apuntan al Postgres efimero de testcontainers, no al de desarrollo),
# hay que respetarla - sobreescribirla siempre aqui rompia esos tests, que
# acababan migrando la base de datos equivocada sin dar ningun error.
_PLACEHOLDER_URL = "driver://user:pass@localhost/dbname"
if config.get_main_option("sqlalchemy.url") == _PLACEHOLDER_URL:
    sync_url = settings.database_url.replace("+asyncpg", "")
    config.set_main_option("sqlalchemy.url", sync_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()