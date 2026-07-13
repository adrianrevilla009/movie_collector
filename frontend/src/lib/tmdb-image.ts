/**
 * TMDB sirve las imagenes desde su propio CDN de imagenes, no desde nuestra
 * API - solo guardamos el path relativo (ej. "/abc123.jpg") y aqui se
 * construye la URL completa. Tamanos documentados en
 * https://developer.themoviedb.org/docs/image-basics
 */
const IMAGE_BASE = "https://image.tmdb.org/t/p";

export function posterUrl(path: string | null, size: "w185" | "w342" | "w500" = "w342") {
  return path ? `${IMAGE_BASE}/${size}${path}` : null;
}

export function backdropUrl(path: string | null, size: "w780" | "w1280" = "w1280") {
  return path ? `${IMAGE_BASE}/${size}${path}` : null;
}