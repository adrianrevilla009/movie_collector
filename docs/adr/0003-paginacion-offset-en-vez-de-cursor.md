# ADR 0003: Paginacion offset (`page`/`size`) en vez de cursor-based

Fecha: 2026-07-13
Estado: aceptada

## Contexto

El plan (Seccion 2.6, version original) fijaba paginacion cursor-based
(`?cursor=...&limit=20`) para listados sin tamano acotado (`GET /movies`,
`GET /movies/{id}/reviews`, `GET /users/me/notifications`), reservando offset
(`?page=...&size=...`) solo para los rankings. Al implementar la Fase 0.3 se
opto por offset de forma consistente en todo el catalogo, incluidos
`GET /movies` y `GET /movies/search`, sin que nadie hubiera reabierto
explicitamente esta decision — quedo como una discrepancia silenciosa entre
el plan y el codigo hasta la revision de cierre de Fase 0.

## Decision

Se fija offset (`?page=...&size=...`) como convencion de paginacion para
`GET /movies`, `GET /movies/search` y los rankings. La Seccion 2.6 se
actualiza para reflejar esto como la decision vigente.

## Motivacion de mantener offset (en vez de migrar a cursor)

- El frontend necesita `total`/`total_pages` para un paginador con numeros de
  pagina (1, 2, 3…), no solo "siguiente/anterior" — eso es mas barato de dar
  con `COUNT(*)` + offset que reconstruyendo el total desde un cursor opaco.
- El desempate estable por `Movie.id` en cada criterio de orden ya resuelve el
  problema que cursor-based evita "gratis" (filas que se solapan o se saltan
  entre paginas cuando hay empates en popularidad/rating/fecha).
- El catalogo real en desarrollo (Seccion 2.1: backfill acotado con
  `INGESTION_DEV_BACKFILL_LIMIT`) esta lejos del ~1M de titulos del backfill
  completo; el coste de `COUNT(*)` sobre `is_complete=True` es hoy despreciable.

## Alternativas consideradas

- **Migrar el codigo a cursor-based para cumplir el plan tal cual**: descartada
  por ahora - habria que rehacer paginacion + tests + frontend ya construidos
  sobre offset, sin un problema de rendimiento real todavia que lo justifique.
- **Cursor solo para `GET /movies`/`search`, offset para el resto**: descartada
  por inconsistencia de API (dos convenciones de paginacion en la misma
  superficie confunde mas de lo que ahorra).

## Consecuencias

- Se gana: consistencia total en la API (una unica convencion de paginacion)
  y un paginador de frontend mas simple de construir.
- Se paga: `COUNT(*)` en cada busqueda/listado. A la escala del backfill
  completo (~1M titulos) esto puede empezar a doler; no se ha medido todavia
  porque el entorno de desarrollo usa un subconjunto acotado.
- Queda pendiente de revisar: si al completar el backfill full (`--full`) el
  `EXPLAIN ANALYZE` de `GET /movies/search` con filtros muestra que el
  `COUNT(*)` domina la latencia, reabrir esta ADR y migrar a cursor-based (o
  a un `COUNT(*)` estimado via `pg_class.reltuples` para listados sin filtro).
