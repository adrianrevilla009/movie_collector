.PHONY: up up-core up-assistant up-fraud up-observability up-storage down \
        ingest test lint tf-plan tf-apply sync

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

test:
	uv run pytest

lint:
	uv run ruff check .
	cd frontend && pnpm lint

tf-plan:
	cd infra/terraform && terraform fmt -check && terraform plan

tf-apply:
	cd infra/terraform && terraform init && terraform apply