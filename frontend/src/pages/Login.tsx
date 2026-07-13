import { useState } from "react";
import { Film } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../lib/auth-context";
import { ApiError } from "../lib/api";

export function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login(email, password);
      navigate("/");
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "No se pudo iniciar sesion");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-[calc(100vh-64px)] flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className="flex flex-col items-center mb-8">
          <Film className="text-marquee mb-2" size={32} strokeWidth={1.5} />
          <h1 className="font-display text-3xl tracking-wide">Bienvenido de vuelta</h1>
          <p className="text-text-muted text-sm mt-1">Entra para valorar y guardar peliculas</p>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <label className="flex flex-col gap-1.5 text-sm">
            Email
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="bg-surface border border-border rounded-md px-3 py-2 text-text focus:border-marquee outline-none"
            />
          </label>

          <label className="flex flex-col gap-1.5 text-sm">
            Contrasena
            <input
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="bg-surface border border-border rounded-md px-3 py-2 text-text focus:border-marquee outline-none"
            />
          </label>

          {error && <p className="text-reel text-sm">{error}</p>}

          <button
            type="submit"
            disabled={submitting}
            className="mt-2 bg-marquee text-bg font-medium rounded-md py-2.5 hover:bg-marquee-dim transition-colors disabled:opacity-50"
          >
            {submitting ? "Entrando..." : "Entrar"}
          </button>
        </form>

        <p className="text-center text-sm text-text-muted mt-6">
          No tienes cuenta?{" "}
          <Link to="/registro" className="text-marquee hover:underline">
            Registrate
          </Link>
        </p>
      </div>
    </div>
  );
}
