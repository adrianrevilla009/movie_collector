/**
 * Cliente de API minimo: adjunta el access token, y si una peticion falla
 * con 401, intenta refrescar UNA vez via la cookie httpOnly antes de
 * reintentar (Seccion 2.4). Si el refresh tambien falla, propaga el 401
 * para que el AuthContext cierre la sesion en el cliente.
 */

const BASE_URL = import.meta.env.VITE_API_BASE_URL as string;

export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.status = status;
    this.detail = detail;
  }
}

let accessToken: string | null = null;
let refreshPromise: Promise<boolean> | null = null;

export function setAccessToken(token: string | null) {
  accessToken = token;
}

export function getAccessToken() {
  return accessToken;
}

async function tryRefresh(): Promise<boolean> {
  // Coalesce: si varias peticiones fallan a la vez, solo se refresca una vez.
  if (!refreshPromise) {
    refreshPromise = fetch(`${BASE_URL}/api/v1/auth/refresh`, {
      method: "POST",
      credentials: "include",
    })
      .then(async (r) => {
        if (!r.ok) return false;
        const data = await r.json();
        setAccessToken(data.access_token);
        return true;
      })
      .catch(() => false)
      .finally(() => {
        refreshPromise = null;
      });
  }
  return refreshPromise;
}

interface RequestOptions extends Omit<RequestInit, "body"> {
  body?: unknown;
  skipAuthRetry?: boolean;
}

export async function apiFetch<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { body, skipAuthRetry, headers, ...rest } = options;

  const doFetch = async () => {
    const finalHeaders: Record<string, string> = {
      ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
      ...(headers as Record<string, string>),
    };
    return fetch(`${BASE_URL}${path}`, {
      ...rest,
      headers: finalHeaders,
      credentials: "include",
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  };

  let response = await doFetch();

  if (response.status === 401 && !skipAuthRetry) {
    const refreshed = await tryRefresh();
    if (refreshed) {
      response = await doFetch();
    }
  }

  if (!response.ok) {
    // El backend responde RFC 7807 (Seccion 2.6): { title, detail, status, ... }
    let detail = `Error ${response.status}`;
    try {
      const problem = await response.json();
      detail = problem.detail || problem.title || detail;
    } catch {
      /* respuesta sin cuerpo JSON */
    }
    throw new ApiError(response.status, detail);
  }

  if (response.status === 204) return undefined as T;
  return response.json();
}
