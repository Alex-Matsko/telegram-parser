import { useState } from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { getStats, reparseAll } from '../api/client';
import {
  BarChart3,
  Radio,
  AlertCircle,
  Package,
  Activity,
  MessageSquareWarning,
  ScrollText,
  RefreshCcw,
  Loader2,
} from 'lucide-react';

function StatsBar() {
  const { data: stats } = useQuery({
    queryKey: ['stats'],
    queryFn: getStats,
    refetchInterval: 5000,
  });

  if (!stats) return null;

  const pendingCount    = stats.pending_count    ?? 0;
  const parsedToday     = stats.parsed_today     ?? 0;
  const unresolvedCount = stats.unresolved_count ?? stats.pending_reviews ?? 0;
  const failedCount     = stats.failed_count     ?? stats.failed_parses   ?? 0;
  const isParsing = pendingCount > 0;

  return (
    <div className="bg-surface-800 border-b border-border px-4 py-2 flex items-center gap-5 text-xs overflow-x-auto">
      {/* Products */}
      <div className="flex items-center gap-1.5 text-gray-400 shrink-0">
        <Package className="w-3.5 h-3.5" />
        <span>Товаров:</span>
        <span className="text-gray-200 font-medium">{stats.total_products}</span>
      </div>

      {/* Sources */}
      <div className="flex items-center gap-1.5 text-gray-400 shrink-0">
        <Radio className="w-3.5 h-3.5" />
        <span>Источников:</span>
        <span className="text-gray-200 font-medium">{stats.active_sources}/{stats.total_sources}</span>
      </div>

      {/* Offers */}
      <div className="flex items-center gap-1.5 text-gray-400 shrink-0">
        <Activity className="w-3.5 h-3.5" />
        <span>Предложений:</span>
        <span className="text-gray-200 font-medium">{stats.total_offers}</span>
      </div>

      <div className="w-px h-4 bg-border shrink-0" />

      {/* Parsing progress ticker */}
      <div className="flex items-center gap-1.5 shrink-0 font-mono">
        {isParsing ? (
          <>
            <Loader2 className="w-3.5 h-3.5 text-accent animate-spin" />
            <span className="text-accent">Парсинг:</span>
            <span className="text-accent font-semibold">{pendingCount}</span>
            <span className="text-gray-500">в очереди</span>
          </>
        ) : (
          <>
            <span className="h-2 w-2 rounded-full bg-positive inline-block" />
            <span className="text-gray-500">Очередь пуста</span>
          </>
        )}
      </div>

      {/* Parsed today */}
      <div className="flex items-center gap-1.5 text-gray-400 shrink-0 font-mono">
        <span>Сегодня:</span>
        <span className="text-gray-200 font-medium">{parsedToday}</span>
      </div>

      {/* Unresolved / failed */}
      {(unresolvedCount > 0 || failedCount > 0) && (
        <div className="flex items-center gap-1.5 shrink-0">
          <MessageSquareWarning className="w-3.5 h-3.5 text-yellow-400" />
          {unresolvedCount > 0 && (
            <span className="text-yellow-400">
              Проверка: <strong>{unresolvedCount}</strong>
            </span>
          )}
          {failedCount > 0 && (
            <span className="text-red-400 ml-2">
              Ошибки: <strong>{failedCount}</strong>
            </span>
          )}
        </div>
      )}
    </div>
  );
}

const navItems = [
  { to: '/', label: 'Сводный прайс', icon: BarChart3 },
  { to: '/sources', label: 'Источники', icon: Radio },
  { to: '/unresolved', label: 'Неразобранные', icon: AlertCircle },
  { to: '/logs', label: 'Логи', icon: ScrollText },
];

type ReparseState = 'idle' | 'confirm' | 'loading' | 'done';

function ReparseAllButton() {
  const [state, setState] = useState<ReparseState>('idle');
  const [result, setResult] = useState<{ reset: number } | null>(null);
  const queryClient = useQueryClient();

  const handleClick = async () => {
    if (state === 'idle') { setState('confirm'); return; }
    if (state === 'confirm') {
      setState('loading');
      try {
        const res = await reparseAll();
        setResult({ reset: res.reset });
        setState('done');
        queryClient.invalidateQueries({ queryKey: ['stats'] });
        setTimeout(() => { setState('idle'); setResult(null); }, 4000);
      } catch {
        setState('idle');
      }
    }
  };

  const handleCancel = (e: React.MouseEvent) => { e.stopPropagation(); setState('idle'); };

  if (state === 'done') {
    return (
      <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs text-positive bg-positive/10">
        <RefreshCcw className="w-3.5 h-3.5" />
        <span>Запущено ({result?.reset} сообщ.)</span>
      </div>
    );
  }

  if (state === 'confirm') {
    return (
      <div className="flex items-center gap-1 text-xs">
        <span className="text-warning px-2">Перепарсить ВСЁ?</span>
        <button onClick={handleClick} className="px-2 py-1 rounded bg-warning/20 text-warning hover:bg-warning/30 transition-colors">Да</button>
        <button onClick={handleCancel} className="px-2 py-1 rounded bg-surface-700 text-gray-400 hover:text-gray-200 transition-colors">Отмена</button>
      </div>
    );
  }

  return (
    <button
      onClick={handleClick}
      disabled={state === 'loading'}
      className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm text-gray-400 hover:text-orange-400 hover:bg-orange-500/10 transition-colors disabled:opacity-50"
      title="Перепарсить все собранные сообщения"
    >
      <RefreshCcw className={`w-4 h-4 ${state === 'loading' ? 'animate-spin' : ''}`} />
      {state === 'loading' ? 'Запуск...' : 'Перепарсить всё'}
    </button>
  );
}

export default function Layout() {
  return (
    <div className="min-h-screen flex flex-col bg-surface-900">
      <header className="bg-surface-800 border-b border-border">
        <div className="px-4 flex items-center h-12 gap-6">
          <NavLink to="/" className="flex items-center gap-2 shrink-0">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" aria-label="TG Price Monitor Logo">
              <rect x="2" y="2" width="20" height="20" rx="4" stroke="currentColor" strokeWidth="1.5" className="text-accent" />
              <path d="M7 14l3-6 4 4 3-5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="text-positive" />
              <circle cx="7" cy="14" r="1.5" fill="currentColor" className="text-positive" />
              <circle cx="10" cy="8" r="1.5" fill="currentColor" className="text-accent" />
              <circle cx="14" cy="12" r="1.5" fill="currentColor" className="text-accent" />
              <circle cx="17" cy="7" r="1.5" fill="currentColor" className="text-positive" />
            </svg>
            <span className="text-sm font-semibold text-gray-100 tracking-tight">TG Price Monitor</span>
          </NavLink>

          <nav className="flex items-center gap-1">
            {navItems.map(({ to, label, icon: Icon }) => (
              <NavLink
                key={to}
                to={to}
                end={to === '/'}
                className={({ isActive }) =>
                  `flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm transition-colors ${
                    isActive
                      ? 'bg-accent/10 text-accent font-medium'
                      : 'text-gray-400 hover:text-gray-200 hover:bg-surface-700'
                  }`
                }
              >
                <Icon className="w-4 h-4" />
                {label}
              </NavLink>
            ))}
          </nav>

          <div className="ml-auto" />
          <ReparseAllButton />
        </div>
      </header>

      <StatsBar />

      <main className="flex-1 overflow-hidden">
        <Outlet />
      </main>
    </div>
  );
}
