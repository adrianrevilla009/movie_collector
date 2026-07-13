import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { apiFetch, setAccessToken } from "./api";
import type { User } from "./types";

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, name: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

// El backend no expone /users/me todavia como tal (Fase 0.5 trae parte de
// esto); decodificamos el propio JWT (payload publico, no verificado en
// cliente - la verificacion real la hace el servidor en cada peticion) solo
// para saber id/rol y pintar la UI. Nunca se usa esto como fuente de verdad
// de autorizacion, solo de presentacion.
function decodeUserFromToken(token: string): Pick<User, "id" | "role"> | null {
  try {
    const payload = JSON.parse(atob(token.split(".")[1]));
    return { id: payload.sub, role: payload.role };
  } catch {
    return null;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  // Cookie NO httpOnly, solo indica "probablemente hay sesion" (el backend
  // la pone junto a la de refresh real). Si no esta, no hace falta ni
  // arrancar en estado "loading": evita una llamada a /auth/refresh en cada
  // carga sin sesion (evita un 401 esperado pero ruidoso en la consola).
  const [loading, setLoading] = useState(() => document.cookie.includes("has_session=1"));

  useEffect(() => {
    if (!document.cookie.includes("has_session=1")) return;

    apiFetch<{ access_token: string }>("/api/v1/auth/refresh", {
      method: "POST",
      skipAuthRetry: true,
    })
      .then((data) => {
        setAccessToken(data.access_token);
        const decoded = decodeUserFromToken(data.access_token);
        if (decoded) setUser({ ...decoded, email: "", name: "" });
      })
      .catch(() => {
        /* cookie de marcador presente pero refresh invalido/expirado, normal */
      })
      .finally(() => setLoading(false));
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const data = await apiFetch<{ access_token: string }>("/api/v1/auth/login", {
      method: "POST",
      body: { email, password },
      skipAuthRetry: true,
    });
    setAccessToken(data.access_token);
    const decoded = decodeUserFromToken(data.access_token);
    if (decoded) setUser({ ...decoded, email, name: "" });
  }, []);

  const register = useCallback(async (email: string, name: string, password: string) => {
    await apiFetch("/api/v1/auth/register", {
      method: "POST",
      body: { email, name, password },
      skipAuthRetry: true,
    });
    // El registro no inicia sesion automaticamente: hay que verificar el
    // email primero para algunas acciones (Seccion 2.4), pero login si
    // funciona antes de verificar.
  }, []);

  const logout = useCallback(async () => {
    try {
      await apiFetch("/api/v1/auth/logout", { method: "POST" });
    } finally {
      setAccessToken(null);
      setUser(null);
    }
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth debe usarse dentro de <AuthProvider>");
  return ctx;
}