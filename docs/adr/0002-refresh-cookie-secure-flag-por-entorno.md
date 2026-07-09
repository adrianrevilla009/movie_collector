# ADR 0002: Flag `Secure` de la cookie de refresh condicionado por entorno

Fecha: 2026-07-09
Estado: aceptada

## Contexto

El plan (Seccion 2.4) fija que el refresh token se entrega en una cookie
`httpOnly`, `Secure`, `SameSite=Strict`. Al probar el flujo real de
`POST /auth/login` seguido de `POST /auth/refresh` (in-process, con `httpx`),
se detecto que el navegador (y `httpx`, que respeta las mismas reglas) nunca
reenvia una cookie marcada `Secure` sobre una conexion HTTP no cifrada. El
stack de desarrollo local definido en el plan (Seccion 4.1/4.3: FastAPI en
`http://localhost:8000`, Vite en `http://localhost:5173`, sin TLS) es HTTP
puro. Sin ajustar esto, `/auth/refresh` nunca funcionaria en desarrollo local,
solo en un entorno con HTTPS real - lo cual habria bloqueado silenciosamente
el "definition of done" de la Fase 0.2 hasta el primer despliegue con TLS.

## Decision

Se anade una variable de entorno `ENVIRONMENT` (`development` | `production`).
El flag `Secure` de la cookie de refresh se fija dinamicamente:
`secure=(ENVIRONMENT == "production")`. En desarrollo local (valor por
defecto) la cookie no lleva `Secure`, permitiendo el flujo completo sobre
HTTP; en produccion (o cualquier entorno con TLS real) se exige `Secure=True`
sin excepcion.

## Alternativas consideradas

- **Terminar TLS en desarrollo local (nginx/mkcert autofirmado)**: descartada
  para el alcance actual - anade complejidad de setup (certificados, confianza
  del navegador) sin beneficio real para un entorno 100% local de un unico
  desarrollador; se revisita si en Fase 6/7 (k3d) se practica TLS real.
- **Quitar `Secure` permanentemente**: descartada - debilitaria la mitigacion
  real contra robo de cookie via red no cifrada en cualquier entorno con TLS
  disponible (Fase 6+ o produccion futura).

## Consecuencias

- Se gana: el flujo de refresh token funciona de extremo a extremo en
  desarrollo local tal como esta definido el stack (Seccion 4.1), sin exigir
  TLS que el proyecto no tiene en esta etapa.
- Se paga: una variable de entorno mas que fijar correctamente en cada
  despliegue - un `ENVIRONMENT=development` olvidado en produccion
  reintroduce el riesgo que `Secure` mitiga. Se marca como checklist explicito
  del despliegue en Fase 6 (OWASP Top 10, Seccion 4.2).
- Queda pendiente de revisar: si Fase 6/7 (k3d) practica TLS real localmente,
  reevaluar si merece la pena tambien forzar `Secure=True` en desarrollo via
  un proxy con certificado local.
