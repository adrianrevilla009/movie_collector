# Working method — como vamos a trabajar juntos en este proyecto

## Ciclo por fase

Cada fase definida en `implementation-plan.md` sigue el mismo ciclo cerrado. No se abre la
siguiente fase hasta que la actual cumple su "definition of done".

```
1. PLAN     -> Definimos alcance exacto de la fase, decisiones de diseno abiertas,
               y como se validara que esta "hecha".
2. ITERAR   -> Discutimos alternativas de arquitectura/enfoque antes de escribir codigo.
               Aqui es donde se resuelven los ADR si hace falta.
3. DESARROLLAR -> Se implementa en incrementos pequenos y revisables, no todo de golpe.
4. PROBAR   -> Tests unitarios/integracion + validacion manual del comportamiento esperado.
5. REVISAR  -> Repaso conjunto: que funciono, que no, que se ajusta del plan original.
   |
   +-- si algo falla o queda incompleto -> vuelve al paso 3 (o al 1 si el diseno era erroneo)
   |
   +-- si todo esta correcto -> se cierra la fase y se abre la siguiente
```

## Roles dentro del ciclo

- Tu decides arquitectura y criterios de aceptacion; yo propongo opciones, senalo
  trade-offs y ejecuto el detalle de bajo nivel cuando lo pidas.
- Antes de escribir codigo de una fase, resumo el plan de esa fase concreta para que lo
  valides o lo ajustes.
- Si detecto que una decision de la fase actual rompe algo asumido en el plan general,
  lo senalo explicitamente antes de seguir, en vez de improvisar en silencio.

## Definicion de "fase cerrada"

Una fase no se da por terminada solo porque el codigo corre. Se cierra cuando:
1. Cumple su "definition of done" del implementation plan.
2. Tiene tests que cubren su comportamiento critico (ver `skill.md`, seccion testing).
3. Se ha revisado juntos y no quedan decisiones de diseno pendientes de esa fase.
4. Se ha actualizado la documentacion (README del modulo, ADR si aplica).

## Que hacemos si algo se tuerce a mitad de fase

En vez de seguir anadiendo parches, volvemos al paso 1 (PLAN) de esa fase: replanteamos el
alcance con lo aprendido, y solo entonces seguimos. Esto evita que la deuda tecnica se
acumule silenciosamente fase tras fase.
