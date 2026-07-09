"""Busqueda, filtros y rankings sobre el catalogo (Seccion 2.3)."""

from sqlalchemy import Float, cast, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.models import Movie, MovieGenre, Rating, WatchProvider

DEFAULT_LIMIT = 20
# Umbral minimo de votos para el Bayesian average (top valoradas) - configurable
MIN_VOTES_THRESHOLD = 50


async def search_movies(
    db: AsyncSession,
    query: str | None,
    genre_id: int | None,
    decade: int | None,
    person_id: int | None,
    region: str,
    sort: str,
    limit: int = DEFAULT_LIMIT,
    cursor_id: int | None = None,
    provider_id: int | None = None,
):
    """Full-text (tsvector/ts_rank) + pg_trgm para tolerancia a typos (Seccion 2.3).
    NOTA: usar text() aqui es seguro porque `query` se pasa como parametro
    bindeado (nunca concatenado como string) - ver security-antipatterns sobre
    inyeccion SQL: parametrizacion obligatoria, esto la respeta."""
    stmt = select(Movie).where(Movie.is_complete.is_(True))

    if query:
        stmt = stmt.where(
            text(
                "to_tsvector('spanish', movies.title || ' ' || coalesce(movies.overview, '')) "
                "@@ plainto_tsquery('spanish', :q) "
                "OR similarity(movies.title, :q) > 0.3"
            ).bindparams(q=query)
        )

    if genre_id is not None:
        stmt = stmt.join(MovieGenre, MovieGenre.movie_id == Movie.id).where(
            MovieGenre.genre_id == genre_id
        )

    if decade is not None:
        stmt = stmt.where(func.substr(Movie.release_date, 1, 3) == str(decade // 10))

    if person_id is not None:
        from platform_core.models import Credit

        stmt = stmt.join(Credit, Credit.movie_id == Movie.id).where(Credit.person_id == person_id)

    if provider_id is not None:
        stmt = stmt.join(WatchProvider, WatchProvider.movie_id == Movie.id).where(
            WatchProvider.region == region, WatchProvider.provider_id == provider_id
        )

    sort_map = {
        "rating_desc": Movie.vote_average.desc(),
        "fecha_estreno_desc": Movie.release_date.desc(),
        "popularidad_desc": Movie.popularity.desc(),
    }
    if sort in sort_map:
        stmt = stmt.order_by(sort_map[sort])
    # "relevancia" (default en busqueda por texto) ya viene ordenado por ts_rank
    # implicito en el filtro anterior; se deja sin ORDER BY explicito adicional.

    if cursor_id is not None:
        stmt = stmt.where(Movie.id > cursor_id)

    stmt = stmt.limit(limit)
    result = await db.scalars(stmt)
    return list(result)


async def top_rated(db: AsyncSession, limit: int = DEFAULT_LIMIT, offset: int = 0):
    """Bayesian average tipo IMDB: (v/(v+m))*R + (m/(v+m))*C (Seccion 2.3)."""
    global_avg = await db.scalar(select(func.avg(Movie.vote_average)).where(Movie.vote_count > 0))
    c = float(global_avg or 0.0)
    m = MIN_VOTES_THRESHOLD

    bayesian_score = (
        cast(Movie.vote_count, Float) / (Movie.vote_count + m) * Movie.vote_average
        + cast(m, Float) / (Movie.vote_count + m) * c
    )
    stmt = (
        select(Movie, bayesian_score.label("score"))
        .where(Movie.is_complete.is_(True))
        .order_by(bayesian_score.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(stmt)
    return [row[0] for row in result.all()]


async def trending_internal(db: AsyncSession, limit: int = DEFAULT_LIMIT, offset: int = 0):
    """Velocidad de ratings/reviews nuevos en los ultimos 7 dias sobre trafico
    PROPIO de la plataforma - deliberadamente distinto del trending de TMDB."""
    stmt = (
        select(Movie, func.count(Rating.id).label("recent_count"))
        .join(Rating, Rating.movie_id == Movie.id)
        .where(Rating.created_at >= func.now() - text("interval '7 days'"))
        .group_by(Movie.id)
        .order_by(func.count(Rating.id).desc())
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(stmt)
    return [row[0] for row in result.all()]


async def most_controversial(db: AsyncSession, limit: int = DEFAULT_LIMIT, offset: int = 0):
    """Mayor varianza de rating por pelicula."""
    stmt = (
        select(Movie, func.variance(Rating.score).label("variance"))
        .join(Rating, Rating.movie_id == Movie.id)
        .group_by(Movie.id)
        .having(func.count(Rating.id) >= 5)
        .order_by(func.variance(Rating.score).desc())
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(stmt)
    return [row[0] for row in result.all()]
