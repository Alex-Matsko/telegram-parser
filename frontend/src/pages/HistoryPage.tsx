import { useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { getPriceHistoryChart, getPriceChangeEvents, getProductDetail } from '../api/client';
import PriceChart from '../components/History/PriceChart';
import PriceHistoryTable from '../components/History/PriceHistory';
import { ChevronRight, Loader2 } from 'lucide-react';

const periodOptions = [
  { value: 1, label: '1 день' },
  { value: 3, label: '3 дня' },
  { value: 7, label: '7 дней' },
];

export default function HistoryPage() {
  const { productId } = useParams<{ productId: string }>();
  const id = Number(productId);
  const [days, setDays] = useState(3);

  const { data: product } = useQuery({
    queryKey: ['productDetail', id],
    queryFn: () => getProductDetail(id),
    enabled: !!id,
  });

  const { data: chartData, isLoading: chartLoading } = useQuery({
    queryKey: ['priceHistoryChart', id, days],
    queryFn: () => getPriceHistoryChart(id, days),
    enabled: !!id,
  });

  const { data: events, isLoading: eventsLoading } = useQuery({
    queryKey: ['priceChangeEvents', id, days],
    queryFn: () => getPriceChangeEvents(id, days),
    enabled: !!id,
  });

  const currency = 'RUB';

  return (
    <div className="p-4 max-w-6xl mx-auto space-y-4">
      {/* Breadcrumb */}
      <nav className="flex items-center gap-1.5 text-xs text-gray-400">
        <Link to="/" className="hover:text-gray-200 transition-colors">
          Сводный прайс
        </Link>
        <ChevronRight className="w-3 h-3" />
        <span className="text-gray-200">
          {product ? product.normalized_name : `Товар #${id}`}
        </span>
      </nav>

      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-gray-100">
          История цен{product ? `: ${product.model}` : ''}
        </h1>

        {/* Period Selector */}
        <div className="flex items-center gap-1 bg-surface-800 rounded-lg p-0.5 border border-border">
          {periodOptions.map(opt => (
            <button
              key={opt.value}
              onClick={() => setDays(opt.value)}
              className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${
                days === opt.value
                  ? 'bg-accent text-white'
                  : 'text-gray-400 hover:text-gray-200'
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {/* Product Info */}
      {product && (
        <div className="card p-3 flex items-center gap-4 text-sm">
          <div>
            <span className="text-gray-400">Модель:</span>{' '}
            <span className="text-gray-200 font-medium">{product.model}</span>
          </div>
          {product.memory && (
            <div>
              <span className="text-gray-400">Память:</span>{' '}
              <span className="text-gray-200">{product.memory}</span>
            </div>
          )}
          {product.color && (
            <div>
              <span className="text-gray-400">Цвет:</span>{' '}
              <span className="text-gray-200">{product.color}</span>
            </div>
          )}
          <div>
            <span className="text-gray-400">Состояние:</span>{' '}
            <span className="text-gray-200">
              {product.condition === 'new' ? 'Новый' : product.condition === 'used' ? 'Б/У' : 'Восст.'}
            </span>
          </div>
        </div>
      )}

      {/* Chart */}
      {chartLoading ? (
        <div className="card flex items-center justify-center py-16">
          <Loader2 className="w-6 h-6 animate-spin text-accent" />
        </div>
      ) : chartData ? (
        <PriceChart data={chartData} currency={currency} />
      ) : null}

      {/* Events Table */}
      {eventsLoading ? (
        <div className="card flex items-center justify-center py-16">
          <Loader2 className="w-6 h-6 animate-spin text-accent" />
        </div>
      ) : events ? (
        <PriceHistoryTable events={events} currency={currency} />
      ) : null}
    </div>
  );
}
