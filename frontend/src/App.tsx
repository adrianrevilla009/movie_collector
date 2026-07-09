import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider, createBrowserRouter } from "react-router-dom";

// Mapa de rutas fijado en el plan (Seccion 4.3): se completa pagina a pagina
// a partir de la Fase 0.3 (catalogo). Fase 0.1 solo monta el esqueleto.
const router = createBrowserRouter([
  {
    path: "/",
    element: <div className="p-8 text-center text-lg">Cine Platform - en construccion</div>,
  },
]);

const queryClient = new QueryClient();

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  );
}

export default App;
