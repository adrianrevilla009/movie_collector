import { ChevronLeft, ChevronRight } from "lucide-react";

interface PaginationProps {
  page: number;
  totalPages: number;
  onPageChange: (page: number) => void;
}

function pageWindow(current: number, total: number): (number | "…")[] {
  const delta = 1;
  const pages: (number | "…")[] = [];
  for (let p = 1; p <= total; p++) {
    if (p === 1 || p === total || (p >= current - delta && p <= current + delta)) {
      pages.push(p);
    } else if (pages[pages.length - 1] !== "…") {
      pages.push("…");
    }
  }
  return pages;
}

export function Pagination({ page, totalPages, onPageChange }: PaginationProps) {
  if (totalPages <= 1) return null;

  return (
    <nav className="flex items-center justify-center gap-1 mt-10" aria-label="Paginacion">
      <button
        onClick={() => onPageChange(page - 1)}
        disabled={page <= 1}
        className="p-2 rounded-md border border-border text-text-muted hover:border-marquee hover:text-marquee disabled:opacity-30 disabled:hover:border-border disabled:hover:text-text-muted transition-colors"
        aria-label="Pagina anterior"
      >
        <ChevronLeft size={16} />
      </button>

      {pageWindow(page, totalPages).map((p, i) =>
        p === "…" ? (
          <span key={`ellipsis-${i}`} className="px-2 text-text-muted text-sm">
            …
          </span>
        ) : (
          <button
            key={p}
            onClick={() => onPageChange(p)}
            aria-current={p === page ? "page" : undefined}
            className={`min-w-9 h-9 rounded-md text-sm tabular transition-colors ${
              p === page
                ? "bg-marquee text-bg font-medium"
                : "text-text-muted hover:text-marquee border border-transparent hover:border-marquee"
            }`}
          >
            {p}
          </button>
        ),
      )}

      <button
        onClick={() => onPageChange(page + 1)}
        disabled={page >= totalPages}
        className="p-2 rounded-md border border-border text-text-muted hover:border-marquee hover:text-marquee disabled:opacity-30 disabled:hover:border-border disabled:hover:text-text-muted transition-colors"
        aria-label="Pagina siguiente"
      >
        <ChevronRight size={16} />
      </button>
    </nav>
  );
}