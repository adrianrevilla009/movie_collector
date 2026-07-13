# Implementation plan — Backbone de ML para plataforma de cine

## 1. Vision

Construir un ecosistema de ML de nivel "produccion simulada": un backbone de plataforma
(registry, serving, monitorizacion) con cuatro modulos de dominio (recomendador, asistente
agentico multiagente, anti-fraude, entrenamiento distribuido) sobre el dominio de
cine/streaming, mas una fase de madurez que cubre fine-tuning/PEFT, cuantizacion,
explicabilidad y evaluacion adversarial. El objetivo no es el producto en si, sino
practicar decisiones de arquitectura de ML de extremo a extremo -incluyendo agentes,
multiagente, RAG hibrido, transformers, entrenamiento distribuido y RL como
extension opcional- con implicacion en el detalle de bajo nivel de cada pieza.

## 2. Fuentes de datos

| Fuente | Rol | Naturaleza |
|---|---|---|
| TMDB API | Metadatos frescos (catalogo, creditos, imagenes, watch providers, trending) | API en vivo, ~150 endpoints, free tier no comercial |
| MovieLens (GroupLens) | Ratings historicos de usuarios | Dataset estatico, base para collaborative filtering |
| OMDb API | Ratings cruzados (IMDb, Rotten Tomatoes, Metascore) | API en vivo, complementaria |

Decision de diseno: TMDB es la fuente de verdad para metadatos y se sincroniza de forma
incremental via sus exports diarios de IDs. MovieLens se usa solo como semilla de
entrenamiento inicial (cold start del propio proyecto), no como fuente productiva.

### 2.1 Estrategia de catalogo (bronze)

1. **Backfill inicial**: descargar el export diario de IDs de TMDB (~1M titulos) y pedir
   `/movie/{id}` con `append_to_response` (creditos + imagenes + keywords en una sola
   llamada). A ~40 req/s el backfill completo tarda del orden de 7 horas, como job de fondo.
2. **Filtro de calidad, no de cobertura**: se ingesta el 100% de IDs, pero se marca como
   "completo" solo lo que tenga senal minima (`vote_count > 0` o sinopsis no vacia). El
   catalogo es completo en cobertura y honesto en calidad.
3. **Sincronizacion incremental**: tras el backfill, `/movie/changes` (diario) + el export
   diario de IDs nuevos mantienen el catalogo actualizado sin re-descargar nada.

### 2.2 Estrategia de ratings (tres carriles hacia la misma capa silver)

1. **Seed historico**: MovieLens (GroupLens), mapeado a IDs de TMDB via `links.csv`.
2. **Ratings reales en vivo**: endpoint `POST /ratings` expuesto desde el frontend, tratado
   como evento (no batch), reutilizando la validacion de anomalias del modulo anti-fraude.
3. **Ratings sinteticos**: generador propio con sesgos configurables (genero, popularidad,
   decada) para testing de carga del recomendador sin depender de trafico real.

### 2.3 Superficie funcional de la aplicacion (features de usuario)

El plan hasta ahora fijaba la plataforma y los 4 modulos de ML, pero no la aplicacion en
si — lo que un usuario real puede hacer. Se fija aqui para que ninguna fase tenga que
inventar funcionalidad de producto sobre la marcha.

- **Autenticacion**: registro/login con email+password (ya fijado en Seccion 4.2:
  `POST /auth/register`, `POST /auth/login`). Al registrarse, se crea automaticamente una
  lista `watchlist` por defecto para el usuario (ver "Listas" abajo).
- **Catalogo y busqueda**: listado paginado de peliculas, ficha de detalle (sinopsis,
  reparto, generos, watch providers, ratings agregados), busqueda por texto + filtros
  (genero, decada, reparto, plataforma de streaming) — esto es la superficie que consume
  tanto el frontend directamente (busqueda por filtros) como el sub-agente de busqueda de
  la Fase 3 (lenguaje natural traducido a los mismos filtros).
  - **Motor de busqueda**: Postgres nativo, sin motor externo. Full-text search
    (`tsvector`/`ts_rank`) sobre titulo+sinopsis para relevancia, combinado con `pg_trgm`
    (extension nativa de Postgres) para tolerancia a errores tipograficos ("Innterstellar"
    encuentra "Interstellar") via similitud de trigramas — cubre el hueco de "busqueda
    lexica" que en versiones previas del plan solo eran filtros estructurados.
  - **Orden**: `?sort=` con valores `relevancia` (default en busqueda por texto),
    `rating_desc`, `fecha_estreno_desc`, `popularidad_desc` (popularidad = la que ya trae
    TMDB, no propia).
  - **Filtro por plataforma de streaming**: usa la tabla `watch_providers` ya ingestada;
    TMDB devuelve esta info **por region**, asi que se fija `ES` (España) como region por
    defecto, configurable por query param `?region=` si se quisiera otra.
- **Ratings**: puntuacion numerica 1-5 por pelicula y usuario (`POST /ratings`, ya
  fijado). Un usuario puede actualizar su propio rating (upsert por `user_id`+`movie_id`,
  no duplicados).
- **Reviews**: entidad separada del rating numerico — texto libre opcional asociado a un
  rating (`POST /reviews`, `GET /movies/{id}/reviews`, `DELETE /reviews/{id}` solo por su
  autor). Es la entidad que consume el modulo anti-fraude de la Fase 4 para detectar
  reviews falsas — sin esta entidad, la Fase 4 no tendria sobre que trabajar, asi que su
  existencia se fija aqui, no se asume implicita.
  - **Voto de utilidad**: `POST /reviews/{id}/vote` (`helpful` o `not_helpful`), tabla
    `review_votes` (`review_id`, `user_id`, `is_helpful` bool, unico por par). Determina el
    orden por defecto de `GET /movies/{id}/reviews` (mas utiles primero, no solo mas
    recientes) — sin esto, una review util quedaria enterrada bajo reviews mas nuevas.
- **Listas**: dos tipos sobre la misma tabla `lists` (ver Seccion 4.8): la `watchlist` por
  defecto (una por usuario, no eliminable, solo vaciable) y listas personalizadas con
  nombre propio, publicas o privadas (`is_public`). Endpoints: `POST /lists`,
  `GET /users/me/lists`, `POST /lists/{id}/items`, `DELETE /lists/{id}/items/{movie_id}`,
  `GET /lists/{id}` (si `is_public` o es el propio dueño).
- **Rankings**: tres vistas sobre los mismos datos de ratings/reviews, sin logica de ML
  (eso es lo que aporta el recomendador de la Fase 2 por encima de esto):
  - **Top valoradas**: media ponderada tipo IMDB (Bayesian average:
    `(v/(v+m))*R + (m/(v+m))*C`, con `v` = numero de votos de la pelicula, `m` = umbral
    minimo de votos configurable, `R` = media de la pelicula, `C` = media global del
    catalogo) para que una pelicula con 2 votos de 10 no desplace a una con 5000 votos de
    8.5.
  - **Trending interno**: velocidad de ratings/reviews nuevos en los ultimos 7 dias sobre
    el trafico propio de la plataforma — deliberadamente distinto del `trending` de TMDB
    (que refleja popularidad global de TMDB, no actividad real de este proyecto); ambos se
    muestran por separado en el frontend para que la diferencia sea explicita.
  - **Mas controvertidas**: mayor varianza de rating por pelicula (util mas adelante como
    caso de prueba para el sub-agente de resumen/critica de la Fase 3).
- **Perfil de usuario**: historial propio de ratings/reviews, listas propias, y (a partir
  de Fase 2) sus recomendaciones personalizadas.
- **Asistente conversacional**: chat con el asistente agentico de la Fase 3, expuesto como
  seccion propia del frontend.

**Mapeo a fases** (para que ninguna quede sin dueño): catalogo, busqueda, ratings, reviews,
listas y rankings son CRUD sin ML — se implementan en **Fase 0/1** junto al resto de
cimientos y plataforma, porque el resto de fases dependen de que estos datos ya existan
(la Fase 2 necesita ratings, la Fase 3 necesita catalogo+busqueda, la Fase 4 necesita
reviews). El perfil de usuario se completa incrementalmente: la parte CRUD en Fase 0/1, la
seccion de recomendaciones cuando llega la Fase 2.

### Extension opcional - Social
No forma parte del camino critico: seguir a otros usuarios y ver sus listas publicas.
Reutiliza la tabla `lists` (ya soporta `is_public`) y solo anade una tabla `follows`
(`follower_id`, `followed_id`). Se trata como experimento aparte, igual que RL/bandits en
la Seccion 5.

### 2.4 Autenticacion a nivel productivo

El JWT simple de la primera version del plan es suficiente para una demo, pero no para
"nivel productivo" — aqui se fija el diseno completo, con las mismas garantias que un
sistema de auth real (aunque el proveedor de email sea local, no cloud).

- **Hashing de contrasenas**: `argon2id` via `argon2-cffi` (ganador del Password Hashing
  Competition, mas resistente a cracking por GPU que bcrypt) — sustituye la mencion previa
  a `bcrypt`.
- **Politica de contrasena**: minimo 10 caracteres, chequeo de fuerza con `zxcvbn` en vez
  de reglas de composicion arbitrarias (mayus/minus/numero) que se sabe que producen
  contrasenas mas debiles en la practica.
- **Estrategia de tokens (access + refresh, con rotacion)**:
  - **Access token**: JWT, TTL 15 minutos, devuelto en el cuerpo de la respuesta, usado por
    el frontend en la cabecera `Authorization: Bearer`. Vida corta a proposito: si se
    filtra, la ventana de abuso es minima.
  - **Refresh token**: token opaco (no JWT, string aleatorio), TTL 7 dias, guardado
    **hasheado** (no en claro) en la tabla `refresh_tokens` (`user_id`, `token_hash`,
    `family_id`, `expires_at`, `revoked_at`). Se entrega en cookie `httpOnly`, `Secure`,
    `SameSite=Strict` (no accesible desde JavaScript, mitiga robo via XSS).
  - **Rotacion con deteccion de reuso**: cada `POST /auth/refresh` invalida el refresh
    token usado y emite uno nuevo de la misma `family_id`. Si un token ya usado se
    presenta de nuevo (señal de robo/replay), se revoca toda la familia y se fuerza
    re-login — patron estandar de refresh token rotation.
  - Endpoints: `POST /auth/refresh`, `POST /auth/logout` (revoca el refresh token actual),
    `POST /auth/logout-all` (revoca toda la familia, "cerrar sesion en todos los
    dispositivos").
- **Verificacion de email**: al registrarse, `email_verified=false` y se envia un token de
  verificacion de un solo uso (`POST /auth/verify-email`, `POST /auth/resend-verification`).
  Publicar reviews (no ratings) requiere `email_verified=true` — ademas de UX, dificulta
  granjas de cuentas falsas y ayuda al propio modulo anti-fraude de la Fase 4.
- **Reset de contrasena**: `POST /auth/forgot-password` (siempre devuelve 200 exista o no
  el email, para no filtrar que emails estan registrados — mitigacion de enumeracion de
  usuarios) + `POST /auth/reset-password` con token de un solo uso, TTL 1 hora, guardado
  hasheado.
- **Envio de email en local (sin proveedor cloud)**: `Mailpit` como servidor SMTP de
  desarrollo — captura los correos de verificacion/reset sin enviarlos de verdad,
  visibles en su UI web. Puerto 1025 (SMTP) / 8025 (UI), añadido a Docker Compose perfil
  `core`.
- **Proteccion contra fuerza bruta**: `POST /auth/login` limitado especificamente (no solo
  el rate limit general) a 5 intentos / 15 min por combinacion IP+email via `slowapi` +
  contador en Redis; al superarlo, bloqueo temporal de 15 min de esa combinacion, no de la
  cuenta entera (evita que un atacante bloquee la cuenta de otro usuario a proposito).
- **Roles (RBAC minimo)**: columna `role` en `users` (`user` | `admin`), un unico usuario
  admin creado por seed en Fase 0 (no hay flujo de auto-registro como admin). Los endpoints
  de moderacion (abajo) requieren `role=admin` via dependencia de FastAPI.
- **Auditoria de eventos de auth**: cada login (exito/fallo), cambio de contrasena y logout
  se registra con `structlog` en un logger dedicado (`auth.audit`), consultable en Loki —
  no se guarda en Postgres para no mezclar datos operacionales con el dominio.
- **Gestion de sesiones/dispositivos**: `refresh_tokens` amplia sus columnas con
  `user_agent`, `ip_address`, `last_used_at`. `GET /users/me/sessions` lista las
  `family_id` activas del usuario (dispositivo/navegador aproximado por `user_agent`,
  ultima actividad, IP), `DELETE /users/me/sessions/{family_id}` revoca una sesion
  concreta sin afectar a las demas — mas fino que `logout-all`, que revoca todas a la vez.
- **OAuth de terceros**: descartado explicitamente (Google/GitHub) por anadir una
  dependencia externa sin necesidad real a este alcance local; ADR abierta si mas adelante
  se quiere practicar OAuth2/OIDC.

### 2.5 Moderacion y gestion de cuenta

- **Panel de moderacion** (consume el `moderation_status` que produce la Fase 4, para que
  la clasificacion de anti-fraude tenga un destino real y no sea solo un dato interno):
  `GET /admin/reviews/flagged` (solo `role=admin`), `POST /admin/reviews/{id}/resolve`
  (`approved` o `flagged` definitivo). Antes de que exista la Fase 4, `moderation_status`
  se fija a `approved` por defecto — el panel no depende de que la Fase 4 este cerrada
  para poder implementarse en Fase 0/1.
- **Reportes de contenido por usuarios** (complementa la deteccion automatica de la Fase 4
  con señal humana, que suele llegar antes que el modelo para casos evidentes): tabla
  `reports` (`reporter_id`, `target_type` enum `review|user`, `target_id`, `reason`,
  `status` enum `open|resolved`). `POST /reports`, `GET /admin/reports` (solo admin),
  `POST /admin/reports/{id}/resolve`.
  - Cada `report` sobre una review adjunta un peso a su `moderation_status`; 3+ reportes
    independientes marcan la review como `flagged` automaticamente, sin esperar al modelo.
- **Suspension/baneo de cuentas** (accion de moderacion que faltaba: hasta ahora solo se
  podia marcar contenido, no al usuario que lo genera): columnas `is_banned` bool,
  `banned_until` timestamp nullable (null = permanente) en `users`.
  `POST /admin/users/{id}/ban`, `POST /admin/users/{id}/unban`. Un usuario baneado no puede
  hacer login (`403` explicito, no un generico "credenciales invalidas", para que el
  frontend pueda mostrar el motivo).
- **Anti-spam en registro sin dependencia cloud**: campo honeypot oculto en el formulario
  de registro (invisible para humanos via CSS, invisible para el propio frontend en su uso
  normal; si llega relleno, es un bot) — se descarta CAPTCHA de terceros (hCaptcha/
  reCAPTCHA) por depender de un servicio cloud externo, incoherente con el alcance
  100% local del proyecto.
- **Gestion de cuenta**: `PATCH /users/me` (nombre/email), `POST /users/me/change-password`
  (pide la contrasena actual), `DELETE /users/me` — borrado logico: se anonimiza
  `email`/nombre y se conservan ratings/reviews de forma agregada y anonima (no se
  borran, para no romper el entrenamiento del recomendador), practica minima de
  "derecho al olvido" aunque el proyecto no tenga usuarios reales todavia.
- **Portabilidad de datos** (simetrico al borrado anterior): `GET /users/me/export`
  devuelve un JSON con todos los datos propios (ratings, reviews, listas, notificaciones) —
  practica minima de "derecho de acceso/portabilidad", igual de barata de implementar que
  el borrado logico y evita tener que anadirla mas tarde como parche.
- **Notificaciones** (minimas, no un sistema de mensajeria completo): tabla
  `notifications` (`user_id`, `type`, `payload` JSONB, `read_at`). Se generan cuando una
  review propia cambia de `moderation_status`, cuando se resuelve un reporte propio, y (si
  se activa la extension Social) cuando una lista seguida se actualiza.
  `GET /users/me/notifications`, `POST /notifications/{id}/read`. Se consumen por
  **polling** desde el frontend (TanStack Query con `refetchInterval`), no websockets — no
  hay volumen que justifique infraestructura de push en tiempo real todavia; se revisita
  si la extension Social lo necesita.
- **Estadisticas de admin**: `GET /admin/stats` (solo `role=admin`) — conteos agregados
  (usuarios totales/nuevos ultimos 7 dias, ratings/reviews totales, reviews pendientes de
  moderar, reportes abiertos). Consultas directas sobre Postgres, sin motor de analitica
  aparte — a este volumen no hace falta un data warehouse, solo `COUNT`/`GROUP BY` bien
  indexados.
- **Feedback de usuarios**: `POST /feedback` (texto libre + `category` enum
  `bug|sugerencia|otro`, sin necesidad de estar logueado). Tabla `feedback` propia,
  revisable solo en `GET /admin/feedback` — canal minimo para que el propio uso del
  proyecto (aunque sea de un unico usuario) deje rastro de que ajustar, sin montar un
  sistema de tickets completo.

### 2.6 Convenciones de API transversales (para que ningun endpoint nuevo invente su propio estilo)

- **Versionado**: todos los endpoints bajo el prefijo `/api/v1/...` desde el primer commit
  — un cambio incompatible futuro es una `v2` nueva, nunca una ruptura silenciosa de `v1`.
- **Paginacion**: offset simple (`?page=...&size=...`) en todos los listados, incluidos
  `GET /movies`/`GET /movies/search` y los rankings — **decision revisada durante la
  implementacion de la Fase 0.3** (ver ADR 0003). La version original de esta seccion fijaba
  cursor-based para listados sin tamano acotado, pero se implemento offset de forma
  consistente en toda la Fase 0.3 (necesita numero total de paginas para el paginador del
  frontend, con desempate estable por `id` en cada criterio de orden para que no se solapen
  ni salten filas entre paginas). Se documenta aqui la decision real en vez de dejar una
  discrepancia entre plan y codigo; revisitar solo si el catalogo completo (~1M titulos) hace
  que el `COUNT(*)` de `total` empiece a doler en el `EXPLAIN ANALYZE` real.
- **Formato de error estandar**: RFC 7807 (`application/problem+json`): `{type, title,
  status, detail, instance}` en toda respuesta de error 4xx/5xx, generado por un exception
  handler global de FastAPI — nunca un `{"error": "..."}` ad-hoc por endpoint.
- **Health checks**: `GET /health` (liveness, sin dependencias externas) y
  `GET /health/ready` (readiness: comprueba Postgres/Redis alcanzables) en cada servicio
  FastAPI — los usa el `healthcheck` de Docker Compose y (en Fase 6/7) el `readinessProbe`
  de k3d ya mencionado en la Seccion 4.1.
- **Idioma**: `es-ES` como idioma por defecto de toda la app (catalogo, UI, respuestas del
  asistente); los campos de TMDB se piden con `language=es-ES` y se cae a `en-US` cuando
  TMDB no tiene traduccion para un titulo concreto. No se construye i18n multi-idioma
  completo — no aporta nada al objetivo de aprendizaje de este proyecto y es puro coste.

### 2.7 Catalogo extendido: personas, colecciones, generos

El catalogo hasta ahora trataba `movies` como la unica entidad de contenido. TMDB modela
tambien personas y colecciones como entidades propias con pagina propia — se fijan aqui
para no tener que remodelar el esquema a mitad de Fase 2/3 cuando el sub-agente de
busqueda necesite "peliculas de Christopher Nolan" o el frontend necesite una ficha de
actor.

- **Personas** (actores/directores/equipo): tabla `people` (id TMDB, nombre, biografia,
  foto), y `credits` redefinida como tabla de union `movie_id`, `person_id`,
  `credit_type` enum `cast|crew`, `character_name` (si `cast`) o `job` (si `crew`),
  `order` (orden de aparicion en los creditos). Endpoints: `GET /people/{id}` (biografia +
  filmografia), y el filtro de busqueda existente (Seccion 2.3) se amplia para aceptar
  `person_id` ademas de genero/decada.
- **Colecciones/franquicias**: TMDB ya expone `belongs_to_collection` en cada pelicula
  (ej. "The Dark Knight Collection"). Tabla `collections` (id TMDB, nombre, overview,
  poster), campo `collection_id` nullable en `movies`. Endpoint `GET /collections/{id}`
  (lista las peliculas de la franquicia en orden). Coste marginal: el dato ya viene en la
  respuesta de `/movie/{id}` del backfill, solo falta persistirlo.
- **Generos**: tabla `genres` (ya existia como nombre en la Seccion 4.8, se detalla aqui:
  id TMDB, nombre) + tabla de union `movie_genres`. Endpoint `GET /genres` (listado, usado
  para poblar filtros en el frontend).
- **Politica de contenido**: se excluye contenido marcado `adult=true` por TMDB **desde el
  backfill** (Seccion 2.1), no se filtra a posteriori en la API — el proyecto es una demo
  de caracter general, y filtrar en origen evita tener que auditar despues que ningun
  endpoint lo haya dejado pasar.
- **Trailers**: TMDB expone `/movie/{id}/videos` (clave de YouTube del trailer oficial,
  entre otros). Se persiste en el backfill como columna JSONB en `movies` (no merece tabla
  propia, es un array pequeno de metadatos). Endpoint `GET /movies/{id}/videos`; el
  frontend embebe el reproductor de YouTube en la ficha de la pelicula.
- **"Mas como esta" antes de que exista el recomendador**: la ficha de pelicula necesita
  una seccion de similares desde el primer dia, pero el recomendador real no llega hasta
  la Fase 2. Fallback explicito: `GET /movies/{id}/similar` devuelve en Fase 0/1
  directamente el resultado de `/movie/{id}/similar` de TMDB (sin logica propia); cuando
  la Fase 2 cierre, el mismo endpoint cambia de implementacion por dentro (pasa a usar el
  recomendador interno) sin cambiar el contrato — el frontend no se entera del cambio.

## 3. Arquitectura (resumen)

```
Datos fuente (TMDB + MovieLens + OMDb)
        |
Plataforma ML interna (registry, serving, monitorizacion, feature store)
        |
   +----+--------+--------------+
Recomendador  RAG/LLM   Anti-fraude   Entrenamiento distribuido
```

Cada modulo consume la plataforma en vez de montar su propia infraestructura de serving o
registro. Esa es la pieza que lo convierte en un ejercicio de arquitectura y no en cuatro
proyectos sueltos.

## 4. Stack tecnico por dominio

Esta seccion fija las decisiones tecnicas concretas para que la implementacion pueda
arrancar sin ambiguedad. Cada eleccion sigue el principio de **componente sustituible**:
se elige la opcion mas simple que resuelve el problema actual, se documenta la alternativa
descartada y bajo que condicion se reconsideraria (ver Seccion 7), de forma que cambiar de
opinion mas adelante sea sustituir una pieza, no rediseñar el sistema. Las alternativas
descartadas quedan anotadas para no repetir la discusion a mitad de fase.

### 4.1 Arquitectura, computo y despliegue

- **Alcance**: 100% local, un unico host de desarrollo. No hay proveedor cloud en esta
  etapa del proyecto; toda decision de IaC se disena para que migrar a cloud mas adelante
  sea un cambio de provider, no un rediseno.
- **IaC**: Terraform con el provider `kreuzwerker/docker` gestiona los recursos
  **persistentes** que se crean una sola vez y sobreviven a reinicios del stack: redes
  Docker con nombre y volúmenes con nombre (los que guardan datos de Postgres, MinIO,
  Grafana). El objetivo es practicar el flujo `plan -> apply -> state` sin depender de
  credenciales cloud. El state se guarda en local (`terraform.tfstate` versionado fuera de
  git, `.gitignore`) durante todo el proyecto.
- **División de responsabilidad Terraform vs. Compose (para que no se pisen)**: Terraform
  se ejecuta una vez (o cuando cambia la topología de red/volúmenes) y crea los recursos
  persistentes; Docker Compose referencia esas redes/volúmenes como `external: true` y es
  el único responsable del ciclo de vida día a día de los **servicios** (arrancar, parar,
  reiniciar). Nunca se define el mismo contenedor en los dos sitios a la vez.
- **Orquestacion de contenedores**: Docker Compose para las Fases 0 a 5 (un unico
  `docker-compose.yml` por entorno: `dev`, `test`), usando los recursos externos creados
  por Terraform. Es la opcion correcta para un solo host: Kubernetes anade una capa de
  complejidad (scheduler, networking overlay, CRDs) que no aporta nada cuando no hay
  multiples nodos que orquestar.
- **¿Hace falta Kubernetes?** No para el camino critico. Se introduce como ejercicio
  deliberado en la Fase 6/7 usando `k3d` (Kubernetes-in-Docker, un solo binario, sin coste
  cloud) para practicar manifiestos, Helm charts y el propio Model Registry como un
  `Deployment` con `readinessProbe`. Se documenta como ADR: "Docker Compose para desarrollo
  continuo, k3d como ejercicio de arquitectura de orquestacion, no como requisito de
  ninguna fase base".
- **CI/CD**: GitHub Actions con tres workflows:
  - `ci.yml`: lint (`ruff`/`black`, `eslint`) + tests unitarios en cada PR.
  - `build.yml`: build y tag de imagenes Docker al hacer merge a `main` (registry local o
    GitHub Container Registry, sin publicacion cloud).
  - `terraform-plan.yml`: `terraform fmt -check` + `terraform plan` en cada PR que toque
    `infra/`; el `apply` se ejecuta manualmente en local (no hay runner con acceso al
    Docker daemon del host de desarrollo, asi que el apply automatico no aplica aqui).
- **Redes**: una red Docker por entorno, resolucion de servicios por nombre de contenedor
  (sin proxy/service mesh en esta fase; se anota como posible ADR futuro si se anade k3d).
- **Secretos**: variables de entorno via `.env` no versionado en Fases 0-6. Se evalua
  `sops`/`age` si el numero de secretos crece en la Fase 7.

### 4.2 Backend

- **Lenguaje unico**: Python en toda la plataforma y modulos, para no fragmentar el
  aprendizaje entre stacks distintos y porque el ecosistema ML lo impone de todas formas.
  Se documenta como ADR abierta: introducir un segundo lenguaje (ej. Go) para un gateway
  ligero es una mejora valida pero no bloqueante.
- **Framework API**: FastAPI, con Pydantic **v2** (no v1: cambia la API de validadores y
  serializacion). Tipado con Pydantic, generacion automatica de OpenAPI (clave para el
  contrato tipado que consumira el frontend), soporte async nativo.
- **Cliente HTTP para APIs externas (TMDB/OMDb)**: `httpx` en modo async (coherente con
  FastAPI async; `requests` es sincrono y bloquearia el event loop), con `tenacity` para
  reintentos con backoff exponencial ante rate limiting o fallos transitorios.
- **CORS**: middleware `CORSMiddleware` de FastAPI habilitado desde el primer commit del
  backend, con origen permitido `http://localhost:5173` (Vite dev) en Fases 0-6; se
  restringe a un origen concreto en Fase 6 en vez de dejarlo abierto.
- **Comunicacion sincrona**: REST/JSON para request-response (serving de modelos, chat del
  asistente, CRUD de catalogo).
- **Comunicacion asincrona**: 
  - **Kafka (via Redpanda como implementacion ligera y compatible)** para el flujo de
    eventos del modulo anti-fraude, que necesita semantica de streaming real
    (particiones, consumer groups, replay).
  - **RQ (Redis Queue)** para tareas de fondo de menor criticidad (reentrenos batch,
    backfill de catalogo, notificaciones). Se descarta Celery por complejidad innecesaria
    a este alcance (no hace falta canvas de tareas ni scheduling avanzado) y se descarta
    la mencion previa a "Redis Streams" para esto por ser una API distinta y no la que usa
    RQ (que usa listas de Redis, no streams) — evita mezclar dos abstracciones distintas
    bajo el mismo nombre.
- **Bases de datos**:
  - **PostgreSQL**: fuente de verdad para catalogo, usuarios, ratings y metadatos de
    experimentos. Integridad relacional + columnas `JSONB` para campos flexibles de TMDB.
  - **pgvector** (extension sobre el mismo Postgres) para embeddings del modulo RAG en las
    Fases 0-3. Migrar a un vector store dedicado (Qdrant) es la primera candidata a ADR si
    el volumen o la latencia de busqueda lo justifican — no se adopta por adelantado.
  - **Redis**: cache de respuestas de TMDB/OMDb (con TTL por tipo de recurso) y capa online
    del feature store (baja latencia para serving en tiempo real).
- **Feature store**: implementacion propia y minima sobre Postgres (batch) + Redis
  (online), en vez de adoptar Feast desde el inicio. Se opta por esto para entender el
  problema de "training-serving skew" desde el detalle de bajo nivel; Feast queda anotado
  como sustituto valido si la complejidad de mantenerlo a mano se vuelve el cuello de botella.
- **Migraciones de esquema**: Alembic.
- **Seguridad**:
  - **Autenticacion — diseño a nivel productivo** (no un JWT simple): ver detalle completo
    en la nueva Seccion 2.4. Resumen: hash `argon2id`, access token de corta duracion +
    refresh token con rotacion y deteccion de reuso, verificacion de email, reset de
    contrasena, bloqueo tras intentos fallidos, roles (`user`/`admin`), auditoria de
    eventos de auth.
  - Validacion estricta de entrada con esquemas Pydantic en todos los endpoints publicos
    (`POST /ratings`, chat del asistente).
  - Rate limiting propio (middleware, ej. `slowapi`) independiente del rate limit de TMDB,
    con limites mas estrictos especificamente en `/auth/*` (ver Seccion 2.4).
  - Checklist OWASP Top 10 aplicado a los endpoints expuestos al frontend antes de cerrar
    la Fase 6.
  - Escaneo de dependencias (parte de OWASP A06, componentes vulnerables): `pip-audit`
    (Python) y `npm audit`/`pnpm audit` (frontend) como paso de `ci.yml`, no solo lint.
- **TDD**: cada endpoint y cada transformacion de datos se escribe test-first con
  `pytest`. Tests de contrato de API con `schemathesis` (valida que la implementacion
  cumple el OpenAPI generado). Tests de integracion con `testcontainers-python` para
  levantar Postgres/Redis/Redpanda reales en CI en vez de mocks — evita falsos positivos
  por mockear mal el comportamiento de la base de datos.

### 4.3 Frontend

- **Alcance**: cliente de demo fino que consume la misma API publica que consumiria un
  tercero — principio **API-first**: la API se disena y documenta (OpenAPI) como si fuera
  a tener consumidores externos reales desde el primer endpoint, en vez de acoplarse a las
  necesidades puntuales del frontend interno. No es el foco del proyecto, pero se monta
  con el mismo nivel de rigor que el backend.
- **Stack**: React + TypeScript + Vite. Se descarta Next.js/SSR porque no hay necesidad de
  renderizado en servidor para un cliente interno de demo — anadiria complejidad sin
  beneficio real aqui.
- **Enrutado**: `React Router` (data mode). Mapa de paginas fijado para que ninguna fase
  tenga que inventar navegacion sobre la marcha: `/` (home, recomendaciones si hay sesion),
  `/buscar` (catalogo + filtros), `/peliculas/:id` (ficha + reviews + rating),
  `/personas/:id`, `/colecciones/:id`, `/rankings`, `/listas/:id`, `/mis-listas`,
  `/perfil`, `/asistente` (chat), `/login`, `/registro`, `/verificar-email`,
  `/recuperar-password`, `/admin/moderacion` (solo `role=admin`, redirige si no).
- **Datos y estado**: TanStack Query para fetching/cache de la API (evita reinventar cache
  de red a mano y evita el peso de un store global tipo Redux para este alcance).
- **Contrato tipado real**: los tipos TypeScript del cliente se generan automaticamente
  desde el OpenAPI de FastAPI (`openapi-typescript`), nunca se escriben a mano dos veces.
- **Estilos**: Tailwind CSS.
- **Testing**: Vitest + React Testing Library para componentes/unidad, Playwright para los
  flujos criticos end-to-end (enviar un rating real, completar una conversacion con el
  asistente). Mismo principio de piramide de tests que en backend.

### 4.4 Machine learning / IA

- **Base**: Python, PyTorch (deep learning, embeddings, entrenamiento multimodal) y
  scikit-learn (baselines clasicos para recomendador y anti-fraude).
- **Recomendador**: `implicit` (ALS, activamente mantenido, sin problemas de compilacion en
  Python moderno) para collaborative filtering. `LightFM` queda descartado explicitamente:
  sin release desde ~2020 y con historial de fallos de build (Cython/NumPy) en Python
  3.11+, no se adopta para no bloquear Fase 2 con un problema de compatibilidad evitable.
  `sentence-transformers` para embeddings de contenido (sinopsis, generos, reparto).
- **Asistente agentico multiagente**: el bucle razonamiento-accion-observacion del agente
  coordinador se construye **a mano primero** (llamadas directas al SDK del proveedor de
  LLM, sin framework), precisamente porque el objetivo es entender el mecanismo de bajo
  nivel. Adoptar `LangGraph` como capa de orquestacion queda anotado como paso siguiente
  documentado en ADR, una vez que la version manual funciona y se entiende que problema
  resuelve el framework.
  - **Proveedor de LLM**: Ollama, 100% local, coherente con el alcance "sin proveedor
    cloud" de la Seccion 4.1. Modelo de partida fijado: `llama3.2:3b` (via
    `ollama pull llama3.2:3b`) — cabe con margen en el presupuesto de RAM de la Seccion
    4.7 junto al resto del stack. Si la calidad de respuesta del coordinador o de los
    sub-agentes no es suficiente, el siguiente paso documentado es `qwen2.5:7b-instruct-q4_K_M`
    (cuantizado), no un cambio de proveedor.
  - **Streaming de respuesta (decision no opcional dado el hardware)**: en CPU (Seccion
    4.7), generar una respuesta completa antes de mostrar nada puede tardar varios
    segundos — inaceptable para UX de chat. `POST /api/v1/assistant/chat` responde via
    **Server-Sent Events** (token a token segun los va emitiendo Ollama), consumido por el
    frontend con `EventSource`. Se descarta WebSocket por ser mas complejo de lo que este
    caso necesita (canal unidireccional servidor->cliente es suficiente, no hace falta
    full-duplex).
- **Fine-tuning / PEFT**: Hugging Face `transformers` + `peft` (LoRA) + `bitsandbytes`
  (cuantizacion) sobre un modelo pequeno open-source, compatible con computo local sin GPU
  de gama alta.
- **Entrenamiento distribuido**: `torchrun` / `DistributedDataParallel` para simular
  multi-proceso en un unico host (no hay multi-nodo real al ser local). `Ray Train` se deja
  anotado como alternativa si se quiere practicar la abstraccion de orquestacion real de
  un cluster, incluso simulado.
- **Tracking de experimentos**: MLflow autoalojado (encaja con la restriccion de "sin
  cloud"; se descarta Weights & Biases por depender de un servicio externo), con MinIO
  como artifact store (ver Seccion 4.5).
- **Model registry y serving**: el registry de MLflow es la fuente de verdad de versiones
  de modelo; el serving real se envuelve en el contrato FastAPI comun de la plataforma
  (nunca se expone el servidor de MLflow directamente a los modulos).
- **Streaming / anti-fraude**: `River` (online ML) para modelos que se actualizan
  incrementalmente, `PyOD` para los algoritmos de deteccion de anomalias.
- **Explicabilidad**: `SHAP` para el recomendador/anti-fraude, `captum` para visualizacion
  de atencion en los modelos basados en transformers.
- **Evaluacion**: `Ragas` para relevancia/fidelidad del RAG, `promptfoo` para las
  suites de red-teaming/adversariales de la Fase 7.

### 4.5 Datos y MLOps transversal

- **Almacen de objetos**: MinIO (S3-compatible, autoalojado). Guarda posters cacheados de
  TMDB, artifacts de MLflow (modelos, checkpoints) y actua como remoto de DVC — en vez de
  filesystem local plano. Se adopta desde ya (no diferido a Fase 6/7) precisamente para
  practicar la interfaz S3 desde el principio, y porque los Helm charts que se usaran mas
  adelante con k3d (Fase 6/7) ya esperan un backend S3-compatible, evitando una migracion
  a mitad de proyecto.
  - **Servido de imagenes**: bucket `public-media` con politica de lectura publica
    (posters/backdrops, contenido no sensible) — el frontend carga las imagenes
    directamente desde MinIO (URL publica), sin pasar por FastAPI, para no cargar el
    backend con trafico binario que no necesita autenticacion ni logica de negocio.
    Artifacts de MLflow y datasets de DVC van en buckets separados y privados.
- **Versionado de datos**: DVC, con MinIO como remoto (protocolo S3) — versiona los
  snapshots del catalogo y los datasets de entrenamiento junto al codigo.
- **Orquestacion de pipelines**: Prefect para los pipelines de ingesta/entrenamiento —
  se prefiere sobre Airflow por su modelo mas ligero y su mejor experiencia de desarrollo
  local; Airflow queda anotado como alternativa si en algun momento se quiere practicar el
  estandar mas "enterprise" (colas de workers, scheduler distribuido).
- **Observabilidad**: Prometheus (metricas) + Grafana (dashboards) + Loki (logs) +
  OpenTelemetry SDK (instrumentacion) + **Grafana Tempo** (backend de trazas — OTel por si
  solo es solo el protocolo de instrumentacion, necesita un backend donde aterricen las
  trazas; se elige Tempo sobre Jaeger por integrarse nativamente con el resto del stack
  Grafana ya elegido), todo autoalojado via Docker Compose — cubre la "observabilidad de
  tres capas" del `skill.md` sin depender de ningun SaaS externo.

### 4.6 Testing y calidad (transversal)

- Piramide de tests identica en todos los dominios: muchos unitarios, menos de
  integracion (con `testcontainers`), pocos end-to-end.
- TDD real: en cada fase, el primer commit de una funcionalidad es un test en rojo.
- Tests especificos de ML (regresion de metricas, contrato de datos, invarianza) definidos
  en `skill.md` seccion 4, aplicados desde la Fase 2 en adelante.
- Ningun test de CI llama a TMDB/OMDb reales: se usan fixtures grabadas (VCR.py) o datos
  sinteticos.

### 4.7 Restricciones de hardware (condicionan Fases 5 y 7)

- **Equipo**: portatil Lenovo IdeaPad 3 15ALC6, AMD Ryzen 7 5700U (8 nucleos / 16 hilos),
  grafica integrada Radeon (sin GPU discreta), 16 GB RAM (~13.9 GB usables). Windows 11
  con Docker via WSL2.
- **Sin aceleracion GPU real**: la grafica integrada del APU no tiene soporte CUDA (AMD)
  ni ROCm funcional (ROCm esta pensado para GPUs discretas de gama Instinct/Radeon
  dedicada, no para integradas de portatil). Todo entrenamiento del proyecto corre en
  CPU, sin excepcion. Esto se documenta como restriccion dura, no como riesgo temporal.
- **Impacto en Fase 5 (entrenamiento distribuido multimodal)**: `torchrun`/DDP
  multi-proceso en CPU sobre 8 nucleos es viable como ejercicio de orquestacion, pero no
  como entrenamiento real de un modelo util en tiempos razonables. Ajuste de alcance:
  dataset reducido (subset del catalogo, no el catalogo completo), arquitectura de
  embeddings pequena y ligera (encoder propio simple o un CLIP pequeno), y el
  "analisis de coste de computo" del entregable se documenta explicitamente como analisis
  en CPU, sin pretender que sea comparable a un caso con GPU real.
- **Impacto en Fase 7 (fine-tuning/PEFT + cuantizacion)**: LoRA en CPU es lento pero
  factible con un modelo base pequeno. Modelo fijado: `Qwen2.5-1.5B-Instruct` (Hugging Face
  Hub: `Qwen/Qwen2.5-1.5B-Instruct`). ADR abierta: `bitsandbytes` tiene soporte de CPU
  limitado/reciente; si no funciona de forma fiable, la cuantizacion se hace via
  GGUF/`llama.cpp`, que ademas encaja mejor con Ollama (ya usado para el asistente de la
  Fase 3).
- **RAM ajustada para el stack completo**: correr Postgres + Redis + Redpanda + MLflow +
  MinIO + Prometheus + Grafana + Loki + Ollama + (mas adelante) k3d a la vez, en una
  maquina con ~13.9 GB usables, es exigente. Se gestiona con **Docker Compose profiles**:
  cada fase levanta solo los servicios que necesita (`core`, `assistant`, `fraud`,
  `observability`, `storage`) en vez del stack completo por defecto. Se anota como
  decision de Fase 0, no algo implicito.

### 4.8 Convenciones transversales de arranque (para implementacion sin ambiguedad)

Esta seccion fija lo que cualquier fase necesita desde el primer commit. Lo que no esta
aqui (esquema exacto de una tabla nueva, hiperparametros, tamano de chunk...) se resuelve
en el paso PLAN de la fase correspondiente, tal como define `working-method.md` — no es
un hueco, es el proceso funcionando como esta disenado.

- **Versiones fijadas**: Python 3.12, Node.js 20 LTS, Terraform >= 1.7, `k3d` >= 5.7,
  Docker Compose v2 (sin clave `version:` en los YAML, sintaxis Compose Specification).
- **Gestor de paquetes Python**: `uv`, con un unico `pyproject.toml` raiz en modo
  workspace (`[tool.uv.workspace] members = ["platform", "modules/*", "ingestion"]`). Cada
  miembro es un paquete instalable propio; `uv sync` instala todo el monorepo con un solo
  lockfile (`uv.lock`) versionado. Se prefiere sobre Poetry por velocidad de resolucion y
  soporte nativo de workspaces sin plugins.
- **Gestor de paquetes frontend**: `pnpm` (mas rapido y eficiente en disco que `npm`/`yarn`
  para un unico paquete de frontend; lockfile `pnpm-lock.yaml` versionado).
- **Imagen base Docker**: `python:3.12-slim` para servicios Python, `node:20-slim` para el
  build del frontend (multi-stage, servido luego via `nginx:alpine` o similar en Fase 6).
- **Mapa de puertos (host, en Docker Compose)**:

  | Servicio | Puerto host | Notas |
  |---|---|---|
  | FastAPI (backend) | 8000 | |
  | Frontend (Vite dev) | 5173 | |
  | PostgreSQL | 5432 | |
  | Redis | 6379 | |
  | Redpanda (Kafka API) | 9092 | + 9644 (admin API) |
  | MLflow | 5000 | |
  | MinIO | 9000 (API) / 9001 (consola) | |
  | Prometheus | 9090 | |
  | Grafana | 3000 | |
  | Loki | 3100 | |
  | Tempo | 3200 (query) / 4317 (OTLP grpc) | |
  | Ollama | 11434 | |
  | Mailpit | 1025 (SMTP) / 8025 (UI web) | solo dev, ver Seccion 2.4 |

- **Variables de entorno esperadas (`.env.example` versionado, `.env` real ignorado)**:
  `TMDB_API_KEY`, `OMDB_API_KEY`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`,
  `POSTGRES_HOST`, `POSTGRES_PORT`, `REDIS_URL`, `REDPANDA_BROKERS`,
  `JWT_SECRET`, `JWT_ALGORITHM` (`HS256`), `JWT_ACCESS_TTL_MINUTES` (`15`),
  `JWT_REFRESH_TTL_DAYS` (`7`), `SMTP_HOST`/`SMTP_PORT` (apuntan a Mailpit en dev),
  `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`, `MLFLOW_TRACKING_URI`,
  `MLFLOW_S3_ENDPOINT_URL` (apunta a MinIO), `OLLAMA_HOST`, `OLLAMA_MODEL`
  (`llama3.2:3b`). Las claves de TMDB/OMDb las obtiene el usuario registrandose en sus
  respectivos portales de desarrollador (gratuito); no bloquean el diseno del plan, solo
  su ejecucion.
- **Targets de Makefile (raiz del repo)**: `make up` (levanta perfil `core` de Compose),
  `make up-<profile>` (levanta un perfil especifico: `assistant`, `fraud`, `observability`,
  `storage`), `make down`, `make ingest` (backfill + sync de catalogo), `make test`
  (unitarios + integracion via `testcontainers`), `make lint` (`ruff`/`black` + `eslint`),
  `make tf-plan` / `make tf-apply` (Terraform sobre `infra/terraform`).
- **Convencion de commits y ramas**: Conventional Commits (`feat:`, `fix:`, `chore:`,
  `docs:`, `test:`) para que `ci.yml` y el historial sean consistentes entre fases. Ramas:
  `fase-N-<slug>` (ej. `fase-2-recomendador`), merge a `main` via PR.
- **Plantilla de ADR**: formato Michael Nygard (`Title` / `Status` / `Context` /
  `Decision` / `Consequences`) en `docs/adr/NNNN-titulo-kebab-case.md`, numeracion
  secuencial. Toda decision marcada "ADR abierta" en este plan se convierte en un ADR real
  con `Status: accepted` y el default ya fijado aqui — nunca se deja "pendiente" bloqueando
  una fase; si aparece una alternativa mejor mas adelante, se abre un ADR nuevo que
  supersede al anterior.
- **Tablas nucleo de la capa bronze/silver (Postgres)**: `movies` (id TMDB, metadatos
  JSONB, `is_complete` bool segun el filtro de calidad de la Seccion 2.1, `collection_id`
  nullable — ver Seccion 2.7), `people` (id TMDB, nombre, biografia, foto — Seccion 2.7),
  `credits` (`movie_id`, `person_id`, `credit_type` enum `cast|crew`, `character_name`,
  `job`, `order` — Seccion 2.7), `collections` (id TMDB, nombre, overview, poster —
  Seccion 2.7), `genres`, `movie_genres` (union `movie_id`+`genre_id`), `keywords`,
  `watch_providers`, `ratings` (columnas: `movie_id`, `user_id`, `score`, `source` enum
  `seed|live|synthetic`, `created_at` — las tres fuentes de la Seccion 2.2 escriben aqui,
  unico por `movie_id`+`user_id`), `users` (incluye `role` enum `user|admin`,
  `email_verified` bool, `is_banned` bool, `banned_until` timestamp nullable — ver Seccion
  2.4/2.5), `refresh_tokens` (`user_id`, `token_hash`, `family_id`, `expires_at`,
  `revoked_at`, `user_agent`, `ip_address`, `last_used_at` — ver Seccion 2.4), `reviews`
  (`movie_id`, `user_id`, `body` texto, `rating_id` opcional FK a `ratings`,
  `moderation_status` enum `pending|approved|flagged` — consumida por el modulo
  anti-fraude de la Fase 4 y por el panel de moderacion de la Seccion 2.5), `review_votes`
  (`review_id`, `user_id`, `is_helpful` bool — ver Seccion 2.3), `reports`
  (`reporter_id`, `target_type` enum `review|user`, `target_id`, `reason`, `status` enum
  `open|resolved` — ver Seccion 2.5), `lists` (`user_id`, `name`, `is_watchlist` bool,
  `is_public` bool), `list_items` (`list_id`, `movie_id`, `added_at`), `notifications`
  (`user_id`, `type`, `payload` JSONB, `read_at`), `feedback` (`user_id` nullable,
  `category` enum `bug|sugerencia|otro`, `body` texto, `created_at`). El detalle completo
  de columnas/indices se cierra en el PLAN de Fase 0, pero esta lista fija que tablas
  existen para que ningun modulo posterior tenga que inventar una capa de datos paralela.

## 5. Fases del proyecto

Cada fase se cierra completamente (planificada, iterada, desarrollada, probada y revisada)
antes de abrir la siguiente. Ver `working-method.md` para el detalle del ciclo.

### Fase 0 - Cimientos (dividida en 5 subfases)

La Fase 0 tal como estaba planteada mezclaba infraestructura, auth, catalogo, interaccion
de usuario y moderacion en un solo bloque — demasiado grande para cerrarse como una unica
iteracion del ciclo PLAN/ITERAR/DESARROLLAR/PROBAR/REVISAR de `working-method.md`. Se
divide en 5 subfases secuenciales, cada una con su propio Definition of Done; ninguna se
abre hasta que la anterior esta cerrada, igual que las fases numeradas grandes.

#### Fase 0.1 - Cimientos tecnicos e ingestion
- Objetivo: repo, entorno reproducible, e ingestion inicial de datos. Sin ningun endpoint
  de usuario todavia — es la base sobre la que se monta todo lo demas.
- Entregables:
  - estructura de repo (Seccion 6), `pyproject.toml` workspace `uv`, `pnpm` en frontend,
  - Terraform (redes/volumenes) + Docker Compose con profiles (Seccion 4.1/4.7),
  - CI basico (`ci.yml`: lint + tests, sin build ni deploy todavia),
  - pipeline de backfill + sincronizacion incremental del catalogo TMDB (bronze layer),
    excluyendo contenido `adult=true` desde el origen (Seccion 2.7),
  - seed de ratings desde MovieLens mapeado por `links.csv`,
  - esquema de datos versionado con Alembic (tablas de la Seccion 4.8, migraciones desde
    el primer commit),
  - `GET /health`, `GET /health/ready`.
- Definition of done: `make ingest` produce un snapshot reproducible del catalogo (sin
  contenido adulto) y `/health`/`/health/ready` responden — sin frontend ni auth todavia,
  solo datos y esqueleto de backend verificables.

#### Fase 0.2 - Autenticacion productiva
- Objetivo: el sistema de auth completo de la Seccion 2.4, aislado del resto porque es lo
  bastante grande y sensible (seguridad) para merecer su propio ciclo de revision.
- Entregables:
  - `POST /api/v1/auth/register` (honeypot anti-spam, `watchlist` automatica),
    `POST /auth/login`, `POST /auth/refresh`, `POST /auth/logout`,
    `POST /auth/logout-all`, `POST /auth/verify-email`, `POST /auth/resend-verification`,
    `POST /auth/forgot-password`, `POST /auth/reset-password`, `GET /users/me/sessions`,
    `DELETE /users/me/sessions/{family_id}`,
  - `argon2id`, rotacion de refresh tokens con deteccion de reuso, bloqueo tras intentos
    fallidos, Mailpit para emails de dev, auditoria de eventos en Loki,
  - seed de un usuario `role=admin`.
- Definition of done: un usuario se puede registrar, verificar su email via Mailpit,
  loguear, refrescar su sesion, ver y revocar sesiones activas, resetear su contrasena, y
  un intento de fuerza bruta queda bloqueado — todo verificado con tests de integracion
  reales (`testcontainers`), sin depender todavia de que exista catalogo ni frontend.

#### Fase 0.3 - Catalogo y descubrimiento
- Objetivo: toda la superficie de solo-lectura sobre el catalogo ya ingestado en la 0.1.
  No requiere login (navegar el catalogo es publico).
- Entregables:
  - `GET /movies`, `GET /movies/{id}`, `GET /movies/search` (con filtro por `person_id`,
    genero, decada, plataforma via `watch_providers`+region, orden `?sort=`, busqueda
    full-text+`pg_trgm` tolerante a errores — Seccion 2.3), `GET /people/{id}`,
    `GET /collections/{id}`, `GET /genres`,
  - `GET /movies/{id}/videos` (trailers), `GET /movies/{id}/similar` (fallback TMDB hasta
    Fase 2 — Seccion 2.7),
  - rankings: `GET /rankings/top-rated`, `GET /rankings/trending`,
    `GET /rankings/most-controversial`,
  - todos bajo `/api/v1/...`, paginacion offset (`page`/`size`, ver Seccion 2.6 y ADR 0003),
    formato de error RFC 7807 (Seccion 2.6),
  - bucket `public-media` en MinIO sirviendo posters/backdrops directamente (Seccion 4.5).
- Definition of done: se puede navegar el catalogo completo (buscar, filtrar por persona/
  genero/decada, ver ficha de pelicula/actor/coleccion con trailer, y consultar los tres
  rankings) sin necesidad de estar logueado.

#### Fase 0.4 - Interaccion de usuario
- Objetivo: todo lo que un usuario logueado (0.2) puede hacer sobre el catalogo (0.3):
  puntuar, reseñar, votar, listar.
- Entregables:
  - `POST /ratings` (upsert por `movie_id`+`user_id`),
  - `POST /reviews`, `GET /movies/{id}/reviews`, `DELETE /reviews/{id}` (requiere
    `email_verified=true`), `POST /reviews/{id}/vote`,
  - `POST /lists`, `GET /users/me/lists`, `POST /lists/{id}/items`,
    `DELETE /lists/{id}/items/{movie_id}`, `GET /lists/{id}`,
  - generador de ratings sinteticos para testing de carga.
- Definition of done: un usuario logueado puntua y reseña una pelicula, vota la utilidad
  de otra review, crea una lista y le añade titulos — con los rankings de la Fase 0.3
  reflejando los nuevos datos.

#### Fase 0.5 - Moderacion, cuenta y notificaciones
- Objetivo: cierra el circuito de confianza sobre el contenido generado en la 0.4 y da
  control de cuenta al usuario. Depende de 0.2 (roles) y 0.4 (reviews) ya cerradas.
- Entregables:
  - `GET /admin/reviews/flagged`, `POST /admin/reviews/{id}/resolve` (`moderation_status`
    por defecto `approved` hasta que exista la Fase 4), `POST /reports`,
    `GET /admin/reports`, `POST /admin/reports/{id}/resolve`, `POST /admin/users/{id}/ban`,
    `POST /admin/users/{id}/unban`,
  - `PATCH /users/me`, `POST /users/me/change-password`, `DELETE /users/me` (borrado
    logico/anonimizacion), `GET /users/me/export`,
  - `GET /users/me/notifications`, `POST /notifications/{id}/read`,
  - `GET /admin/stats`, `POST /feedback`, `GET /admin/feedback`.
- Definition of done: un admin ve y resuelve reviews marcadas, resuelve un reporte y banea
  un usuario (que ya no puede loguear), y consulta el panel de estadisticas basicas; un
  usuario edita su perfil, exporta sus datos, envia feedback, y puede borrar su cuenta de
  forma reversible en la anonimizacion — con esto se cierra toda la Fase 0 y ninguna fase
  posterior (1-7) tiene que volver a tocar producto no-ML.

### Fase 1 - Plataforma ML interna (el backbone)
- Objetivo: registry de modelos, capa de serving generica, feature store minimo,
  monitorizacion base (logs + metricas).
- Entregables: API interna de registro/consulta de modelos, contrato de serving unico que
  usaran los 4 modulos, dashboard minimo de salud de modelos.
- Definition of done: se puede registrar un modelo dummy, servirlo por la API y ver sus
  metricas basicas en el dashboard.

### Fase 2 - Modulo recomendador
- Objetivo: collaborative filtering + embeddings hibridos, serving batch (email) y
  en tiempo real (home).
- Entregables: pipeline de entrenamiento, modelo registrado en la plataforma, endpoint de
  recomendaciones, manejo de cold start.
- Definition of done: recomendaciones coherentes servidas end-to-end desde la plataforma.

### Fase 3 - Modulo RAG / asistente agentico multiagente
- Objetivo: indexacion de sinopsis/resenas, vector DB, y un sistema **agentico** (no un
  RAG de una sola pasada) sobre el catalogo de TMDB.
- Diseno agentico:
  - **Agente coordinador**: recibe la consulta, decide que sub-agentes invocar y en que
    orden, y compone la respuesta final.
  - **Sub-agente de busqueda**: convierte lenguaje natural en filtros estructurados sobre
    el catalogo (genero, decada, reparto) + busqueda vectorial sobre sinopsis/resenas.
  - **Sub-agente de recomendacion**: consulta al modulo recomendador (Fase 2) cuando la
    pregunta lo requiere ("algo parecido a X pero mas ligero").
  - **Sub-agente de resumen/critica**: resume resenas y sinopsis largas sin alucinar datos
    que no esten en el catalogo.
  - El coordinador sigue un bucle explicito de razonamiento-accion-observacion (piensa que
    falta, llama a un sub-agente o herramienta, evalua el resultado, decide si necesita otra
    vuelta o si ya puede responder), con limite maximo de vueltas para evitar bucles infinitos.
- RAG hibrido: busqueda lexica (filtros estructurados) + vectorial (semantica), con
  re-ranking antes de pasar el contexto al LLM.
- Entregables: pipeline de chunking + embeddings, orquestador multiagente, API de chat,
  evaluacion de calidad de respuestas (relevancia, alucinacion, latencia, coherencia entre
  sub-agentes).
- Definition of done: el asistente responde correctamente preguntas mixtas
  (texto + filtros estructurados + recomendacion) delegando en los sub-agentes correctos,
  con latencia aceptable y sin bucles sin terminar.

### Fase 4 - Modulo anti-fraude
- Objetivo: deteccion de reviews falsas (entidad `reviews` de la Seccion 2.3/4.8) / trafico
  anomalo en (pseudo) tiempo real; actualiza `moderation_status` de la review evaluada.
- Entregables: pipeline de streaming, modelo de clasificacion, sistema de alertas,
  deteccion de drift.
- Definition of done: el sistema detecta anomalias inyectadas artificialmente en menos de 1s
  y marca la review correspondiente como `flagged` en la tabla `reviews`.

### Fase 5 - Entrenamiento distribuido multimodal
- Objetivo: entrenar un modelo de embeddings conjunto texto+imagen (sinopsis + posters)
  usando orquestacion real y checkpoints.
- Entregables: pipeline de entrenamiento distribuido, tracking de experimentos, analisis
  de coste de computo.
- Definition of done: modelo multimodal entrenado y registrado, con comparacion de coste
  vs. entrenamiento single-node.

### Fase 6 - Integracion y hardening
- Objetivo: unir los 4 modulos bajo la plataforma comun, endurecer seguridad, documentar
  decisiones de arquitectura (ADR).
- Entregables: demo end-to-end, documentacion de arquitectura final, informe de
  lecciones aprendidas.

### Fase 7 - Madurez de IA (fine-tuning, eficiencia, explicabilidad, evaluacion)
- Objetivo: cerrar los conceptos de IA moderna que los modulos base no cubren por si
  solos, una vez que todo el sistema funciona de extremo a extremo.
- Entregables:
  - **Fine-tuning / PEFT (LoRA)**: ajustar un modelo pequeno open-source para el
    clasificador de resenas falsas del modulo anti-fraude, en vez de usar un clasificador
    generico. Esto sustituye "consumir un LLM por API" por "modificar sus pesos".
  - **Cuantizacion / distilacion**: reducir el coste de servir el modelo multimodal de la
    Fase 5 (o el modelo fine-tuneado de anti-fraude) antes de desplegarlo, con comparacion
    de latencia/coste/precision antes y despues.
  - **Explicabilidad (XAI)**: anadir SHAP o visualizacion de atencion al recomendador o al
    clasificador de fraude, para poder justificar por que el modelo decide algo.
  - **Evaluacion y red-teaming del asistente agentico**: suite de casos adversariales
    (jailbreaks, prompts ambiguos, induccion de alucinaciones, intentos de que un
    sub-agente entre en bucle) sobre el sistema de la Fase 3.
- Definition of done: hay al menos un modelo fine-tuneado y cuantizado en produccion
  simulada, con un informe de explicabilidad y un informe de evaluacion adversarial del
  asistente agentico.

### Extension opcional - Aprendizaje por refuerzo / bandits
- No forma parte del camino critico, pero si sobra tiempo: anadir un contextual bandit al
  recomendador para el problema de exploracion/explotacion en tiempo real (que recomendar
  cuando aun no se sabe si el usuario lo valorara bien). Se trata como experimento aparte,
  no como bloqueo de ninguna fase anterior.

## 6. Estructura de repositorio propuesta

```
project-root/
    pyproject.toml       (workspace uv: platform, modules/*, ingestion)
    uv.lock
    Makefile
    .env.example
    platform/            (registry wrapper, serving contract, monitoring, feature store)
    modules/
        recommender/
        rag_assistant/    (agente coordinador + sub-agentes)
        fraud_detection/
        distributed_training/
    ingestion/            (conectores TMDB / OMDb / MovieLens, seed sintetico de ratings)
    frontend/             (React + TS + Vite, cliente de demo; package.json + pnpm-lock.yaml)
    infra/
        terraform/        (provider docker, definicion de contenedores/redes/volumenes)
        compose/          (docker-compose.dev.yml, docker-compose.test.yml,
                           profiles: core / assistant / fraud / observability / storage)
        k3d/              (manifiestos/Helm, ejercicio de Fase 6/7)
    .github/
        workflows/        (ci.yml, build.yml, terraform-plan.yml)
    docs/
        adr/              (architecture decision records, plantilla Nygard)
        diagrams/
    tests/
        contract/
        integration/
        e2e/
```

## 7. Riesgos y decisiones abiertas

- Sin GPU real disponible (ver Seccion 4.7): Fases 5 y 7 corren en CPU. El alcance de
  ambas fases (tamano de dataset y de modelo) esta ajustado de partida por esta razon; no
  es una decision a revisitar salvo cambio de equipo.
- Limite de rate de TMDB (~40 rps) obliga a cachear agresivamente. Decidir TTL por tipo de
  endpoint.
- **OMDb tiene un limite gratuito de 1.000 peticiones/dia**: enriquecer el catalogo
  completo (~1M titulos) con este limite tardaria mas de 1.000 dias. Decision fijada: OMDb
  se aplica solo a un subconjunto acotado (top 5.000-10.000 peliculas mas populares por
  TMDB), no al catalogo completo. Alternativa si se quisiera cobertura total: key de mayor
  cuota de OMDb, 1 USD/mes via Patreon — unico coste opcional de todo el proyecto.
- Escoger vector DB (pgvector vs. Qdrant dedicado) es una decision de arquitectura, no de
  implementacion. Se documentara como ADR cuando la Fase 3 lo requiera, no antes.
- Nivel de "realismo" del entrenamiento distribuido (single-machine multi-proceso simulado
  vs. multi-nodo con Ray) se decide al empezar Fase 5 segun recursos disponibles.
- Kafka vs. Redpanda para el modulo anti-fraude: se arranca con Redpanda por menor
  footprint de recursos en un solo host; migrar a Kafka real es un cambio de imagen Docker,
  no de codigo, si en algun momento hace falta el ecosistema completo (Kafka Connect, etc.).
- Prefect vs. Airflow para orquestacion de pipelines: se documentara como ADR si en algun
  momento se decide practicar el modelo mas pesado de Airflow.
- Feature store propio vs. Feast: se revisita como ADR si mantener la version propia se
  convierte en el cuello de botella de alguna fase.
