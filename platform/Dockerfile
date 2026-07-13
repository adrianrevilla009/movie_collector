# syntax=docker/dockerfile:1
FROM python:3.12.7-slim AS builder

RUN pip install --no-cache-dir uv==0.11.7
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY platform/pyproject.toml platform/pyproject.toml
COPY platform/src platform/src
RUN uv sync --package platform-core --no-dev --frozen

FROM python:3.12.7-slim AS runtime

RUN useradd --create-home --uid 1000 appuser
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY platform/src platform/src
ENV PATH="/app/.venv/bin:$PATH" PYTHONPATH="/app/platform/src"
USER appuser

EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "platform_core.app:app", "--host", "0.0.0.0", "--port", "8000"]
