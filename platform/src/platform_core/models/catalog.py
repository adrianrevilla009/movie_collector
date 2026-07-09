"""Capa silver: catalogo (movies, people, collections, genres, credits, etc.)."""

import enum

from sqlalchemy import (
    JSON,
    Boolean,
    Enum,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from platform_core.db import Base


class CreditType(str, enum.Enum):
    cast = "cast"
    crew = "crew"


class Collection(Base):
    __tablename__ = "collections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)  # id TMDB
    name: Mapped[str] = mapped_column(String(255))
    overview: Mapped[str | None] = mapped_column(Text, nullable=True)
    poster_path: Mapped[str | None] = mapped_column(String(255), nullable=True)


class Genre(Base):
    __tablename__ = "genres"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)  # id TMDB
    name: Mapped[str] = mapped_column(String(64), unique=True)


class Movie(Base):
    __tablename__ = "movies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)  # id TMDB
    title: Mapped[str] = mapped_column(String(500), index=True)
    original_title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    overview: Mapped[str | None] = mapped_column(Text, nullable=True)
    release_date: Mapped[str | None] = mapped_column(String(10), nullable=True)  # YYYY-MM-DD
    popularity: Mapped[float | None] = mapped_column(nullable=True)
    vote_count: Mapped[int] = mapped_column(Integer, default=0)
    vote_average: Mapped[float] = mapped_column(default=0.0)
    adult: Mapped[bool] = mapped_column(Boolean, default=False)
    # Filtro de calidad, no de cobertura (Seccion 2.1): se ingesta el 100% de IDs,
    # pero solo se marca "completo" lo que tiene senal minima.
    is_complete: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    collection_id: Mapped[int | None] = mapped_column(ForeignKey("collections.id"), nullable=True)
    videos: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # trailers, Seccion 2.7
    raw_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class Person(Base):
    __tablename__ = "people"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)  # id TMDB
    name: Mapped[str] = mapped_column(String(255), index=True)
    biography: Mapped[str | None] = mapped_column(Text, nullable=True)
    profile_path: Mapped[str | None] = mapped_column(String(255), nullable=True)


class Credit(Base):
    __tablename__ = "credits"
    __table_args__ = (
        UniqueConstraint("movie_id", "person_id", "credit_type", "job", "character_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    movie_id: Mapped[int] = mapped_column(ForeignKey("movies.id"), index=True)
    person_id: Mapped[int] = mapped_column(ForeignKey("people.id"), index=True)
    credit_type: Mapped[CreditType] = mapped_column(Enum(CreditType, name="credit_type"))
    character_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    job: Mapped[str | None] = mapped_column(String(255), nullable=True)
    order: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)


class MovieGenre(Base):
    __tablename__ = "movie_genres"

    movie_id: Mapped[int] = mapped_column(ForeignKey("movies.id"), primary_key=True)
    genre_id: Mapped[int] = mapped_column(ForeignKey("genres.id"), primary_key=True)


class Keyword(Base):
    __tablename__ = "keywords"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)  # id TMDB
    name: Mapped[str] = mapped_column(String(128), unique=True)


class MovieKeyword(Base):
    __tablename__ = "movie_keywords"

    movie_id: Mapped[int] = mapped_column(ForeignKey("movies.id"), primary_key=True)
    keyword_id: Mapped[int] = mapped_column(ForeignKey("keywords.id"), primary_key=True)


class WatchProvider(Base):
    """Disponibilidad por region (Seccion 2.3): TMDB devuelve esto por pais."""

    __tablename__ = "watch_providers"
    __table_args__ = (UniqueConstraint("movie_id", "provider_id", "region", "access_type"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    movie_id: Mapped[int] = mapped_column(ForeignKey("movies.id"), index=True)
    provider_id: Mapped[int] = mapped_column(Integer)
    provider_name: Mapped[str] = mapped_column(String(128))
    region: Mapped[str] = mapped_column(String(2), index=True, default="ES")
    access_type: Mapped[str] = mapped_column(String(32))  # flatrate|rent|buy|ads
