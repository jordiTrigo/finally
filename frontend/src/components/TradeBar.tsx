"use client";

import { useState } from "react";
import { formatMoney, formatQuantity } from "@/lib/format";
import type { PriceUpdate, TradeReceipt } from "@/lib/types";

interface TradeBarProps {
  selectedTicker: string | null;
  prices: Record<string, PriceUpdate>;
  onTrade: (
    ticker: string,
    side: "buy" | "sell",
    quantity: number,
  ) => Promise<TradeReceipt>;
}

/**
 * Market orders, instant fill, no confirmation dialog. A rejected trade
 * surfaces the backend's `detail` inline next to the bar.
 */
export function TradeBar({ selectedTicker, prices, onTrade }: TradeBarProps) {
  const [ticker, setTicker] = useState(selectedTicker ?? "");
  const [quantity, setQuantity] = useState("1");
  const [error, setError] = useState<string | null>(null);
  const [receipt, setReceipt] = useState<TradeReceipt | null>(null);
  const [pending, setPending] = useState(false);
  const [lastSelected, setLastSelected] = useState(selectedTicker);

  // Follow the selection, but leave the field editable in between. Adjusting
  // during render rather than in an effect avoids a second render pass.
  if (selectedTicker !== lastSelected) {
    setLastSelected(selectedTicker);
    if (selectedTicker) setTicker(selectedTicker);
  }

  const symbol = ticker.trim().toUpperCase();
  const quoted = prices[symbol]?.price ?? null;
  const size = Number(quantity);
  const estimate = quoted !== null && size > 0 ? quoted * size : null;

  async function trade(side: "buy" | "sell") {
    setError(null);
    setReceipt(null);

    if (!symbol) {
      setError("Enter a ticker");
      return;
    }
    if (!Number.isFinite(size) || size <= 0) {
      setError("Quantity must be greater than zero");
      return;
    }

    setPending(true);
    try {
      setReceipt(await onTrade(symbol, side, size));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Trade failed");
    } finally {
      setPending(false);
    }
  }

  return (
    <div
      data-testid="trade-bar"
      className="flex shrink-0 flex-wrap items-center gap-3 border-t border-terminal-border bg-terminal-panel px-4 py-2"
    >
      <span className="text-[10px] uppercase tracking-[0.08em] text-terminal-muted">
        Market order
      </span>

      <input
        data-testid="trade-ticker"
        aria-label="Trade ticker"
        placeholder="TICKER"
        value={ticker}
        onChange={(event) => setTicker(event.target.value.toUpperCase())}
        className="w-28 border border-terminal-border bg-terminal-bg px-2 py-1 uppercase outline-none placeholder:text-terminal-muted/70 focus:border-terminal-blue"
      />

      <input
        data-testid="trade-quantity"
        aria-label="Trade quantity"
        type="number"
        min="0"
        step="any"
        value={quantity}
        onChange={(event) => setQuantity(event.target.value)}
        className="tabular w-24 border border-terminal-border bg-terminal-bg px-2 py-1 text-right outline-none focus:border-terminal-blue"
      />

      <button
        type="button"
        data-testid="trade-buy"
        disabled={pending}
        onClick={() => void trade("buy")}
        className="bg-terminal-up px-4 py-1 text-[11px] font-semibold uppercase tracking-[0.08em] text-white transition-opacity hover:opacity-85 disabled:opacity-50"
      >
        Buy
      </button>

      <button
        type="button"
        data-testid="trade-sell"
        disabled={pending}
        onClick={() => void trade("sell")}
        className="bg-terminal-down px-4 py-1 text-[11px] font-semibold uppercase tracking-[0.08em] text-white transition-opacity hover:opacity-85 disabled:opacity-50"
      >
        Sell
      </button>

      <span data-testid="trade-estimate" className="tabular text-terminal-muted">
        {estimate === null ? "--" : `~ ${formatMoney(estimate)}`}
      </span>

      {error && (
        <span data-testid="trade-error" role="alert" className="text-terminal-down">
          {error}
        </span>
      )}

      {receipt && !error && (
        <span data-testid="trade-receipt" className="text-terminal-up">
          {receipt.side.toUpperCase()} {formatQuantity(receipt.quantity)}{" "}
          {receipt.ticker} @ {formatMoney(receipt.price)}
        </span>
      )}
    </div>
  );
}
