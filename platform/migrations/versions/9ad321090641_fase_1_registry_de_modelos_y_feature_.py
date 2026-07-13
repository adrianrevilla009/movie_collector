"""fase 1: registry de modelos y feature store

Revision ID: 9ad321090641
Revises: d50a75a06fdd
Create Date: 2026-07-13 19:44:08.685943

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '9ad321090641'
down_revision: Union[str, Sequence[str], None] = 'd50a75a06fdd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Registry de modelos + feature store minimo (Fase 1, Seccion 6)."""
    model_stage = sa.Enum("staging", "production", "archived", name="model_stage")
    dummy_model_kind = sa.Enum("constant", "echo", name="dummy_model_kind")

    op.create_table(
        "ml_models",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("stage", model_stage, nullable=False, server_default="staging"),
        sa.Column("framework", sa.String(length=64), nullable=False),
        sa.Column("dummy_kind", dummy_model_kind, nullable=True),
        sa.Column("dummy_params", sa.JSON(), nullable=True),
        sa.Column("artifact_uri", sa.String(length=1024), nullable=True),
        sa.Column("metrics", sa.JSON(), nullable=True),
        sa.Column("registered_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("name", "version", name="uq_ml_models_name_version"),
    )
    op.create_index("ix_ml_models_name", "ml_models", ["name"])

    op.create_table(
        "feature_values",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", sa.String(length=64), nullable=False),
        sa.Column("feature_name", sa.String(length=128), nullable=False),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "entity_type", "entity_id", "feature_name", name="uq_feature_values_entity_feature"
        ),
    )
    op.create_index("ix_feature_values_entity_type", "feature_values", ["entity_type"])
    op.create_index("ix_feature_values_entity_id", "feature_values", ["entity_id"])
    op.create_index("ix_feature_values_feature_name", "feature_values", ["feature_name"])


def downgrade() -> None:
    op.drop_table("feature_values")
    op.drop_table("ml_models")
    sa.Enum(name="dummy_model_kind").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="model_stage").drop(op.get_bind(), checkfirst=True)
