"use client";

import { useCallback, useMemo, useState } from "react";
import { ChatPanel } from "./ChatPanel";
import { Header } from "./Header";
import { Panel } from "./Panel";
import { PortfolioHeatmap } from "./PortfolioHeatmap";
import { PositionsTable } from "./PositionsTable";
import { TimeSeriesChart } from "./TimeSeriesChart";
import { TradeBar } from "./TradeBar";
import { Watchlist } from "./Watchlist";
import { useChat } from "@/hooks/useChat";
import { usePortfolio } from "@/hooks/usePortfolio";
import { usePriceStream, type PricePoint } from "@/hooks/usePriceStream";
import { useWatchlist } from "@/hooks/useWatchlist";
import { formatMoney } from "@/lib/format";
import { pnlSeries, repricePortfolio } from "@/lib/portfolio";

const NO_POINTS: PricePoint[] = [];

/** The whole workstation. Browser-only: it owns the SSE stream and the canvases. */
export function Terminal() {
  const { prices, history, status } = usePriceStream();
  const watchlist = useWatchlist();
  const portfolioState = usePortfolio();
  const [picked, setPicked] = useState<string | null>(null);
  const [chatOpen, setChatOpen] = useState(true);

  /** Falling back to the first watched ticker keeps the main chart from ever
      being blank, without an effect that syncs state to state. */
  const selected = picked ?? watchlist.entries[0]?.ticker ?? null;

  const { refresh: refreshPortfolio } = portfolioState;
  const { refresh: refreshWatchlist } = watchlist;
  const refreshAll = useCallback(() => {
    void refreshPortfolio();
    void refreshWatchlist();
  }, [refreshPortfolio, refreshWatchlist]);

  const chat = useChat(refreshAll);

  const portfolio = useMemo(
    () => repricePortfolio(portfolioState.portfolio, prices),
    [portfolioState.portfolio, prices],
  );

  const pnlPoints = useMemo(
    () => pnlSeries(portfolioState.history, portfolio.total_value),
    [portfolioState.history, portfolio.total_value],
  );

  const loadError = portfolioState.error ?? watchlist.error;
  const selectedPoints = selected ? (history[selected] ?? NO_POINTS) : NO_POINTS;

  return (
    <div className="flex h-full flex-col bg-terminal-bg text-terminal-text">
      <Header
        totalValue={portfolio.total_value}
        cashBalance={portfolio.cash_balance}
        unrealizedPnl={portfolio.total_unrealized_pnl}
        status={status}
        chatOpen={chatOpen}
        onToggleChat={() => setChatOpen((open) => !open)}
      />

      {loadError && (
        <p
          data-testid="load-error"
          role="alert"
          className="shrink-0 border-b border-terminal-down/50 bg-terminal-down/10 px-4 py-1 text-terminal-down"
        >
          {loadError}
        </p>
      )}

      <div className="flex min-h-0 flex-1">
        <main className="grid min-h-0 flex-1 grid-cols-[330px_minmax(0,1fr)_360px] grid-rows-[minmax(0,1.35fr)_minmax(0,1fr)] gap-px bg-terminal-border">
          {/* Auto-placement fills the rest of the grid around this spanning cell. */}
          <Watchlist
            className="row-span-2"
            entries={watchlist.entries}
            prices={prices}
            history={history}
            selected={selected}
            onSelect={setPicked}
            onAdd={watchlist.add}
            onRemove={watchlist.remove}
          />

          <Panel
            title={selected ? `${selected} - price` : "Price"}
            testId="price-chart"
            actions={
              <span className="tabular text-terminal-accent">
                {selected && prices[selected]
                  ? formatMoney(prices[selected].price)
                  : "--"}
              </span>
            }
          >
            <TimeSeriesChart
              points={selectedPoints}
              resetKey={selected ?? "none"}
              color="#209dd7"
              variant="area"
              emptyMessage={
                selected ? `Accumulating ${selected} ticks` : "Select a ticker"
              }
            />
          </Panel>

          <Panel title="Portfolio heatmap" testId="heatmap-panel">
            <PortfolioHeatmap positions={portfolio.positions} />
          </Panel>

          <Panel
            title="Positions"
            testId="positions-panel"
            actions={
              <span className="tabular text-terminal-muted">
                {formatMoney(portfolio.positions_value)} invested
              </span>
            }
            bodyClassName="overflow-hidden"
          >
            <PositionsTable positions={portfolio.positions} onSelect={setPicked} />
          </Panel>

          <Panel title="Portfolio value" testId="pnl-chart">
            <TimeSeriesChart
              points={pnlPoints}
              resetKey="pnl"
              color="#ecad0a"
              variant="line"
              emptyMessage="Waiting for the first snapshot"
            />
          </Panel>
        </main>

        {chatOpen && (
          <ChatPanel
            messages={chat.messages}
            pending={chat.pending}
            error={chat.error}
            onSend={chat.send}
          />
        )}
      </div>

      <TradeBar
        selectedTicker={selected}
        prices={prices}
        onTrade={portfolioState.trade}
      />
    </div>
  );
}
