"use client";

import { useEffect, useRef, useState } from "react";
import type { PriceUpdate } from "@/lib/types";

export type StreamStatus =
  | "connecting"
  | "connected"
  | "reconnecting"
  | "disconnected";

/** One charted sample. `time` is a UNIX second, as Lightweight Charts wants. */
export interface PricePoint {
  time: number;
  value: number;
}

export interface PriceStream {
  prices: Record<string, PriceUpdate>;
  history: Record<string, PricePoint[]>;
  status: StreamStatus;
}

/** Events are batched into one render per flush instead of one per ticker. */
const FLUSH_INTERVAL_MS = 120;
const WATCHDOG_INTERVAL_MS = 1000;
/** Four missed server ticks: a green dot over frozen numbers would be a lie. */
const STALE_AFTER_MS = 3000;
/** How long to wait before reopening a stream that closed fatally. */
const RECONNECT_DELAY_MS = 2000;
/** Roughly four minutes of one-second samples. */
const HISTORY_POINTS = 240;

/**
 * Append updates to per-ticker history, keeping one sample per second so the
 * series stays strictly ascending and unique - both required by setData.
 */
export function appendPoints(
  history: Record<string, PricePoint[]>,
  updates: PriceUpdate[],
): Record<string, PricePoint[]> {
  const next = { ...history };

  for (const update of updates) {
    const time = Math.floor(Date.parse(update.timestamp) / 1000);
    const series = next[update.ticker] ?? [];
    const last = series[series.length - 1];

    if (last && last.time === time) {
      next[update.ticker] = [...series.slice(0, -1), { time, value: update.price }];
      continue;
    }

    const grown = [...series, { time, value: update.price }];
    next[update.ticker] = grown.slice(-HISTORY_POINTS);
  }

  return next;
}

/**
 * Live prices from `GET /api/stream/prices`.
 *
 * Sparkline and chart history accumulate here and are session-only by design:
 * a refresh starts them over rather than replaying anything from the server.
 */
export function usePriceStream(url = "/api/stream/prices"): PriceStream {
  const [prices, setPrices] = useState<Record<string, PriceUpdate>>({});
  const [history, setHistory] = useState<Record<string, PricePoint[]>>({});
  const [status, setStatus] = useState<StreamStatus>("connecting");
  const [generation, setGeneration] = useState(0);

  const buffer = useRef<Record<string, PriceUpdate>>({});
  /** Zero while no connection is open, which parks the stall watchdog. */
  const lastEventAt = useRef(0);

  useEffect(() => {
    const source = new EventSource(url);
    let retry: ReturnType<typeof setTimeout> | undefined;

    const reopen = () => setGeneration((count) => count + 1);

    source.onopen = () => {
      // Measure silence from the moment the connection opens, so a stream that
      // opens and then says nothing is caught too.
      lastEventAt.current = Date.now();
      setStatus("connected");
    };

    source.onerror = () => {
      lastEventAt.current = 0;

      if (source.readyState === EventSource.CLOSED) {
        // A fatal close - a non-2xx from a restarting server, say - is never
        // retried by EventSource, so the retry has to be ours.
        setStatus("disconnected");
        retry = setTimeout(reopen, RECONNECT_DELAY_MS);
        return;
      }

      setStatus("reconnecting");
    };

    source.onmessage = (event: MessageEvent<string>) => {
      const update = JSON.parse(event.data) as PriceUpdate;
      buffer.current[update.ticker] = update;
      lastEventAt.current = Date.now();
    };

    const flush = setInterval(() => {
      const batch = Object.values(buffer.current);
      if (batch.length === 0) return;
      buffer.current = {};

      setPrices((previous) => {
        const next = { ...previous };
        for (const update of batch) next[update.ticker] = update;
        return next;
      });
      setHistory((previous) => appendPoints(previous, batch));
      setStatus("connected");
    }, FLUSH_INTERVAL_MS);

    const watchdog = setInterval(() => {
      if (!lastEventAt.current) return;
      if (Date.now() - lastEventAt.current <= STALE_AFTER_MS) return;

      // A stalled stream can sit at readyState OPEN - an intermediary holding
      // the socket open after the server is gone - and EventSource never
      // retries on its own in that state. Force a fresh connection.
      setStatus("disconnected");
      lastEventAt.current = 0;
      source.close();
      reopen();
    }, WATCHDOG_INTERVAL_MS);

    return () => {
      clearTimeout(retry);
      clearInterval(flush);
      clearInterval(watchdog);
      source.close();
    };
  }, [url, generation]);

  return { prices, history, status };
}
