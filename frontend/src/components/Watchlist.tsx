"use client";

import { useState } from "react";
import { Panel } from "./Panel";
import { PriceCell } from "./PriceCell";
import { Sparkline } from "./Sparkline";
import type { PricePoint } from "@/hooks/usePriceStream";
import { formatPercent, pnlClass } from "@/lib/format";
import type { PriceUpdate, WatchlistEntry } from "@/lib/types";

/** Trailing samples drawn per row. */
const SPARK_POINTS = 48;

interface WatchlistProps {
  entries: WatchlistEntry[];
  prices: Record<string, PriceUpdate>;
  history: Record<string, PricePoint[]>;
  selected: string | null;
  onSelect: (ticker: string) => void;
  onAdd: (ticker: string) => Promise<void>;
  onRemove: (ticker: string) => Promise<void>;
  className?: string;
}

/** Change since page load - the only baseline the session actually has. */
function sessionChangePercent(points: PricePoint[] | undefined): number | null {
  if (!points || points.length < 2) return null;
  const first = points[0].value;
  if (first === 0) return null;
  return ((points[points.length - 1].value - first) / first) * 100;
}

export function Watchlist({
  entries,
  prices,
  history,
  selected,
  onSelect,
  onAdd,
  onRemove,
  className = "",
}: WatchlistProps) {
  const [draft, setDraft] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    const ticker = draft.trim().toUpperCase();
    if (!ticker) return;

    setError(null);
    try {
      await onAdd(ticker);
      setDraft("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not add ticker");
    }
  }

  return (
    <Panel
      title="Watchlist"
      testId="watchlist"
      className={className}
      bodyClassName="flex flex-col"
    >
      <div className="min-h-0 flex-1 overflow-y-auto">
        <table className="w-full border-collapse">
          <thead className="sticky top-0 z-10 bg-terminal-panel">
            <tr className="text-[10px] uppercase tracking-[0.08em] text-terminal-muted">
              <th className="px-2 py-1.5 text-left font-medium">Sym</th>
              <th className="px-2 py-1.5 text-right font-medium">Last</th>
              <th className="px-2 py-1.5 text-right font-medium">Chg%</th>
              <th className="px-2 py-1.5 text-right font-medium">Trend</th>
              <th className="w-5 px-1 py-1.5" />
            </tr>
          </thead>
          <tbody>
            {entries.map((entry) => {
              const points = history[entry.ticker];
              const change = sessionChangePercent(points);
              const price = prices[entry.ticker]?.price ?? entry.price;
              const isSelected = entry.ticker === selected;

              return (
                <tr
                  key={entry.ticker}
                  data-testid={`watchlist-row-${entry.ticker}`}
                  data-selected={isSelected}
                  onClick={() => onSelect(entry.ticker)}
                  className={`cursor-pointer border-t border-terminal-border/50 hover:bg-terminal-raised ${
                    isSelected ? "bg-terminal-raised" : ""
                  }`}
                >
                  <td className="px-2 py-1 text-left font-semibold tracking-[0.04em]">
                    <span
                      className={
                        isSelected ? "text-terminal-accent" : "text-terminal-text"
                      }
                    >
                      {entry.ticker}
                    </span>
                  </td>
                  <td className="px-2 py-1 text-right">
                    <PriceCell
                      price={price}
                      testId={`watchlist-price-${entry.ticker}`}
                    />
                  </td>
                  <td
                    data-testid={`watchlist-change-${entry.ticker}`}
                    className={`tabular px-2 py-1 text-right ${
                      change === null ? "text-terminal-muted" : pnlClass(change)
                    }`}
                  >
                    {change === null ? "--" : formatPercent(change)}
                  </td>
                  <td className="px-2 py-1">
                    <div className="flex justify-end">
                      <Sparkline
                        values={(points ?? []).slice(-SPARK_POINTS).map((p) => p.value)}
                        width={72}
                        testId={`sparkline-${entry.ticker}`}
                      />
                    </div>
                  </td>
                  <td className="px-1 py-1 text-right">
                    <button
                      type="button"
                      aria-label={`Remove ${entry.ticker}`}
                      data-testid={`watchlist-remove-${entry.ticker}`}
                      onClick={(event) => {
                        event.stopPropagation();
                        void onRemove(entry.ticker);
                      }}
                      className="px-1 text-terminal-muted transition-colors hover:text-terminal-down"
                    >
                      &times;
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>

        {entries.length === 0 && (
          <p data-testid="watchlist-empty" className="px-3 py-6 text-terminal-muted">
            Watchlist is empty. Add a ticker below.
          </p>
        )}
      </div>

      <form
        onSubmit={submit}
        className="flex shrink-0 items-center gap-2 border-t border-terminal-border px-3 py-2"
      >
        <input
          data-testid="watchlist-add-input"
          aria-label="Add ticker"
          placeholder="ADD TICKER"
          value={draft}
          onChange={(event) => {
            setDraft(event.target.value.toUpperCase());
            setError(null);
          }}
          className="min-w-0 flex-1 border border-terminal-border bg-terminal-bg px-2 py-1 uppercase outline-none placeholder:text-terminal-muted/70 focus:border-terminal-blue"
        />
        <button
          type="submit"
          data-testid="watchlist-add-button"
          className="bg-terminal-purple px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.08em] text-white transition-opacity hover:opacity-85"
        >
          Add
        </button>
      </form>

      {error && (
        <p
          data-testid="watchlist-error"
          role="alert"
          className="shrink-0 border-t border-terminal-border px-3 py-1.5 text-terminal-down"
        >
          {error}
        </p>
      )}
    </Panel>
  );
}
