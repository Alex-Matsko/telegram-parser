import { useState, useEffect, useCallback, useRef } from 'react';

export function useAutoRefresh(refetchFn: () => void, intervalMs: number = 60000) {
  const [isAutoRefresh, setIsAutoRefresh] = useState(true);
  const [lastRefresh, setLastRefresh] = useState<Date>(() => new Date());
  const [secondsAgo, setSecondsAgo] = useState<number>(0);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const tickRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const refresh = useCallback(() => {
    refetchFn();
    setLastRefresh(new Date());
    setSecondsAgo(0);
  }, [refetchFn]);

  useEffect(() => {
    if (isAutoRefresh) {
      intervalRef.current = setInterval(refresh, intervalMs);
    }
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [isAutoRefresh, intervalMs, refresh]);

  useEffect(() => {
    tickRef.current = setInterval(() => {
      setSecondsAgo(Math.floor((Date.now() - lastRefresh.getTime()) / 1000));
    }, 1000);
    return () => {
      if (tickRef.current) clearInterval(tickRef.current);
    };
  }, [lastRefresh]);

  return { isAutoRefresh, setIsAutoRefresh, secondsAgo, refresh };
}
