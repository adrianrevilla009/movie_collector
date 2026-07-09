from pydantic import BaseModel


class GenreOut(BaseModel):
    id: int
    name: str
    model_config = {"from_attributes": True}


class MovieListItemOut(BaseModel):
    id: int
    title: str
    release_date: str | None
    vote_average: float
    popularity: float | None
    model_config = {"from_attributes": True}


class MovieDetailOut(BaseModel):
    id: int
    title: str
    original_title: str | None
    overview: str | None
    release_date: str | None
    popularity: float | None
    vote_count: int
    vote_average: float
    collection_id: int | None
    videos: list | None
    model_config = {"from_attributes": True}


class PersonOut(BaseModel):
    id: int
    name: str
    biography: str | None
    profile_path: str | None
    model_config = {"from_attributes": True}


class CollectionOut(BaseModel):
    id: int
    name: str
    overview: str | None
    poster_path: str | None
    model_config = {"from_attributes": True}


class PaginatedMovies(BaseModel):
    items: list[MovieListItemOut]
    next_cursor: str | None
