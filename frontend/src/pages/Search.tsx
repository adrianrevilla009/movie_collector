import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { searchMovies } from "../lib/catalog";
import { MovieCard } from "../components/MovieCard";
import { Pagination } from "../components/Pagination";

const PAGE_SIZE = 20;

export function Search() {
  const [params, setParams] = useSearchParams();
  const query = params.get("q") ?? "";
  const page = Number(params.get("page") ?? "1");

  const { data, isLoading } = useQuery({
    queryKey: ["movies", "search", query, page],
    queryFn: () => searchMovies(query, page, PAGE_SIZE),
    enabled: query.length > 0,
    placeholderData: (previous) => previous,
  });

  function goToPage(p: number) {
    setParams({ q: query, page: String(p) });
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  return (
    <div className="mx-auto max-w-6xl px-4 py-10">
      <h1 className="font-display text-3xl tracking-wide mb-1">
        Resultados para <span className="text-marquee">"{query}"</span>
      </h1>
      <p className="text-text-muted text-sm mb-8">
        {data ? `${data.total.toLocaleString("es")} resultados. ` : ""}
        Busqueda tolerante a errores tipograficos - prueba con una palabra mal escrita.
      </p>

      {isLoading && <p className="text-text-muted">Buscando...</p>}
      {data && data.items.length === 0 && (
        <p className="text-text-muted">Sin resultados. Prueba con otro termino.</p>
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