import { useState } from "react";
import { Film, MailCheck } from "lucide-react";
import { Link } from "react-router-dom";
import { useAuth } from "../lib/auth-context";
import { ApiError } from "../lib/api";

export function Register() {
  const { register } = useAuth();
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await register(email, name, password);
      setDone(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "No se pudo completar el registro");
    } finally {
      setSubmitting(false);
    }
  }

  if (done) {
    return (
      <div className="min-h-[calc(100vh-64px)] flex items-center justify-center px-4">
        <div className="max-w-sm text-center flex flex-col items-center gap-3">
          <MailCheck className="text-marquee" size={40} strokeWidth={1.5} />
          <h1 className="font-display text-3xl tracking-wide">Revisa tu correo</h1>
          <p className="text-text-muted text-sm">
            Te hemos enviado un enlace de verificacion a <strong className="text-text">{email}</strong>.
            Verifica tu cuenta para poder publicar resenas.
          </p>
          <Link to="/login" className="text-marquee hover:underline text-sm mt-2">
            Ir a iniciar sesion
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-[calc(100vh-64px)] flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className="flex flex-col items-center mb-8">
          <Film className="text-marquee mb-2" size={32} strokeWidth={1.5} />
          <h1 className="font-display text-3xl tracking-wide">Crea tu cuenta</h1>
          <p className="text-text-muted text-sm mt-1">Guarda listas, valora y escribe resenas</p>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <label className="flex flex-col gap-1.5 text-sm">
            Nombre
            <input
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="bg-surface border border-border rounded-md px-3 py-2 text-text focus:border-marquee outline-none"
            />
          </label>

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
              minLength={10}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="bg-surface border border-border rounded-md px-3 py-2 text-text focus:border-marquee outline-none"
            />
            <span className="text-xs text-text-muted">Minimo 10 caracteres, evita contrasenas comunes.</span>
          </label>

          {error && <p className="text-reel text-sm">{error}</p>}

          <button
            type="submit"
            disabled={submitting}
            className="mt-2 bg-marquee text-bg font-medium rounded-md py-2.5 hover:bg-marquee-dim transition-colors disabled:opacity-50"
          >
            {submitting ? "Creando cuenta..." : "Crear cuenta"}
          </button>
        </form>

        <p className="text-center text-sm text-text-muted mt-6">
          Ya tienes cuenta?{" "}
          <Link to="/login" className="text-marquee hover:underline">
            Entra
          </Link>
        </p>
      </div>
    </div>
  );
}
