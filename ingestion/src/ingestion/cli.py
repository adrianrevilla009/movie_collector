"""CLI de ingestion (usado por `make ingest`, ver Makefile raiz)."""

import asyncio
from pathlib import Path

import click
import structlog

from ingestion.backfill import load_dev_movie_ids, make_session_factory, run_backfill
from ingestion.config import get_ingestion_settings
from ingestion.movielens_seed import seed_ratings_from_movielens
from ingestion.transform import transform_bronze_to_silver

logger = structlog.get_logger("ingestion.cli")
settings = get_ingestion_settings()


@click.group()
def cli():
    pass


@cli.command()
@click.option(
    "--full",
    is_flag=True,
    help="Backfill completo (~1M titulos, ~7h). Por defecto usa el alcance acotado de desarrollo.",
)
@click.option("--limit", type=int, default=None, help="Sobrescribe el limite de IDs a procesar.")
def backfill(full: bool, limit: int | None):
    """Backfill del catalogo TMDB hacia bronze (Seccion 2.1)."""
    if full:
        click.echo(
            "ADVERTENCIA: --full no esta implementado en Fase 0.1 (requiere el "
            "export diario de IDs de TMDB, ver TODO en ingestion/backfill.py). "
            "Usa el alcance de desarrollo por ahora."
        )
    n = limit or settings.dev_backfill_limit
    movie_ids = load_dev_movie_ids(n)
    session_factory = make_session_factory()
    result = asyncio.run(run_backfill(session_factory, movie_ids, full=full))
    click.echo(f"Backfill: {result}")


@cli.command()
def transform():
    """Transformacion bronze -> silver (ver docs/adr/0001)."""
    session_factory = make_session_factory()
    result = asyncio.run(transform_bronze_to_silver(session_factory))
    click.echo(f"Transform: {result}")


@cli.command(name="seed-movielens")
@click.option(
    "--ratings-csv", type=click.Path(path_type=Path), default=Path("data/movielens/ratings.csv")
)
@click.option(
    "--links-csv", type=click.Path(path_type=Path), default=Path("data/movielens/links.csv")
)
@click.option("--limit", type=int, default=None)
def seed_movielens(ratings_csv: Path, links_csv: Path, limit: int | None):
    """Seed de ratings historicos desde MovieLens (Seccion 2.2)."""
    session_factory = make_session_factory()
    try:
        result = asyncio.run(
            seed_ratings_from_movielens(session_factory, ratings_csv, links_csv, limit=limit)
        )
        click.echo(f"Seed MovieLens: {result}")
    except FileNotFoundError as exc:
        click.echo(str(exc), err=True)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    cli()
