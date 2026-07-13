import { useQuery } from "@tanstack/react-query";
import { Star, Calendar, ArrowLeft } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { useState } from "react";
import { getMovie } from "../lib/catalog";
import { backdropUrl, posterUrl } from "../lib/tmdb-image";

export function MovieDetail() {
  const { id } = useParams<{ id: string }>();
  const { data: movie, isLoading, isError } = useQuery({
    queryKey: ["movie", id],
    queryFn: () => getMovie(id!),
    enabled: !!id,
  });
  const [posterFailed, setPosterFailed] = useState(false);

  if (isLoading) {
    return <p className="mx-auto max-w-4xl px-4 py-10 text-text-muted">Cargando...</p>;
  }

  if (isError || !movie) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-10">
        <p className="text-reel">No se encontro esta pelicula.</p>
        <Link to="/" className="text-marquee hover:underline text-sm">
          Volver al catalogo
        </Link>
      </div>
    );
  }

  const year = movie.release_date ? movie.release_date.slice(0, 4) : "—";
  const backdrop = backdropUrl(movie.backdrop_path);
  const poster = posterUrl(movie.poster_path, "w500");

  return (
    <div className="relative">
      {backdrop && (
        <div
          className="absolute inset-x-0 top-0 h-80 bg-cover bg-center opacity-25 [mask-image:linear-gradient(to_bottom,black,transparent)]"
          style={{ backgroundImage: `url(${backdrop})` }}
          aria-hidden
        />
      )}

      <div className="relative mx-auto max-w-4xl px-4 py-10">
        <Link
          to="/"
          className="flex items-center gap-1.5 text-sm text-text-muted hover:text-marquee mb-6 w-fit"
        >
          <ArrowLeft size={15} /> Volver
        </Link>

        <div className="grid grid-cols-1 md:grid-cols-[240px_1fr] gap-8">
          <div className="aspect-[2/3] bg-surface border border-border rounded-lg flex items-center justify-center overflow-hidden">
            {poster && !posterFailed ? (
              <img
                src={poster}
                alt={`Poster de ${movie.title}`}
                onError={() => setPosterFailed(true)}
                className="w-full h-full object-cover"
              />
            ) : (
              <span className="font-display text-2xl text-center text-text-muted leading-tight p-4">
                {movie.title}
              </span>
            )}
          </div>

          <div>
            <h1 className="font-display text-4xl tracking-wide mb-2">{movie.title}</h1>
            {movie.original_title && movie.original_title !== movie.title && (
              <p className="text-text-muted text-sm mb-4 italic">{movie.original_title}</p>
            )}

            <div className="flex items-center gap-5 text-sm text-text-muted mb-6">
              <span className="flex items-center gap-1.5">
                <Calendar size={14} /> {year}
              </span>
              <span className="flex items-center gap-1.5 tabular">
                <Star size={14} className="text-marquee fill-marquee" />
                {movie.vote_average.toFixed(1)}{" "}
                <span className="text-text-muted">({movie.vote_count} votos)</span>
              </span>
            </div>

            <p className="text-text leading-relaxed">
              {movie.overview || "Sin sinopsis disponible."}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}