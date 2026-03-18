import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getSourceStats, triggerSource, resetSourceErrors } from '../../api/client';
import type { Source } from '../../types';
import {
  X, RefreshCw, Play, AlertTriangle, XCircle,
  BarChart2, Clock, Tag, RotateCcw, CheckCircle2,
} from 'lucide-react';

interface Props {
  source: Source;
  onClose: () => void;
}

const STATUS_STYLE: Record<string, string> = {
  parsed:       'bg-positive/10 text-positive',
  failed:       'bg-negative/10 text-negative',
  pending:      'bg-accent/10 text-accent',
  needs_review: 'bg-warning/10 text-warning',
};
const STATUS_LABEL: Record<string, string> = {
  parsed: 'Parsed', failed: 'Ошибка', pending: 'Очередь', needs_review: 'Проверка',
};

function StatCard({ label, value, accent }: { label: string; value: string | number; accent?: boolean }) {
  return (
    <div className="bg-surface-700 rounded-lg px-3 py-2.5">
      <div className="text-[10px] text-gray-500 mb-0.5">{label}</div>
      <div className={`text-sm font-semibold ${accent ? 'text-negative' : 'text-gray-100'}`}>{value}</div>
    </div>
  );
}

export default function SourceStatsDrawer({ source, onClose }: Props) {
  const queryClient = useQueryClient();
  const [triggerStatus, setTriggerStatus] = useState<'idle' | 'queued' | 'error'>('idle');

  const { data: stats, isLoading, refetch, isFetching } = useQuery({
    queryKey: ['sourceStats', source.id],
    queryFn: () => getSourceStats(source.id),
    staleTime: 30_000,
  });

  const triggerMutation = useMutation({
    mutationFn: () => triggerSource(source.id),
    onSuccess: () => {
      setTriggerStatus('queued');
      setTimeout(() => { setTriggerStatus('idle'); refetch(); }, 4000);
    },
    onError: () => setTriggerStatus('error'),
  });

  const resetMutation = useMutation({
    mutationFn: () => resetSourceErrors(source.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sources'] });
      refetch();
    },
  });

  const fmt = (iso: string | null) => {
    if (!iso) return '—';
    return new Date(iso).toLocaleString('ru-RU', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });
  };
  const fmtMsg = (iso: string) =>
    new Date(iso).toLocaleString('ru-RU', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });

  const pct = stats ? Math.round(stats.parse_success_rate * 100) : 0;

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={onClose} />
      <div className="relative w-full max-w-md bg-surface-900 border-l border-border flex flex-col h-full shadow-2xl">

        {/* Header */}
        <div className="flex items-start justify-between px-4 py-3 border-b border-border flex-shrink-0">
          <div className="min-w-0 pr-2">
            <h2 className="text-sm font-semibold text-gray-100 truncate">{source.source_name}</h2>
            <p className="text-[10px] text-gray-500 mt-0.5">
              ID: {source.telegram_id} · {source.type} · интервал {source.poll_interval_minutes} мин
            </p>
          </div>
          <div className="flex items-center gap-1 flex-shrink-0">
            <button
              onClick={() => refetch()}
              disabled={isFetching}
              className="p-1.5 rounded text-gray-500 hover:text-accent hover:bg-surface-700 transition-colors"
              title="Обновить"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isFetching ? 'animate-spin' : ''}`} />
            </button>
            <button onClick={onClose} className="p-1.5 rounded text-gray-500 hover:text-gray-200 hover:bg-surface-700 transition-colors">
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Action buttons */}
        <div className="flex gap-2 px-4 py-2.5 border-b border-border/50 flex-shrink-0">
          <button
            onClick={() => { setTriggerStatus('idle'); triggerMutation.mutate(); }}
            disabled={triggerMutation.isPending || triggerStatus === 'queued'}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg bg-accent/10 text-accent hover:bg-accent/20 disabled:opacity-50 disabled:cursor-not-allowed transition-colors font-medium"
          >
            {triggerStatus === 'queued'
              ? <><CheckCircle2 className="w-3.5 h-3.5" /> Запущено</>  
              : <><Play className="w-3.5 h-3.5" /> Запустить сбор</>}
          </button>
          {(stats?.error_count ?? 0) > 0 && (
            <button
              onClick={() => resetMutation.mutate()}
              disabled={resetMutation.isPending}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg bg-surface-600 text-gray-400 hover:text-gray-200 hover:bg-surface-500 disabled:opacity-50 transition-colors"
            >
              <RotateCcw className="w-3.5 h-3.5" /> Сбросить ошибки
            </button>
          )}
        </div>

        {isLoading ? (
          <div className="flex-1 flex items-center justify-center">
            <RefreshCw className="w-5 h-5 animate-spin text-accent" />
          </div>
        ) : stats ? (
          <div className="flex-1 overflow-y-auto space-y-4 pb-6">

            {/* Error banner */}
            {stats.last_error && (
              <div className="mx-4 mt-3 p-3 bg-negative/10 border border-negative/20 rounded-lg">
                <div className="flex items-start gap-2">
                  <AlertTriangle className="w-3.5 h-3.5 text-negative flex-shrink-0 mt-0.5" />
                  <div className="min-w-0">
                    <p className="text-[11px] font-medium text-negative mb-0.5">Последняя ошибка ({stats.error_count}×)</p>
                    <p className="text-[10px] text-negative/80 break-all">{stats.last_error}</p>
                  </div>
                </div>
              </div>
            )}

            {/* Meta info */}
            <div className="px-4 pt-3 flex flex-wrap gap-x-3 gap-y-1 text-[10px] text-gray-500">
              <span>Последнее чтение: <span className="text-gray-300">{fmt(stats.last_read_at)}</span></span>
              <span>Стратегия: <span className="text-gray-300">{stats.parsing_strategy}</span></span>
              {stats.supplier_id && <span>Поставщик ID: <span className="text-gray-300">{stats.supplier_id}</span></span>}
            </div>

            {/* Message stats */}
            <div className="px-4">
              <div className="flex items-center gap-1.5 mb-2">
                <BarChart2 className="w-3.5 h-3.5 text-gray-500" />
                <span className="text-xs font-medium text-gray-400">Сообщения</span>
              </div>
              <div className="grid grid-cols-3 gap-2">
                <StatCard label="Всего" value={stats.messages_total} />
                <StatCard label="За 24ч" value={stats.messages_24h} />
                <StatCard label="В очереди" value={stats.messages_pending} />
                <StatCard label="Успешно" value={stats.messages_parsed} />
                <StatCard label="Ошибки" value={stats.messages_failed} accent={stats.messages_failed > 0} />
                <StatCard label="Проверка" value={stats.messages_needs_review} accent={stats.messages_needs_review > 0} />
              </div>
              {/* Parse rate bar */}
              <div className="mt-3">
                <div className="flex justify-between text-[10px] text-gray-500 mb-1">
                  <span>Успешность парсинга</span>
                  <span className={pct >= 70 ? 'text-positive' : pct >= 40 ? 'text-warning' : 'text-negative'}>{pct}%</span>
                </div>
                <div className="h-1.5 bg-surface-600 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all ${
                      pct >= 70 ? 'bg-positive' : pct >= 40 ? 'bg-warning' : 'bg-negative'
                    }`}
                    style={{ width: `${pct}%` }}
                  />
                </div>
              </div>
            </div>

            {/* Offer stats */}
            {stats.supplier_id && (
              <div className="px-4">
                <div className="flex items-center gap-1.5 mb-2">
                  <Tag className="w-3.5 h-3.5 text-gray-500" />
                  <span className="text-xs font-medium text-gray-400">Офферы</span>
                </div>
                <div className="grid grid-cols-3 gap-2">
                  <StatCard label="Всего" value={stats.offers_total} />
                  <StatCard label="Актуальные" value={stats.offers_current} />
                  <StatCard label="Товаров" value={stats.products_covered} />
                </div>
              </div>
            )}

            {/* Recent messages log */}
            <div className="px-4">
              <div className="flex items-center gap-1.5 mb-2">
                <Clock className="w-3.5 h-3.5 text-gray-500" />
                <span className="text-xs font-medium text-gray-400">Лог сообщений</span>
                <span className="ml-auto text-[10px] text-gray-600">последние {stats.recent_messages.length}</span>
              </div>
              {stats.recent_messages.length === 0 ? (
                <p className="text-[11px] text-gray-600 py-2">Нет сообщений</p>
              ) : (
                <div className="space-y-1.5">
                  {stats.recent_messages.map(msg => (
                    <div key={msg.id} className="bg-surface-700 rounded-lg p-2.5 border border-border/20">
                      <div className="flex items-center justify-between mb-1.5">
                        <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${STATUS_STYLE[msg.parse_status] ?? 'bg-gray-600/20 text-gray-400'}`}>
                          {STATUS_LABEL[msg.parse_status] ?? msg.parse_status}
                        </span>
                        <span className="text-[10px] text-gray-600">{fmtMsg(msg.message_date)}</span>
                      </div>
                      <p className="text-[11px] text-gray-300 whitespace-pre-wrap break-words leading-relaxed">
                        {msg.message_text}
                      </p>
                      {msg.parse_error && (
                        <p className="mt-1.5 text-[10px] text-negative/80 flex items-start gap-1">
                          <XCircle className="w-3 h-3 flex-shrink-0 mt-0.5" />
                          <span>{msg.parse_error}</span>
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>

          </div>
        ) : null}
      </div>
    </div>
  );
}
