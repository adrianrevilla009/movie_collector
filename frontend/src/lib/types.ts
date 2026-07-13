export interface User {
  id: string;
  email: string;
  name: string;
  role: "user" | "admin";
}

export interface MovieListItem {
  id: number;
  title: string;
  release_date: string | null;
  vote_average: number;
  popularity: number | null;
  poster_path: string | null;
}

export interface MovieDetail extends MovieListItem {
  original_title: string | null;
  overview: string | null;
  vote_count: number;
  collection_id: number | null;
  videos: unknown[];
  backdrop_path: string | null;
}

export interface PaginatedMovies {
  items: MovieListItem[];
  page: number;
  size: number;
  total: number;
  total_pages: number;
}

export interface Genre {
  id: number;
  name: string;
}