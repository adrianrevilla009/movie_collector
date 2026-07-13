"""Cliente TMDB async con backoff exponencial y respeto de rate limit (~40 rps).

Nunca reintentos a ritmo fijo contra una API externa (ver mlops-pipelines).
"""

import asyncio
import time

import httpx
import structlog
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from ingestion.config import get_ingestion_settings

settings = get_ingestion_settings()
logger = structlog.get_logger("ingestion.tmdb_client")


def _is_retryable(exc: BaseException) -> bool:
    """401/403/404 son errores permanentes (key invalida, recurso no existe):
    reintentarlos solo malgasta el presupuesto de backoff sin arreglarlos.
    Solo se reintenta lo transitorio: errores de transporte, 429 y 5xx."""
    if isinstance(exc, httpx.TransportError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code == 429 or exc.response.status_code >= 500
    return False


def _log_before_retry(retry_state) -> None:
    exc = retry_state.outcome.exception()
    logger.warning(
        "tmdb_request_retry",
        attempt=retry_state.attempt_number,
        wait_seconds=round(retry_state.next_action.sleep, 1),
        error=str(exc),
    )


class _RateLimiter:
    """Limitador simple de ventana deslizante: no supera N requests/segundo."""

    def __init__(self, rps: float):
        self._interval = 1.0 / rps
        self._last_call = 0.0
        self._lock = asyncio.Lock()

    async def wait(self) -> None:
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_call
            if elapsed < self._interval:
                await asyncio.sleep(self._interval - elapsed)
            self._last_call = time.monotonic()


class TMDBClient:
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or settings.tmdb_api_key
        self._client = httpx.AsyncClient(base_url=settings.tmdb_base_url, timeout=15.0)
        self._limiter = _RateLimiter(settings.tmdb_requests_per_second)

    async def aclose(self) -> None:
        await self._client.aclose()

    @retry(
        retry=retry_if_exception(_is_retryable),
        wait=wait_exponential(multiplier=1, min=1, max=30),
        stop=stop_after_attempt(5),
        before_sleep=_log_before_retry,
        reraise=True,
    )
    async def _get(self, path: str, params: dict | None = None) -> dict:
        await self._limiter.wait()
        params = {**(params or {}), "api_key": self.api_key, "language": "es-ES"}
        resp = await self._client.get(path, params=params)
        if resp.status_code == 429:
            # Respeta el header Retry-After si TMDB lo manda; si no, deja que
            # tenacity aplique el backoff exponencial por defecto.
            retry_after = float(resp.headers.get("Retry-After", 1))
            await asyncio.sleep(retry_after)
            resp.raise_for_status()
        resp.raise_for_status()
        return resp.json()

    async def get_movie(self, movie_id: int) -> dict:
        """append_to_response minimiza el numero de llamadas (Seccion decision
        de diseno del plan): creditos + imagenes + keywords + videos + watch
        providers en una sola peticion."""
        return await self._get(
            f"/movie/{movie_id}",
            {"append_to_response": "credits,images,keywords,videos,watch/providers"},
        )

    async def get_changed_movie_ids(self, start_date: str, end_date: str) -> list[int]:
        """/movie/changes (Seccion 2.1): sincronizacion incremental diaria,
        checkpoint separado del backfill completo."""
        page = 1
        ids: list[int] = []
        while True:
            data = await self._get(
                "/movie/changes", {"start_date": start_date, "end_date": end_date, "page": page}
            )
            ids.extend(item["id"] for item in data.get("results", []))
            if page >= data.get("total_pages", 1):
                break
            page += 1
        return ids