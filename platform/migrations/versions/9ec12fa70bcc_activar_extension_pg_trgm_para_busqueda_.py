"""activar extension pg_trgm para busqueda tolerante a typos

Revision ID: 9ec12fa70bcc
Revises: 81ea96db5f0d
Create Date: 2026-07-13 15:13:35.363260

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9ec12fa70bcc'
down_revision: Union[str, Sequence[str], None] = '81ea96db5f0d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")
