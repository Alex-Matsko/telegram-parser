import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getProductDetail } from '../../api/client';
import { useNavigate } from 'react-router-dom';
import { History, Loader2, TrendingUp, TrendingDown, ExternalLink, MessageSquare, ChevronDown, ChevronUp } from 'lucide-react';

interface Props { productId: number; }

function fmt(price: number, currency: string) {
  return currency === 'USD' ? `$${price.toLocaleString('ru-RU')}` : `${price.toLocaleString('ru-RU')} ₽`;
}

function fmtDate(iso: string | null): string {
  if (!iso) return '';
  const d = new Date(iso);
  return d.toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit', year: '2-digit' })
    + ' ' + d.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
}

export default function PriceDetail({ productId }: Props) {
  const navigate = useNavigate();
  const [expandedMsg, setExpandedMsg] = useState<number | null>(null);

  const { data, isLoading, error } = useQuery({
    queryKey: ['productDetail', productId],
    queryFn: () => getProductDetail(productId),
  });

  if (isLoading) return (
    <div className="flex items-center justify-center py-6">
      <Loader2 className="w-4 h-4 animate-spin text-muted" />
    </div>
  );
  if (error) return (
    <div className="px-6 py-4 text-xs text-negative">Ошибка загрузки: {String(error)}</div>
  );
  if (!data) return null;

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const offers = [...(data.offers as any[])].sort((a, b) => a.price - b.price);
  const best = offers[0];
  const getId = (o: any) => o.offer_id ?? o.id;

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
        {offers.map((offer, idx) => {
          const offerId = getId(offer);
          const isWinner = offerId === getId(best);
          const diffFromBest = idx > 0 ? offer.price - best.price : 0;
          const diffPct = idx > 0 ? Math.round((diffFromBest / best.price) * 100) : 0;
          const conf = offer.confidence ?? offer.detected_confidence ?? 1;
          const confCls = conf > 0.9 ? 'bg-positive' : conf > 0.7 ? 'bg-warning' : 'bg-negative';
          const msgExpanded = expandedMsg === offerId;
          const hasRawMsg = !!offer.message_text;

          // Direct link to Telegram message
          const msgLink = offer.channel_url && offer.telegram_message_id
            ? offer.channel_url  // already constructed as t.me/c/{id}/{msg_id} by backend
            : null;

          return (
            <div
              key={offerId ?? idx}
              className={`rounded-lg border transition-colors ${
                isWinner ? 'bg-positive/5 border-positive/30' : 'bg-surface-700/40 border-border/20'
              }`}
            >
              {/* Main row */}
              <div className="flex items-center justify-between px-3 py-2.5">
                <div className="flex items-center gap-2 min-w-0">
                  <div className={`w-2 h-2 rounded-full flex-shrink-0 ${isWinner ? 'bg-positive' : 'bg-surface-500'}`} />
                  <div className="min-w-0">
                    <span className={`text-xs font-medium ${isWinner ? 'text-positive' : 'text-gray-200'}`}>
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

                <div className="flex items-center gap-3 flex-shrink-0">
                  <div className="flex items-center gap-1" title={`Уверенность: ${Math.round(conf * 100)}%`}>
                    <div className="w-14 h-1 bg-surface-600 rounded-full overflow-hidden">
                      <div className={`h-full rounded-full ${confCls}`} style={{ width: `${conf * 100}%` }} />
                    </div>
                    <span className="text-[10px] text-gray-600">{Math.round(conf * 100)}%</span>
                  </div>

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

                  <span className={`font-mono font-bold w-28 text-right ${
                    isWinner ? 'text-positive text-sm' : 'text-gray-300 text-xs'
                  }`}>
                    {fmt(offer.price, offer.currency)}
                  </span>
                </div>
              </div>

              {/* Source row: channel + date + raw_line + toggle for full message */}
              <div className="px-3 pb-2.5 pt-0 border-t border-border/10">
                <div className="flex items-center justify-between gap-2 pt-1.5">
                  <div className="flex items-center gap-2 min-w-0">
                    <MessageSquare className="w-3 h-3 text-gray-600 flex-shrink-0" />
                    {/* Channel link */}
                    {offer.source_name && (
                      msgLink ? (
                        <a
                          href={msgLink}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="flex items-center gap-1 text-[10px] text-accent hover:text-accent-hover transition-colors font-medium"
                        >
                          <ExternalLink className="w-2.5 h-2.5" />
                          {offer.source_name}
                        </a>
                      ) : (
                        <span className="text-[10px] text-gray-500">{offer.source_name}</span>
                      )
                    )}
                    {offer.message_date && (
                      <span className="text-[10px] text-gray-600">{fmtDate(offer.message_date)}</span>
                    )}
                    {/* Verbatim parsed line */}
                    {offer.raw_line && (
                      <span className="text-[10px] font-mono text-gray-500 truncate max-w-[200px]" title={offer.raw_line}>
                        {offer.raw_line}
                      </span>
                    )}
                  </div>

                  {/* Toggle full message */}
                  {hasRawMsg && (
                    <button
                      onClick={() => setExpandedMsg(msgExpanded ? null : offerId)}
                      className="flex items-center gap-1 text-[10px] text-gray-500 hover:text-gray-300 transition-colors flex-shrink-0"
                    >
                      {msgExpanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                      {msgExpanded ? 'Скрыть' : 'Сырое сообщение'}
                    </button>
                  )}
                </div>

                {/* Full raw message text */}
                {msgExpanded && offer.message_text && (
                  <div className="mt-2 p-2 rounded bg-surface-900/60 border border-border/20">
                    <pre className="text-[11px] font-mono text-gray-300 whitespace-pre-wrap break-words leading-relaxed">
                      {offer.message_text}
                    </pre>
                    {msgLink && (
                      <a
                        href={msgLink}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="mt-2 flex items-center gap-1 text-[10px] text-accent hover:text-accent-hover transition-colors"
                      >
                        <ExternalLink className="w-3 h-3" />
                        Открыть в Telegram
                      </a>
                    )}
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
