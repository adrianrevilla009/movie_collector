# Plataforma de cine/streaming — backbone de ML de extremo a extremo

Proyecto de practica: un backbone de plataforma ML (registry, serving, feature store,
monitorizacion) con cuatro modulos de dominio (recomendador, asistente agentico
multiagente, anti-fraude, entrenamiento distribuido) sobre un dominio de cine/streaming.

Ver el diseno completo en [`docs/implementation-plan.md`](docs/implementation-plan.md) y
el metodo de trabajo por fases en [`docs/working-method.md`](docs/working-method.md).

## Estado actual

**Fase 0 (0.1-0.5) cerrada** y **Fase 1 — Plataforma ML interna (backbone)** implementada:
registry de modelos con versionado/stage, contrato de serving unico, feature store minimo,
y monitorizacion base (Prometheus + dashboard de Grafana provisionado). Siguiente:
Fase 2 (modulo recomendador).

## Estructura del repo

```
platform/       backbone: registry wrapper, contrato de serving, feature store, monitorizacion
modules/        recommender, rag_assistant, fraud_detection, distributed_training
ingestion/      conectores TMDB/OMDb/MovieLens, backfill, transformacion bronze->silver
frontend/       React + TS + Vite, cliente de demo API-first
infra/          terraform (recursos persistentes), compose (servicios), k3d (Fase 6/7)
docs/adr/       Architecture Decision Records (formato Nygard)
tests/          contract, integration, e2e
```

## Quickstart (desarrollo local)

```bash
cp .env.example .env   # rellenar TMDB_API_KEY / OMDB_API_KEY reales
make sync              # instala backend (uv workspace) + frontend (pnpm)
make tf-apply          # crea redes/volumenes persistentes (una vez)
make up                # levanta el profile 'core' de Docker Compose
make ingest             # backfill acotado (dev) + transformacion + seed MovieLens
make seed-admin        # crea el usuario admin de seed (Seccion 2.4)
make test
```

El backend (`platform-core`) y el frontend corren en el host, no como servicios de
Compose (iteracion rapida con `--reload`/HMR):

```bash
cd platform && uv run --package platform-core uvicorn platform_core.app:app --reload
cd frontend && pnpm dev
```

Observabilidad (Prometheus + Grafana, con el dashboard de salud del registry de modelos
de la Fase 1 ya provisionado): `make up-observability`, luego Grafana en
`http://localhost:3000` (admin/admin por defecto).

Requisitos: Python 3.12, Node.js 20 LTS, `uv`, `pnpm`, Docker + Docker Compose v2,
Terraform >= 1.7.

## Convenciones

- Commits: [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `chore:`, `docs:`, `test:`).
- Ramas: `fase-N-<slug>` (ej. `fase-2-recomendador`), merge a `main` via PR.
- Cada decision de arquitectura no trivial se documenta como ADR en `docs/adr/`.
