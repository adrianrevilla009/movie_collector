"""Rate limiting con slowapi (Seccion 2.4/4.2): limites mas estrictos en /auth/*
que el rate limit general de la API."""

from slowapi import Limiter
from slowapi.util import get_remote_address

from platform_core.config import get_settings

settings = get_settings()

# storage_uri=Redis (Seccion 2.4): el bloqueo de fuerza bruta debe compartirse
# entre workers/replicas, no vivir en memoria de un solo proceso - gap detectado
# en la revision de Fase 0.2 (el contador en memoria no sobrevive un reinicio
# ni se comparte entre workers de uvicorn).
limiter = Limiter(key_func=get_remote_address, storage_uri=settings.redis_url)

# 5 intentos / 15 min por IP+email (aplicado explicitamente en el endpoint de login,
# ya que la clave compuesta IP+email no la da get_remote_address por si sola).
LOGIN_RATE_LIMIT = "5/15minutes"
GENERAL_RATE_LIMIT = "100/minute"
