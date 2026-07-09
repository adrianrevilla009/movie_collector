# ADR 0001: Separacion explicita de capa bronze y capa silver en el esquema de datos

Fecha: 2026-07-09
Estado: aceptada

## Contexto

El plan de implementacion (Seccion 4.8) lista un conjunto de "tablas nucleo de la capa
bronze/silver" (`movies`, `people`, `credits`, `collections`, `genres`, etc.) sin separar
explicitamente que parte de ese esquema es bronze y cual es silver. La skill
`mlops-pipelines` exige que bronze sea estrictamente append-only (nunca se sobrescribe un
registro; si TMDB corrige un dato, se anade un nuevo registro con nueva fecha de ingesta),
mientras que las tablas tipadas que sirven el catalogo (`movies`, etc.) necesitan poder
actualizarse (UPDATE) para reflejar el estado actual conocido. Combinar ambas cosas en la
misma tabla rompe una de las dos garantias: o bronze deja de ser append-only (se pierde
reproducibilidad de "que sabiamos en el momento X"), o silver se vuelve insert-only con
duplicados masivos por titulo (impractico para servir catalogo).

## Decision

Se separan explicitamente dos capas de tablas en Postgres:

- **Bronze**: tabla unica `bronze_ingestions` (append-only, nunca UPDATE ni DELETE) con
  columnas `id`, `source` (enum `tmdb|omdb|movielens`), `entity_type`
  (`movie|person|collection|credit|genre|watch_provider|keyword`), `external_id`,
  `raw_payload JSONB`, `ingested_at`, `ingestion_run_id`. Cada backfill o sincronizacion
  incremental escribe aqui el payload crudo tal cual llega de la fuente, sin transformar.
- **Silver**: las tablas tipadas de la Seccion 4.8 (`movies`, `people`, `credits`,
  `collections`, `genres`, `movie_genres`, `keywords`, `watch_providers`), pobladas y
  actualizadas por un job de transformacion que lee el ultimo registro `bronze_ingestions`
  por `external_id` y hace upsert en la tabla tipada correspondiente.

## Alternativas consideradas

- **Combinado (JSONB crudo + columnas tipadas en la misma tabla, particionado por fecha
  de ingesta)**: descartada. Requeriria particionado explicito para no perder el
  append-only, anadiendo complejidad de gestion de particiones sin ganar nada frente a
  una tabla bronze dedicada; ademas mezclaria en una sola tabla dos patrones de acceso
  distintos (lectura de "estado actual" vs. lectura de "historial de ingesta").

## Consecuencias

- Se gana: reproducibilidad real de bronze (auditable, cumple la regla dura de
  `mlops-pipelines`), y tablas silver simples de consultar para servir catalogo sin logica
  de particionado.
- Se paga: un job de transformacion bronze->silver adicional (parte del incremento de
  ingestion de la Fase 0.1) y algo mas de almacenamiento (el payload crudo se guarda una
  vez por cada sync que trae cambios, no una vez total por entidad).
- Queda pendiente de revisar: si el volumen de `bronze_ingestions` crece de forma
  problematica (backfill completo ~1M titulos), evaluar particionado por `ingested_at` o
  purga de versiones bronze muy antiguas — no bloqueante para la Fase 0.1.
