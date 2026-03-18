import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import Layout from './components/Layout';
import PriceListPage from './pages/PriceListPage';
import HistoryPage from './pages/HistoryPage';
import SourcesPage from './pages/SourcesPage';
import UnresolvedPage from './pages/UnresolvedPage';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30000,
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route path="/" element={<PriceListPage />} />
            <Route path="/history/:productId" element={<HistoryPage />} />
            <Route path="/sources" element={<SourcesPage />} />
            <Route path="/unresolved" element={<UnresolvedPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
