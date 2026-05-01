import { useState, useCallback } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getPriceList } from '../api/client';
import type { PriceListFilters } from '../types';
import PriceListTable from '../components/PriceList/PriceListTable';
import PriceListFiltersPanel from '../components/PriceList/PriceListFilters';
import ExportButton from '../components/PriceList/ExportButton';
import { useAutoRefresh } from '../hooks/useAutoRefresh';
import { Search, RefreshCw, Loader2, Pause, Play } from 'lucide-react';

const defaultFilters: PriceListFilters = {
  page: 1,
  per_page: 25,
  sort_by: 'best_price',
  order: 'asc',
};

export default function PriceListPage() {
  const [filters, setFilters] = useState<PriceListFilters>(defaultFilters);
  const [searchInput, setSearchInput] = useState('');

  const { data, isLoading, refetch, isFetching } = useQuery({
    queryKey: ['priceList', filters],
    queryFn: () => getPriceList(filters),
  });

  const { isAutoRefresh, setIsAutoRefresh, secondsAgo, refresh } = useAutoRefresh(
    useCallback(() => { refetch(); }, [refetch]),
    60000
  );

  const handleSearch = () => {
    setFilters(f => ({ ...f, search: searchInput || undefined, page: 1 }));
  };

  const handleSearchKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') handleSearch();
  };

  const handleReset = () => {
    setFilters(defaultFilters);
    setSearchInput('');
  };

  return (
    <div className="flex h-[calc(100vh-7.5rem)]">
      {/* Filter Panel */}
      <PriceListFiltersPanel
        filters={filters}
        onChange={setFilters}
        onReset={handleReset}
      />

      {/* Main Content */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Toolbar: search + refresh + export */}
        <div className="px-4 py-2.5 bg-surface-800/50 border-b border-border flex items-center gap-3">
          {/* Search input */}
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-muted" />
            <input
              type="text"
              placeholder="Поиск товаров..."
              value={searchInput}
              onChange={e => setSearchInput(e.target.value)}
              onKeyDown={handleSearchKeyDown}
              className="input-field w-full pl-9 py-1.5 text-sm"
            />
          </div>
          <button onClick={handleSearch} className="btn-primary py-1.5 text-xs">
            Найти
          </button>

          {/* Right side controls */}
          <div className="ml-auto flex items-center gap-2">
            {/* Export dropdown */}
            <ExportButton
              filters={filters}
              totalItems={data?.total}
            />

            {/* Auto-refresh toggle */}
            <div className="flex items-center gap-1.5 text-xs text-gray-400 pl-2 border-l border-border">
              <button
                onClick={() => setIsAutoRefresh(!isAutoRefresh)}
                className={`p-1.5 rounded transition-colors ${
                  isAutoRefresh
                    ? 'text-positive hover:text-positive/80'
                    : 'text-gray-500 hover:text-gray-300'
                }`}
                title={isAutoRefresh ? 'Авто-обновление вкл' : 'Авто-обновление выкл'}
              >
                {isAutoRefresh ? (
                  <Play className="w-3.5 h-3.5" />
                ) : (
                  <Pause className="w-3.5 h-3.5" />
                )}
              </button>
              <span className="text-gray-500">{secondsAgo}с назад</span>
              <button
                onClick={refresh}
                disabled={isFetching}
                className="p-1.5 rounded text-gray-400 hover:text-gray-200
                           hover:bg-surface-700 transition-colors disabled:opacity-50"
                title="Обновить"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${isFetching ? 'animate-spin' : ''}`} />
              </button>
            </div>
          </div>
        </div>

        {/* Table */}
        {isLoading ? (
          <div className="flex-1 flex items-center justify-center">
            <Loader2 className="w-6 h-6 animate-spin text-accent" />
          </div>
        ) : data ? (
          <PriceListTable
            data={data.items}
            total={data.total}
            page={data.page}
            perPage={data.per_page}
            totalPages={data.total_pages}
            filters={filters}
            onFiltersChange={setFilters}
          />
        ) : null}
      </div>
    </div>
  );
}
