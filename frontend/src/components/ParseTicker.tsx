import { useEffect, useState } from 'react';
import { getStats } from '../api/client';
import type { DashboardStats } from '../types';

const POLL_MS = 5000;

export default function ParseTicker() {
  const [stats, setStats] = useState<DashboardStats | null>(null);

  useEffect(() => {
    const poll = async () => {
      try {
        const data = await getStats();
        setStats(data);
      } catch {
        // silent
      }
    };
    poll();
    const id = setInterval(poll, POLL_MS);
    return () => clearInterval(id);
  }, []);

  if (!stats) return null;

  const pendingCount = stats.pending_count ?? 0;
  const parsedToday = stats.parsed_today ?? 0;
  const unresolvedCount = stats.unresolved_count ?? stats.pending_reviews ?? 0;
  const failedCount = stats.failed_count ?? stats.failed_parses ?? 0;
  const isParsing = pendingCount > 0;

  return (
    <div className="flex items-center gap-3 text-[11px] font-mono select-none">
      {/* Parsing indicator */}
      <span className={`flex items-center gap-1.5 ${
        isParsing ? 'text-accent' : 'text-gray-500'
      }`}>
        {isParsing ? (
          <>
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-accent opacity-75" />
              <span className="relative inline-flex rounded-full h-2 w-2 bg-accent" />
            </span>
            <span>Парсинг: <strong>{pendingCount}</strong> в очереди</span>
          </>
        ) : (
          <>
            <span className="h-2 w-2 rounded-full bg-gray-600 inline-block" />
            <span>Очередь пуста</span>
          </>
        )}
      </span>

      <span className="text-gray-600">|</span>

      {/* Parsed today */}
      <span className="text-gray-400">
        Разобрано сегодня: <strong className="text-gray-200">{parsedToday}</strong>
      </span>

      {/* Unresolved */}
      {unresolvedCount > 0 && (
        <>
          <span className="text-gray-600">|</span>
          <span className="text-yellow-400">
            На проверке: <strong>{unresolvedCount}</strong>
          </span>
        </>
      )}

      {/* Failed */}
      {failedCount > 0 && (
        <>
          <span className="text-gray-600">|</span>
          <span className="text-red-400">
            Ошибки: <strong>{failedCount}</strong>
          </span>
        </>
      )}
    </div>
  );
}
