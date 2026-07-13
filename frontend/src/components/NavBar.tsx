import { Film, LogOut, Search, User as UserIcon } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import { useState } from "react";
import { useAuth } from "../lib/auth-context";

export function NavBar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [query, setQuery] = useState("");

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    if (query.trim()) navigate(`/buscar?q=${encodeURIComponent(query.trim())}`);
  }

  return (
    <header className="sticky top-0 z-10 bg-surface/95 backdrop-blur border-b border-border">
      <div className="mx-auto max-w-6xl px-4 h-16 flex items-center gap-6">
        <Link to="/" className="flex items-center gap-2 shrink-0">
          <Film className="text-marquee" size={26} strokeWidth={1.75} />
          <span className="font-display text-2xl tracking-wide text-text leading-none">
            CINE<span className="text-marquee">PLATFORM</span>
          </span>
        </Link>

        <form onSubmit={handleSearch} className="flex-1 max-w-md relative">
          <Search
            size={16}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted"
          />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Buscar peliculas..."
            className="w-full bg-surface-raised border border-border rounded-full pl-9 pr-4 py-2 text-sm text-text placeholder:text-text-muted focus:border-marquee outline-none"
          />
        </form>

        <nav className="flex items-center gap-4 text-sm text-text-muted shrink-0">
          <Link to="/rankings/top-rated" className="hover:text-marquee transition-colors">
            Mejor valoradas
          </Link>
          <Link to="/rankings/trending" className="hover:text-marquee transition-colors">
            Tendencias
          </Link>

          {user ? (
            <button
              onClick={() => logout()}
              className="flex items-center gap-1.5 hover:text-reel transition-colors"
            >
              <LogOut size={16} /> Salir
            </button>
          ) : (
            <Link
              to="/login"
              className="flex items-center gap-1.5 rounded-full border border-marquee/50 px-3 py-1.5 text-marquee hover:bg-marquee hover:text-bg transition-colors"
            >
              <UserIcon size={15} /> Entrar
            </Link>
          )}
        </nav>
      </div>
      <div className="film-perf opacity-40" />
    </header>
  );
}
