import { useQuery } from "@tanstack/react-query";
import { useParams, useSearchParams } from "react-router-dom";
import { getRanking, type RankingType } from "../lib/catalog";
import { MovieCard } from "../components/MovieCard";
import { Pagination } from "../components/Pagination";

const PAGE_SIZE = 20;

const TITLES: Record<RankingType, { label: string; eyebrow: string }> = {
  "top-rated": { label: "Mejor valoradas", eyebrow: "Ranking bayesiano" },
  trending: { label: "Tendencias", eyebrow: "Actividad de la ultima semana" },
  "most-controversial": { label: "Mas controvertidas", eyebrow: "Mayor divergencia de opiniones" },
};

export function Rankings() {
  const { type } = useParams<{ type: RankingType }>();
  const rankingType = (type ?? "top-rated") as RankingType;
  const meta = TITLES[rankingType] ?? TITLES["top-rated"];

  const [params, setParams] = useSearchParams();
  const page = Number(params.get("page") ?? "1");

  const { data, isLoading } = useQuery({
    queryKey: ["rankings", rankingType, page],
    queryFn: () => getRanking(rankingType, page, PAGE_SIZE),
    placeholderData: (previous) => previous,
  });

  function goToPage(p: number) {
    setParams({ page: String(p) });
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  return (
    <div className="mx-auto max-w-6xl px-4 py-10">
      <p className="text-marquee text-xs tracking-[0.2em] uppercase mb-1">{meta.eyebrow}</p>
      <h1 className="font-display text-4xl tracking-wide mb-8">{meta.label}</h1>

      {isLoading && <p className="text-text-muted">Cargando...</p>}
      {data && data.items.length === 0 && (
        <p className="text-text-muted">Todavia no hay suficientes datos para este ranking.</p>
      )}

      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
        {data?.items.map((movie, i) => (
          <div key={movie.id} className="relative">
            <span className="absolute -top-2 -left-2 z-10 font-display text-xl bg-marquee text-bg rounded-full w-8 h-8 flex items-center justify-center">
              {(page - 1) * PAGE_SIZE + i + 1}
            </span>
            <MovieCard movie={movie} />
          </div>
        ))}
      </div>

      {data && <Pagination page={data.page} totalPages={data.total_pages} onPageChange={goToPage} />}
    </div>
  );
}