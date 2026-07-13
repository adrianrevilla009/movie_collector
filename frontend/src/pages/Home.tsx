import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { listMovies } from "../lib/catalog";
import { MovieCard } from "../components/MovieCard";
import { Pagination } from "../components/Pagination";

const PAGE_SIZE = 20;

export function Home() {
  const [params, setParams] = useSearchParams();
  const page = Number(params.get("page") ?? "1");

  const { data, isLoading, isError } = useQuery({
    queryKey: ["movies", "home", page],
    queryFn: () => listMovies(page, PAGE_SIZE),
    placeholderData: (previous) => previous, // evita parpadeo al cambiar de pagina
  });

  function goToPage(p: number) {
    setParams({ page: String(p) });
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  return (
    <div className="mx-auto max-w-6xl px-4 py-10">
      <div className="mb-8 flex items-end justify-between">
        <div>
          <p className="text-marquee text-xs tracking-[0.2em] uppercase mb-1">Ahora en cartel</p>
          <h1 className="font-display text-4xl tracking-wide">Explora el catalogo</h1>
        </div>
        {data && (
          <p className="text-text-muted text-sm tabular">
            {data.total.toLocaleString("es")} peliculas
          </p>
        )}
      </div>

      {isLoading && <p className="text-text-muted">Cargando peliculas...</p>}
      {isError && (
        <p className="text-reel">
          No se pudo cargar el catalogo. Comprueba que la API este corriendo en{" "}
          {import.meta.env.VITE_API_BASE_URL as string}.
        </p>
      )}

      {data && data.items.length === 0 && (
        <p className="text-text-muted">
          El catalogo esta vacio todavia. Corre <code className="text-marquee">make ingest</code> para
          poblarlo.
        </p>
      )}

      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
        {data?.items.map((movie) => (
          <MovieCard key={movie.id} movie={movie} />
        ))}
      </div>

      {data && <Pagination page={data.page} totalPages={data.total_pages} onPageChange={goToPage} />}
    </div>
  );
}