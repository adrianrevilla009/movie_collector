"""indices gin para busqueda full-text y trigram en movies

Revision ID: d50a75a06fdd
Revises: 9ec12fa70bcc
Create Date: 2026-07-13 19:33:57.780095

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd50a75a06fdd'
down_revision: Union[str, Sequence[str], None] = '9ec12fa70bcc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Indices GIN para que la busqueda de la Seccion 2.3 no haga sequential
    scan sobre movies a escala de catalogo completo (~1M titulos, Seccion 2.1).
    `pg_trgm` ya estaba activado en la migracion anterior pero sin indice
    ningun `similarity()`/`to_tsvector()` lo aprovechaba - gap detectado en la
    revision de cierre de Fase 0.

    Sin CONCURRENTLY porque Alembic ejecuta cada migracion dentro de una
    transaccion por defecto (CONCURRENTLY no esta permitido dentro de una
    transaccion); a la escala de desarrollo actual el bloqueo breve de CREATE
    INDEX normal es aceptable. Revisar si se necesita CONCURRENTLY (via
    `op.get_bind().execute(text(...))` con autocommit) cuando se corra contra
    el catalogo completo en un entorno con trafico concurrente real.
    """
    op.execute(
        "CREATE INDEX ix_movies_title_trgm ON movies USING gin (title gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX ix_movies_search_tsv ON movies USING gin ("
        "to_tsvector('spanish', title || ' ' || coalesce(overview, ''))"
        ")"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_movies_search_tsv")
    op.execute("DROP INDEX IF EXISTS ix_movies_title_trgm")
