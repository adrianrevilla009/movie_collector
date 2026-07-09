from fastapi import APIRouter

from platform_core.db import check_db_ready

router = APIRouter(tags=["health"])


@router.get("/health")
async def liveness():
    """Liveness: sin dependencias externas (Seccion 2.6)."""
    return {"status": "ok"}


@router.get("/health/ready")
async def readiness():
    """Readiness: comprueba que Postgres es alcanzable de verdad."""
    db_ok = await check_db_ready()
    status_code = "ok" if db_ok else "degraded"
    return {"status": status_code, "postgres": db_ok}
