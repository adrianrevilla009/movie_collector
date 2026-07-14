"""Tracing distribuido (Tempo, profile `observability`). No es un entregable
de la Fase 1 (que solo pedia "logs + metricas", ver Seccion: Fase 1) - se
anade porque Tempo ya estaba provisionado en el stack de observabilidad y sin
instrumentacion no habia ninguna traza que ver en Grafana.

Diseno deliberadamente best-effort: si Tempo no esta levantado (perfil
`observability` apagado), el `BatchSpanProcessor` falla en background al
exportar y el request sigue funcionando con normalidad - instrumentar nunca
debe poder tumbar la API por un dashboard que nadie esta mirando.
"""

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from platform_core.config import get_settings

settings = get_settings()


def setup_tracing(app: FastAPI) -> None:
    if not settings.otel_enabled:
        return

    resource = Resource(attributes={SERVICE_NAME: settings.otel_service_name})
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=settings.otel_exporter_otlp_endpoint, insecure=True)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    FastAPIInstrumentor.instrument_app(app, tracer_provider=provider)

    # Instrumentar el engine de SQLAlchemy directamente (no solo FastAPI) es
    # lo que hace que cada query aparezca como un span hijo del request en
    # Tempo - sin esto solo se veria "un span opaco por endpoint", sin poder
    # distinguir si la latencia viene de Postgres o del resto del handler.
    from platform_core.db import engine

    SQLAlchemyInstrumentor().instrument(
        engine=engine.sync_engine, tracer_provider=provider
    )