# syntax=docker/dockerfile:1
FROM python:3.12.7-slim AS builder

RUN pip install --no-cache-dir uv==0.11.7
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY platform/pyproject.toml platform/pyproject.toml
COPY platform/src platform/src
COPY ingestion/pyproject.toml ingestion/pyproject.toml
COPY ingestion/src ingestion/src
RUN uv sync --package ingestion --no-dev --frozen

FROM python:3.12.7-slim AS runtime

RUN useradd --create-home --uid 1000 appuser
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY platform/src platform/src
COPY ingestion/src ingestion/src
ENV PATH="/app/.venv/bin:$PATH" PYTHONPATH="/app/platform/src:/app/ingestion/src"
USER appuser

ENTRYPOINT ["python", "-m", "ingestion.cli"]
CMD ["backfill"]
