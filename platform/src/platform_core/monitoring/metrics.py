"""Monitorizacion base (Fase 1, entregables: "logs + metricas"). Se usa
`prometheus_client` directamente (sin exporter aparte) porque el stack de
observabilidad ya provisiona Prometheus con scrape nativo (Seccion 4.1,
profile `observability`) - no hace falta nada mas para que las metricas
lleguen a Grafana.

Se cablea aqui (no en cada router) para que cualquier modulo de dominio que
sirva predicciones a traves del contrato de la Fase 1 (`serving_service`)
quede instrumentado gratis, sin tener que repetir el boilerplate de metricas
en cada uno de los 4 modulos.
"""

from prometheus_client import Counter, Gauge, Histogram

# Contador de predicciones servidas, por modelo/version/resultado - permite
# ver en el dashboard que modelos reciben trafico y su tasa de error.
PREDICTIONS_TOTAL = Counter(
    "ml_predictions_total",
    "Numero total de predicciones servidas a traves del contrato de serving",
    ["model_name", "model_version", "status"],
)

# Latencia de servir una prediccion - la Fase 1 no fija un SLO todavia, pero
# sin esta metrica ningun modulo posterior podria detectar regresiones de
# latencia al cambiar de modelo dummy a modelo real.
PREDICTION_LATENCY_SECONDS = Histogram(
    "ml_prediction_latency_seconds",
    "Latencia de una prediccion servida a traves del contrato de serving",
    ["model_name"],
)

# Gauge de modelos registrados actualmente en produccion, por nombre logico -
# la senal minima de "salud del registry" que pide el DoD de Fase 1
# ("ver sus metricas basicas en el dashboard").
MODELS_IN_PRODUCTION = Gauge(
    "ml_models_in_production",
    "1 si el modelo (name) tiene una version activa en stage=production, 0 si no",
    ["name"],
)
