.PHONY: up up-core up-assistant up-fraud up-observability up-storage down \
        ingest test lint tf-plan tf-apply sync seed-admin run-backend

COMPOSE_FILE := infra/compose/docker-compose.dev.yml
COMPOSE := docker compose -f $(COMPOSE_FILE) --env-file .env

## Instala todo el monorepo (uv workspace) + frontend (pnpm)
sync:
	uv sync --all-packages
	cd frontend && pnpm install

## Levanta el profile 'core' (servicios minimos: postgres, redis)
up: up-core

up-core:
	$(COMPOSE) --profile core up -d

up-assistant:
	$(COMPOSE) --profile assistant up -d

up-fraud:
	$(COMPOSE) --profile fraud up -d

up-observability:
	$(COMPOSE) --profile observability up -d

up-storage:
	$(COMPOSE) --profile storage up -d

down:
	$(COMPOSE) down

## Aplica las migraciones de Alembic (necesario tras el primer `up-core`
## o siempre que se recree el volumen de Postgres desde cero)
migrate:
	cd platform && uv run --package platform-core alembic upgrade head

## Backfill + sincronizacion incremental del catalogo (bronze -> silver)
## Por defecto usa el alcance acotado de desarrollo (INGESTION_DEV_BACKFILL_LIMIT).
## Backfill completo real: make ingest ARGS="--full"
ingest: migrate
	uv run --package ingestion python -m ingestion.cli backfill $(ARGS)
	uv run --package ingestion python -m ingestion.cli transform
	uv run --package ingestion python -m ingestion.cli seed-movielens

## Crea (o promueve, si ya existe) el usuario admin de seed (Seccion 2.4).
## Requiere migraciones ya aplicadas. Lee ADMIN_EMAIL/ADMIN_PASSWORD/ADMIN_NAME
## de .env directamente en Python (ver seed_admin.py) - nada de sintaxis de
## shell aqui, para que funcione igual en Windows (cmd.exe), Mac y Linux.
seed-admin: migrate
	uv run --package platform-core python -m platform_core.scripts.seed_admin

## Levanta el backend en modo desarrollo (hot-reload). Se ejecuta SIEMPRE
## desde la raiz del repo (nunca `cd platform` antes) para usar el .venv
## compartido del workspace - si se invoca `uv run` desde dentro de
## platform/, uv trata ese directorio como su propio proyecto y usa/crea un
## .venv aislado ahi, que nunca recibe lo que instala `make sync` en la raiz.
run-backend:
	uv run --package platform-core uvicorn platform_core.app:app --reload

test:
	uv run pytest

lint:
	uv run ruff check .
	cd frontend && pnpm lint

tf-plan:
	cd infra/terraform && terraform fmt -check && terraform plan

tf-apply:
	cd infra/terraform && terraform init && terraform apply