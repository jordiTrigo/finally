"use client";

import { useCallback, useEffect, useState } from "react";
import { executeTrade, fetchHistory, fetchPortfolio } from "@/lib/api";
import type { Portfolio, Snapshot, TradeReceipt } from "@/lib/types";

/** Snapshots are written server-side every 30s; polling matches that cadence. */
const HISTORY_POLL_MS = 30_000;

export const EMPTY_PORTFOLIO: Portfolio = {
  cash_balance: 0,
  positions: [],
  positions_value: 0,
  total_value: 0,
  total_unrealized_pnl: 0,
};

export interface PortfolioState {
  portfolio: Portfolio;
  history: Snapshot[];
  error: string | null;
  refresh: () => Promise<void>;
  trade: (
    ticker: string,
    side: "buy" | "sell",
    quantity: number,
  ) => Promise<TradeReceipt>;
}

/**
 * Portfolio state and the trade action.
 *
 * The portfolio is refetched around trades rather than polled: between fetches
 * the live stream re-prices it client-side, so a poll would buy nothing.
 */
export function usePortfolio(): PortfolioState {
  const [portfolio, setPortfolio] = useState<Portfolio>(EMPTY_PORTFOLIO);
  const [history, setHistory] = useState<Snapshot[]>([]);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [next, snapshots] = await Promise.all([fetchPortfolio(), fetchHistory()]);
      setPortfolio(next);
      setHistory(snapshots);
      setError(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Portfolio unavailable");
    }
  }, []);

  useEffect(() => {
    // refresh only sets state after awaiting the fetch, so this is not the
    // synchronous cascade the rule guards against.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void refresh();
    const timer = setInterval(() => void refresh(), HISTORY_POLL_MS);
    return () => clearInterval(timer);
  }, [refresh]);

  const trade = useCallback(
    async (ticker: string, side: "buy" | "sell", quantity: number) => {
      const receipt = await executeTrade(ticker, side, quantity);
      await refresh();
      return receipt;
    },
    [refresh],
  );

  return { portfolio, history, error, refresh, trade };
}
