import { useEffect, useState } from 'react';
import { getStats } from '../api/client';

interface Stats {
  pending_count: number;
  parsed_today: number;
  unresolved_count: number;
  failed_count: number;
}

const POLL_MS = 5000;

export default function ParseTicker() {
  const [stats, setStats] = useState<Stats | null>(null);

  useEffect(() => {
    const fetch = async () => {
      try {
        const data = await getStats();
        setStats(data);
      } catch {
        // silent
      }
    };
    fetch();
    const id = setInterval(fetch, POLL_MS);
    return () => clearInterval(id);
  }, []);

  if (!stats) return null;

  const isParsing = stats.pending_count > 0;

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
            <span>Парсинг: <strong>{stats.pending_count}</strong> в очереди</span>
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
        Разобрано сегодня: <strong className="text-gray-200">{stats.parsed_today}</strong>
      </span>

      {/* Unresolved */}
      {stats.unresolved_count > 0 && (
        <>
          <span className="text-gray-600">|</span>
          <span className="text-yellow-400">
            На проверке: <strong>{stats.unresolved_count}</strong>
          </span>
        </>
      )}

      {/* Failed */}
      {stats.failed_count > 0 && (
        <>
          <span className="text-gray-600">|</span>
          <span className="text-red-400">
            Ошибки: <strong>{stats.failed_count}</strong>
          </span>
        </>
      )}
    </div>
  );
}
