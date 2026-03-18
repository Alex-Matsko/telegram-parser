import { useQuery } from '@tanstack/react-query';
import { getProductDetail } from '../../api/client';
import { useNavigate } from 'react-router-dom';
import { History, Loader2 } from 'lucide-react';

interface Props {
  productId: number;
}

export default function PriceDetail({ productId }: Props) {
  const navigate = useNavigate();
  const { data, isLoading } = useQuery({
    queryKey: ['productDetail', productId],
    queryFn: () => getProductDetail(productId),
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-4">
        <Loader2 className="w-4 h-4 animate-spin text-muted" />
      </div>
    );
  }

  if (!data) return null;

  const { offers } = data;

  const formatPrice = (price: number, currency: string) => {
    if (currency === 'USD') return `$${price.toLocaleString('ru-RU')}`;
    return `${price.toLocaleString('ru-RU')} ₽`;
  };

  const formatTime = (iso: string) => {
    const d = new Date(iso);
    return d.toLocaleString('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <div className="bg-surface-700/30 px-6 py-3">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs text-gray-400">Все предложения ({offers.length})</span>
        <button
          onClick={() => navigate(`/history/${productId}`)}
          className="flex items-center gap-1 text-xs text-accent hover:text-accent-hover transition-colors"
        >
          <History className="w-3 h-3" />
          История цен
        </button>
      </div>
      <table className="w-full text-xs">
        <thead>
          <tr className="text-gray-400 text-left">
            <th className="pb-1.5 font-medium">Поставщик</th>
            <th className="pb-1.5 font-medium text-right">Цена</th>
            <th className="pb-1.5 font-medium text-center">Наличие</th>
            <th className="pb-1.5 font-medium text-center">Уверенность</th>
            <th className="pb-1.5 font-medium text-right">Обновлено</th>
          </tr>
        </thead>
        <tbody>
          {offers.map((offer, idx) => (
            <tr key={offer.id} className={`border-t border-border/50 ${idx === 0 ? 'text-positive' : 'text-gray-300'}`}>
              <td className="py-1.5">{offer.supplier_name}</td>
              <td className="py-1.5 text-right font-mono font-medium">
                {formatPrice(offer.price, offer.currency)}
              </td>
              <td className="py-1.5 text-center">
                <span className={`inline-block px-1.5 py-0.5 rounded text-[10px] ${
                  offer.availability === 'в наличии'
                    ? 'bg-positive/10 text-positive'
                    : 'bg-warning/10 text-warning'
                }`}>
                  {offer.availability || '—'}
                </span>
              </td>
              <td className="py-1.5 text-center">
                <div className="flex items-center justify-center gap-1">
                  <div className="w-12 h-1 bg-surface-600 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full ${
                        offer.detected_confidence > 0.9 ? 'bg-positive' : offer.detected_confidence > 0.7 ? 'bg-warning' : 'bg-negative'
                      }`}
                      style={{ width: `${offer.detected_confidence * 100}%` }}
                    />
                  </div>
                  <span className="text-gray-500">{Math.round(offer.detected_confidence * 100)}%</span>
                </div>
              </td>
              <td className="py-1.5 text-right text-gray-500">{formatTime(offer.updated_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
