import { Star } from "lucide-react";
import { Link } from "react-router-dom";
import { useState } from "react";
import type { MovieListItem } from "../lib/types";
import { posterUrl } from "../lib/tmdb-image";

export function MovieCard({ movie }: { movie: MovieListItem }) {
  const year = movie.release_date ? movie.release_date.slice(0, 4) : "—";
  const [imageFailed, setImageFailed] = useState(false);
  const src = posterUrl(movie.poster_path);

  return (
    <Link
      to={`/peliculas/${movie.id}`}
      className="group relative flex flex-col rounded-lg bg-surface border border-border overflow-hidden hover:border-marquee/60 transition-colors"
    >
      <div className="aspect-[2/3] bg-surface-raised flex items-center justify-center overflow-hidden">
        {src && !imageFailed ? (
          <img
            src={src}
            alt={`Poster de ${movie.title}`}
            loading="lazy"
            onError={() => setImageFailed(true)}
            className="w-full h-full object-cover"
          />
        ) : (
          // Fallback cuando TMDB no tiene poster para este titulo (o la
          // imagen falla al cargar): placeholder tipografico, coherente con
          // la estetica de cartel de marquesina, nunca un icono roto.
          <span className="font-display text-3xl text-center text-text-muted leading-tight line-clamp-4 p-4">
            {movie.title}
          </span>
        )}
      </div>
      <div className="p-3 flex-1 flex flex-col gap-1">
        <h3 className="text-sm font-medium text-text line-clamp-1 group-hover:text-marquee transition-colors">
          {movie.title}
        </h3>
        <div className="flex items-center justify-between text-xs text-text-muted">
          <span>{year}</span>
          <span className="flex items-center gap-1 tabular">
            <Star size={12} className="text-marquee fill-marquee" />
            {movie.vote_average.toFixed(1)}
          </span>
        </div>
      </div>
    </Link>
  );
}