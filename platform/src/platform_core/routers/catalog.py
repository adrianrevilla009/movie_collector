import math

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.config import get_settings
from platform_core.db import get_db
from platform_core.models import Collection, Genre, Movie, Person
from platform_core.schemas.catalog import (
    CollectionOut,
    GenreOut,
    MovieDetailOut,
    PaginatedMovies,
    PersonOut,
)
from platform_core.services import catalog_service

router = APIRouter(prefix="/api/v1", tags=["catalog"])
settings = get_settings()


def _paginated(items: list[Movie], total: int, page: int, size: int) -> PaginatedMovies:
    return PaginatedMovies(
        items=items,
        page=page,
        size=size,
        total=total,
        total_pages=max(1, math.ceil(total / size)) if size else 1,
    )


@router.get("/movies", response_model=PaginatedMovies)
async def list_movies(
    db: AsyncSession = Depends(get_db),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
):
    movies, total = await catalog_service.search_movies(
        db,
        query=None,
        genre_id=None,
        decade=None,
        person_id=None,
        region=settings.default_region,
        sort="popularidad_desc",
        page=page,
        size=size,
        provider_id=None,
    )
    return _paginated(movies, total, page, size)


@router.get("/movies/search", response_model=PaginatedMovies)
async def search_movies(
    db: AsyncSession = Depends(get_db),
    q: str | None = None,
    genre_id: int | None = None,
    decade: int | None = None,
    person_id: int | None = None,
    provider_id: int | None = Query(
        default=None, description="Filtra por plataforma de streaming (usa `region`)"
    ),
    region: str = Query(default=settings.default_region),
    sort: str = Query(default="relevancia"),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
):
    movies, total = await catalog_service.search_movies(
        db,
        query=q,
        genre_id=genre_id,
        decade=decade,
        person_id=person_id,
        region=region,
        sort=sort,
        page=page,
        size=size,
        provider_id=provider_id,
    )
    return _paginated(movies, total, page, size)


@router.get("/movies/{movie_id}", response_model=MovieDetailOut)
async def get_movie(movie_id: int, db: AsyncSession = Depends(get_db)):
    movie = await db.get(Movie, movie_id)
    if movie is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Pelicula no encontrada")
    return movie


@router.get("/movies/{movie_id}/videos")
async def get_movie_videos(movie_id: int, db: AsyncSession = Depends(get_db)):
    movie = await db.get(Movie, movie_id)
    if movie is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Pelicula no encontrada")
    return {"videos": movie.videos or []}


@router.get("/movies/{movie_id}/similar")
async def get_similar_movies(movie_id: int, db: AsyncSession = Depends(get_db)):
    """Fallback TMDB hasta que exista el recomendador de la Fase 2 (Seccion 2.7).
    Cuando la Fase 2 cierre, este endpoint cambia de implementacion por dentro
    sin cambiar el contrato."""
    movie = await db.get(Movie, movie_id)
    if movie is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Pelicula no encontrada")
    similar_ids = (movie.raw_metadata or {}).get("similar_tmdb_ids", [])
    if not similar_ids:
        return {"items": []}
    result = await db.scalars(select(Movie).where(Movie.id.in_(similar_ids)))
    return {"items": list(result)}


@router.get("/people/{person_id}", response_model=PersonOut)
async def get_person(person_id: int, db: AsyncSession = Depends(get_db)):
    person = await db.get(Person, person_id)
    if person is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Persona no encontrada")
    return person


@router.get("/collections/{collection_id}", response_model=CollectionOut)
async def get_collection(collection_id: int, db: AsyncSession = Depends(get_db)):
    collection = await db.get(Collection, collection_id)
    if collection is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Coleccion no encontrada")
    return collection


@router.get("/genres", response_model=list[GenreOut])
async def list_genres(db: AsyncSession = Depends(get_db)):
    result = await db.scalars(select(Genre).order_by(Genre.name))
    return list(result)


@router.get("/rankings/top-rated", response_model=PaginatedMovies)
async def rankings_top_rated(
    db: AsyncSession = Depends(get_db),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
):
    movies, total = await catalog_service.top_rated(db, limit=size, offset=(page - 1) * size)
    return _paginated(movies, total, page, size)


@router.get("/rankings/trending", response_model=PaginatedMovies)
async def rankings_trending(
    db: AsyncSession = Depends(get_db),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
):
    movies, total = await catalog_service.trending_internal(
        db, limit=size, offset=(page - 1) * size
    )
    return _paginated(movies, total, page, size)


@router.get("/rankings/most-controversial", response_model=PaginatedMovies)
async def rankings_most_controversial(
    db: AsyncSession = Depends(get_db),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
):
    movies, total = await catalog_service.most_controversial(
        db, limit=size, offset=(page - 1) * size
    )
    return _paginated(movies, total, page, size)