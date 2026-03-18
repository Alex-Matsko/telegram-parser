import { useQuery } from '@tanstack/react-query';
import { getProductDetail } from '../../api/client';
import { useNavigate } from 'react-router-dom';
import { History, Loader2, TrendingUp, TrendingDown, Minus } from 'lucide-react';

interface Props { productId: number; }

function fmt(price: number, currency: string) {
  return currency === 'USD' ? `$${price.toLocaleString('ru-RU')}` : `${price.toLocaleString('ru-RU')} ₽`;
}

export default function PriceDetail({ productId }: Props) {
  const navigate = useNavigate();
  const { data, isLoading } = useQuery({
    queryKey: ['productDetail', productId],
    queryFn: () => getProductDetail(productId),
  });

  if (isLoading) return (
    <div className="flex items-center justify-center py-6">
      <Loader2 className="w-4 h-4 animate-spin text-muted" />
    </div>
  );
  if (!data) return null;

  const { offers } = data;
  const sorted = [...offers].sort((a, b) => a.price - b.price);
  const best = sorted[0];

  return (
    <div className="px-6 py-4 bg-surface-800/60 border-t border-border/30">
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs font-medium text-gray-400">
          {offers.length} {offers.length === 1 ? 'предложение' : offers.length < 5 ? 'предложения' : 'предложений'}
        </span>
        <button
          onClick={() => navigate(`/history/${productId}`)}
          className="flex items-center gap-1.5 text-xs text-accent hover:text-accent-hover transition-colors font-medium"
        >
          <History className="w-3.5 h-3.5" />
          История цен
        </button>
      </div>

      <div className="grid gap-2">
        {sorted.map((offer, idx) => {
          const isWinner = offer.id === best.id;
          const diffFromBest = idx > 0 ? offer.price - best.price : 0;
          const diffPct = idx > 0 ? Math.round((diffFromBest / best.price) * 100) : 0;
          const conf = offer.detected_confidence;
          const confCls = conf > 0.9 ? 'bg-positive' : conf > 0.7 ? 'bg-warning' : 'bg-negative';

          return (
            <div
              key={offer.id}
              className={`flex items-center justify-between rounded-lg px-3 py-2.5 border transition-colors ${
                isWinner
                  ? 'bg-positive/5 border-positive/30'
                  : 'bg-surface-700/40 border-border/20'
              }`}
            >
              {/* Left: supplier + availability */}
              <div className="flex items-center gap-2 min-w-0">
                <div className={`w-2 h-2 rounded-full flex-shrink-0 ${isWinner ? 'bg-positive' : 'bg-surface-500'}`} />
                <div className="min-w-0">
                  <span className={`text-xs font-medium ${ isWinner ? 'text-positive' : 'text-gray-200'}`}>
                    {offer.supplier_name}
                  </span>
                  {offer.availability && (
                    <span className={`ml-2 text-[10px] px-1.5 py-0.5 rounded ${
                      offer.availability === 'в наличии'
                        ? 'bg-positive/10 text-positive'
                        : 'bg-warning/10 text-warning'
                    }`}>{offer.availability}</span>
                  )}
                </div>
              </div>

              {/* Right: price + diff + confidence */}
              <div className="flex items-center gap-4 flex-shrink-0">
                {/* confidence bar */}
                <div className="flex items-center gap-1" title={`Уверенность: ${Math.round(conf * 100)}%`}>
                  <div className="w-14 h-1 bg-surface-600 rounded-full overflow-hidden">
                    <div className={`h-full rounded-full ${confCls}`} style={{ width: `${conf * 100}%` }} />
                  </div>
                  <span className="text-[10px] text-gray-600">{Math.round(conf * 100)}%</span>
                </div>

                {/* diff vs best */}
                {idx > 0 ? (
                  <div className="flex items-center gap-0.5 text-[10px] text-negative w-20 justify-end">
                    <TrendingUp className="w-3 h-3" />
                    <span>+{fmt(diffFromBest, offer.currency)}</span>
                    <span className="text-gray-600">({diffPct}%)</span>
                  </div>
                ) : (
                  <div className="flex items-center gap-0.5 text-[10px] text-positive w-20 justify-end">
                    <TrendingDown className="w-3 h-3" />
                    <span>лучшая</span>
                  </div>
                )}

                {/* price */}
                <span className={`font-mono font-bold w-28 text-right ${
                  isWinner ? 'text-positive text-sm' : 'text-gray-300 text-xs'
                }`}>
                  {fmt(offer.price, offer.currency)}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
