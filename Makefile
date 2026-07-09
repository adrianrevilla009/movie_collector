.PHONY: up up-core up-assistant up-fraud up-observability up-storage down \
        ingest test lint tf-plan tf-apply sync

COMPOSE_FILE := infra/compose/docker-compose.dev.yml

## Instala todo el monorepo (uv workspace) + frontend (pnpm)
sync:
	uv sync --all-packages
	cd frontend && pnpm install

## Levanta el profile 'core' (servicios minimos: postgres, redis)
up: up-core

up-core:
	docker compose -f $(COMPOSE_FILE) --profile core up -d

up-assistant:
	docker compose -f $(COMPOSE_FILE) --profile assistant up -d

up-fraud:
	docker compose -f $(COMPOSE_FILE) --profile fraud up -d

up-observability:
	docker compose -f $(COMPOSE_FILE) --profile observability up -d

up-storage:
	docker compose -f $(COMPOSE_FILE) --profile storage up -d

down:
	docker compose -f $(COMPOSE_FILE) down

## Backfill + sincronizacion incremental del catalogo (bronze -> silver)
## Por defecto usa el alcance acotado de desarrollo (INGESTION_DEV_BACKFILL_LIMIT).
## Backfill completo real: make ingest ARGS="--full"
ingest:
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
	cd infra/terraform && terraform apply
