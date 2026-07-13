import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Outlet, RouterProvider, createBrowserRouter } from "react-router-dom";
import { AuthProvider } from "./lib/auth-context";
import { NavBar } from "./components/NavBar";
import { Home } from "./pages/Home";
import { Search } from "./pages/Search";
import { MovieDetail } from "./pages/MovieDetail";
import { Rankings } from "./pages/Rankings";
import { Login } from "./pages/Login";
import { Register } from "./pages/Register";
import { VerifyEmail } from "./pages/VerifyEmail";

function Layout() {
  return (
    <>
      <NavBar />
      <Outlet />
    </>
  );
}

const router = createBrowserRouter([
  {
    element: <Layout />,
    children: [
      { path: "/", element: <Home /> },
      { path: "/buscar", element: <Search /> },
      { path: "/peliculas/:id", element: <MovieDetail /> },
      { path: "/rankings/:type", element: <Rankings /> },
      { path: "/login", element: <Login /> },
      { path: "/registro", element: <Register /> },
      { path: "/verificar-email", element: <VerifyEmail /> },
    ],
  },
]);

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, staleTime: 30_000 } },
});

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <RouterProvider router={router} />
      </AuthProvider>
    </QueryClientProvider>
  );
}

export default App;
