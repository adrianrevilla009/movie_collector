import { useState } from "react";
import { MailCheck } from "lucide-react";
import { Link } from "react-router-dom";
import { apiFetch, ApiError } from "../lib/api";

export function VerifyEmail() {
  const [token, setToken] = useState("");
  const [status, setStatus] = useState<"idle" | "ok" | "error">("idle");
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    try {
      await apiFetch("/api/v1/auth/verify-email", {
        method: "POST",
        body: { token: token.trim() },
        skipAuthRetry: true,
      });
      setStatus("ok");
    } catch (err) {
      setStatus("error");
      setError(err instanceof ApiError ? err.detail : "Token invalido");
    }
  }

  if (status === "ok") {
    return (
      <div className="min-h-[calc(100vh-64px)] flex items-center justify-center px-4">
        <div className="max-w-sm text-center flex flex-col items-center gap-3">
          <MailCheck className="text-marquee" size={40} strokeWidth={1.5} />
          <h1 className="font-display text-3xl tracking-wide">Email verificado</h1>
          <Link to="/login" className="text-marquee hover:underline text-sm">
            Ir a iniciar sesion
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-[calc(100vh-64px)] flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <h1 className="font-display text-3xl tracking-wide mb-2">Verifica tu email</h1>
        <p className="text-text-muted text-sm mb-6">
          Pega aqui el token del correo que te envio Mailpit (
          <a
            href="http://localhost:8025"
            target="_blank"
            rel="noreferrer"
            className="text-marquee hover:underline"
          >
            localhost:8025
          </a>
          ).
        </p>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <input
            required
            value={token}
            onChange={(e) => setToken(e.target.value)}
            placeholder="Token de verificacion"
            className="bg-surface border border-border rounded-md px-3 py-2 text-text focus:border-marquee outline-none"
          />
          {status === "error" && <p className="text-reel text-sm">{error}</p>}
          <button
            type="submit"
            className="bg-marquee text-bg font-medium rounded-md py-2.5 hover:bg-marquee-dim transition-colors"
          >
            Verificar
          </button>
        </form>
      </div>
    </div>
  );
}
