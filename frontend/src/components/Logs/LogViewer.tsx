import { useState, useEffect, useRef, useCallback } from 'react';
import { getLogs, clearLogs } from '../../api/client';
import type { LogRecord } from '../../api/client';
import {
  RefreshCw, Trash2, Play, Pause, ChevronDown, Filter,
} from 'lucide-react';

const LEVEL_STYLES: Record<string, string> = {
  DEBUG:    'text-gray-400',
  INFO:     'text-blue-400',
  WARNING:  'text-yellow-400',
  ERROR:    'text-red-400',
  CRITICAL: 'text-red-300 font-bold',
};

const LEVEL_BADGE: Record<string, string> = {
  DEBUG:    'bg-gray-700 text-gray-300',
  INFO:     'bg-blue-900/50 text-blue-300',
  WARNING:  'bg-yellow-900/50 text-yellow-300',
  ERROR:    'bg-red-900/50 text-red-300',
  CRITICAL: 'bg-red-800 text-red-100',
};

const LEVELS = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'];
const POLL_INTERVAL_MS = 3000;

export default function LogViewer() {
  const [records, setRecords] = useState<LogRecord[]>([]);
  const [total, setTotal] = useState(0);
  const [minLevel, setMinLevel] = useState('INFO');
  const [loggerFilter, setLoggerFilter] = useState('');
  const [limit, setLimit] = useState(300);
  const [autoScroll, setAutoScroll] = useState(true);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [clearing, setClearing] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const fetchLogs = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getLogs({ level: minLevel, limit, logger_filter: loggerFilter || undefined });
      setRecords(data.records);
      setTotal(data.total);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Ошибка загрузки логов');
    } finally {
      setLoading(false);
    }
  }, [minLevel, limit, loggerFilter]);

  // Initial load & on filter change
  useEffect(() => { fetchLogs(); }, [fetchLogs]);

  // Auto-refresh polling
  useEffect(() => {
    if (!autoRefresh) return;
    const id = setInterval(fetchLogs, POLL_INTERVAL_MS);
    return () => clearInterval(id);
  }, [autoRefresh, fetchLogs]);

  // Auto-scroll to bottom
  useEffect(() => {
    if (autoScroll && bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [records, autoScroll]);

  const handleClear = async () => {
    if (!confirm('Очистить буфер логов?')) return;
    setClearing(true);
    try {
      await clearLogs();
      setRecords([]);
      setTotal(0);
    } finally {
      setClearing(false);
    }
  };

  const formatTime = (iso: string) => {
    const d = new Date(iso);
    return d.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  };

  const errCount = records.filter(r => r.level === 'ERROR' || r.level === 'CRITICAL').length;
  const warnCount = records.filter(r => r.level === 'WARNING').length;

  return (
    <div className="flex flex-col h-full bg-surface-900">
      {/* Header toolbar */}
      <div className="flex flex-wrap items-center gap-3 px-4 py-3 bg-surface-800 border-b border-border">
        <h1 className="text-sm font-semibold text-gray-100 mr-2">Логи</h1>

        {/* Counters */}
        {errCount > 0 && (
          <span className="px-2 py-0.5 rounded text-xs bg-red-900/60 text-red-300">
            {errCount} ошибок
          </span>
        )}
        {warnCount > 0 && (
          <span className="px-2 py-0.5 rounded text-xs bg-yellow-900/50 text-yellow-300">
            {warnCount} предупреждений
          </span>
        )}
        <span className="text-xs text-gray-500 ml-auto">всего: {total}</span>

        {/* Level selector */}
        <div className="flex items-center gap-1.5">
          <Filter className="w-3.5 h-3.5 text-gray-400" />
          <div className="relative">
            <select
              value={minLevel}
              onChange={e => setMinLevel(e.target.value)}
              className="appearance-none bg-surface-700 border border-border text-gray-200 text-xs rounded px-2 py-1 pr-6 cursor-pointer focus:outline-none focus:ring-1 focus:ring-accent"
            >
              {LEVELS.map(l => <option key={l} value={l}>{l}</option>)}
            </select>
            <ChevronDown className="absolute right-1.5 top-1/2 -translate-y-1/2 w-3 h-3 text-gray-400 pointer-events-none" />
          </div>
        </div>

        {/* Logger filter */}
        <input
          type="text"
          placeholder="Фильтр по логгеру (app.collector)"
          value={loggerFilter}
          onChange={e => setLoggerFilter(e.target.value)}
          className="bg-surface-700 border border-border text-gray-200 text-xs rounded px-2 py-1 w-48 focus:outline-none focus:ring-1 focus:ring-accent placeholder-gray-500"
        />

        {/* Limit */}
        <div className="flex items-center gap-1.5">
          <span className="text-xs text-gray-400">кол-во:</span>
          <div className="relative">
            <select
              value={limit}
              onChange={e => setLimit(Number(e.target.value))}
              className="appearance-none bg-surface-700 border border-border text-gray-200 text-xs rounded px-2 py-1 pr-6 cursor-pointer focus:outline-none focus:ring-1 focus:ring-accent"
            >
              {[100, 200, 300, 500, 1000].map(n => <option key={n} value={n}>{n}</option>)}
            </select>
            <ChevronDown className="absolute right-1.5 top-1/2 -translate-y-1/2 w-3 h-3 text-gray-400 pointer-events-none" />
          </div>
        </div>

        {/* Controls */}
        <button
          onClick={() => setAutoRefresh(v => !v)}
          title={autoRefresh ? 'Пауза' : 'Авто-обновление'}
          className={`p-1.5 rounded border text-xs flex items-center gap-1 ${
            autoRefresh
              ? 'border-accent text-accent bg-accent/10'
              : 'border-border text-gray-400 hover:text-gray-200'
          }`}
        >
          {autoRefresh ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
          <span>{autoRefresh ? 'Пауза' : 'Старт'}</span>
        </button>

        <button
          onClick={fetchLogs}
          disabled={loading}
          title="Обновить"
          className="p-1.5 rounded border border-border text-gray-400 hover:text-gray-200 disabled:opacity-40"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
        </button>

        <button
          onClick={() => setAutoScroll(v => !v)}
          title="Авто-прокрутка"
          className={`p-1.5 rounded border text-xs ${
            autoScroll ? 'border-accent text-accent bg-accent/10' : 'border-border text-gray-400'
          }`}
        >
          ↓авто
        </button>

        <button
          onClick={handleClear}
          disabled={clearing}
          title="Очистить"
          className="p-1.5 rounded border border-border text-gray-400 hover:text-red-400 disabled:opacity-40"
        >
          <Trash2 className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* Error banner */}
      {error && (
        <div className="px-4 py-2 bg-red-900/40 border-b border-red-800 text-red-300 text-xs">
          {error}
        </div>
      )}

      {/* Log list */}
      <div
        ref={containerRef}
        className="flex-1 overflow-y-auto font-mono text-xs leading-5 px-4 py-2 space-y-0.5"
      >
        {records.length === 0 && !loading && (
          <div className="text-gray-500 py-8 text-center">Логов нет</div>
        )}
        {records.map((r, i) => (
          <div key={i} className={`flex gap-2 ${LEVEL_STYLES[r.level] ?? 'text-gray-300'} hover:bg-surface-800/60 rounded px-1`}>
            <span className="shrink-0 text-gray-500 w-[68px]">{formatTime(r.ts)}</span>
            <span className={`shrink-0 px-1.5 rounded text-[10px] self-start mt-0.5 ${LEVEL_BADGE[r.level] ?? ''}`}>
              {r.level}
            </span>
            <span className="shrink-0 text-gray-500 max-w-[160px] truncate" title={r.logger}>
              {r.logger}
            </span>
            <span className="break-all whitespace-pre-wrap">{r.message}</span>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Status bar */}
      <div className="px-4 py-1.5 bg-surface-800 border-t border-border flex items-center gap-4 text-[10px] text-gray-500">
        <span>Показано: {records.length}</span>
        <span>Авто-обновление: {autoRefresh ? `каждые ${POLL_INTERVAL_MS / 1000}с` : 'выключено'}</span>
        {loading && <span className="text-accent">Загрузка...</span>}
      </div>
    </div>
  );
}
