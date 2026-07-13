"""Rate limiting con slowapi (Seccion 2.4/4.2): limites mas estrictos en /auth/*
que el rate limit general de la API."""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

# 5 intentos / 15 min por IP+email (aplicado explicitamente en el endpoint de login,
# ya que la clave compuesta IP+email no la da get_remote_address por si sola).
LOGIN_RATE_LIMIT = "5/15minutes"
GENERAL_RATE_LIMIT = "100/minute"
