import { apiFetch } from "./api";
import type { Genre, MovieDetail, PaginatedMovies } from "./types";

export function listMovies(page = 1, size = 20) {
  return apiFetch<PaginatedMovies>(`/api/v1/movies?page=${page}&size=${size}`);
}

export function searchMovies(query: string, page = 1, size = 20) {
  return apiFetch<PaginatedMovies>(
    `/api/v1/movies/search?q=${encodeURIComponent(query)}&page=${page}&size=${size}`,
  );
}

export function getMovie(id: number | string) {
  return apiFetch<MovieDetail>(`/api/v1/movies/${id}`);
}

export function listGenres() {
  return apiFetch<Genre[]>("/api/v1/genres");
}

export type RankingType = "top-rated" | "trending" | "most-controversial";

export function getRanking(type: RankingType, page = 1, size = 20) {
  return apiFetch<PaginatedMovies>(`/api/v1/rankings/${type}?page=${page}&size=${size}`);
}