"use client";

import { useCallback, useEffect, useState } from "react";
import { addTicker, fetchWatchlist, removeTicker } from "@/lib/api";
import type { WatchlistEntry } from "@/lib/types";

export interface WatchlistState {
  entries: WatchlistEntry[];
  error: string | null;
  refresh: () => Promise<void>;
  add: (ticker: string) => Promise<void>;
  remove: (ticker: string) => Promise<void>;
}

/**
 * The watched tickers. Prices in `entries` are only the values at fetch time;
 * the live values come from the stream.
 */
export function useWatchlist(): WatchlistState {
  const [entries, setEntries] = useState<WatchlistEntry[]>([]);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setEntries(await fetchWatchlist());
      setError(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Watchlist unavailable");
    }
  }, []);

  useEffect(() => {
    // refresh only sets state after awaiting the fetch, so this is not the
    // synchronous cascade the rule guards against.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void refresh();
  }, [refresh]);

  const add = useCallback(
    async (ticker: string) => {
      await addTicker(ticker);
      await refresh();
    },
    [refresh],
  );

  const remove = useCallback(
    async (ticker: string) => {
      await removeTicker(ticker);
      await refresh();
    },
    [refresh],
  );

  return { entries, error, refresh, add, remove };
}
