"""Feature store minimo (Fase 1, entregables). No es Feast: es un almacen
clave-valor con upsert por (entity_type, entity_id, feature_name) - lo justo
para que el recomendador (Fase 2) y el resto de modulos compartan features
precalculadas sin que cada uno reinvente su propia tabla (ver ADR 0004 y
Seccion 7 "Feature store propio vs. Feast" - se revisita ahi si esto se
convierte en cuello de botella)."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.models import FeatureValue


async def set_feature(
    db: AsyncSession, entity_type: str, entity_id: str, feature_name: str, value: object
) -> FeatureValue:
    """Upsert (Postgres `ON CONFLICT DO UPDATE`): recalcular una feature no
    debe acumular historico de versiones a este nivel de madurez - solo se
    guarda el valor mas reciente."""
    now = datetime.now(UTC)
    stmt = (
        insert(FeatureValue)
        .values(
            entity_type=entity_type,
            entity_id=entity_id,
            feature_name=feature_name,
            value={"value": value},
            computed_at=now,
        )
        .on_conflict_do_update(
            index_elements=["entity_type", "entity_id", "feature_name"],
            set_={"value": {"value": value}, "computed_at": now},
        )
        .returning(FeatureValue)
    )
    result = await db.execute(stmt)
    await db.commit()
    return result.scalar_one()


async def get_features(db: AsyncSession, entity_type: str, entity_id: str) -> list[FeatureValue]:
    result = await db.scalars(
        select(FeatureValue).where(
            FeatureValue.entity_type == entity_type, FeatureValue.entity_id == entity_id
        )
    )
    return list(result)
