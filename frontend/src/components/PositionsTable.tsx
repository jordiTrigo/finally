"use client";

import { PriceCell } from "./PriceCell";
import {
  formatMoney,
  formatPercent,
  formatQuantity,
  formatSigned,
  pnlClass,
} from "@/lib/format";
import type { Position } from "@/lib/types";

interface PositionsTableProps {
  positions: Position[];
  onSelect: (ticker: string) => void;
}

export function PositionsTable({ positions, onSelect }: PositionsTableProps) {
  if (positions.length === 0) {
    return (
      <p data-testid="positions-empty" className="px-3 py-6 text-terminal-muted">
        No open positions. Buy something from the trade bar below.
      </p>
    );
  }

  return (
    <div className="h-full overflow-auto">
      <table data-testid="positions-table" className="w-full border-collapse">
        <thead className="sticky top-0 z-10 bg-terminal-panel">
          <tr className="text-[10px] uppercase tracking-[0.08em] text-terminal-muted">
            <th className="px-3 py-1.5 text-left font-medium">Sym</th>
            <th className="px-3 py-1.5 text-right font-medium">Qty</th>
            <th className="px-3 py-1.5 text-right font-medium">Avg cost</th>
            <th className="px-3 py-1.5 text-right font-medium">Last</th>
            <th className="px-3 py-1.5 text-right font-medium">Value</th>
            <th className="px-3 py-1.5 text-right font-medium">Unreal. P&L</th>
            <th className="px-3 py-1.5 text-right font-medium">%</th>
          </tr>
        </thead>
        <tbody>
          {positions.map((position) => (
            <tr
              key={position.ticker}
              data-testid={`position-row-${position.ticker}`}
              onClick={() => onSelect(position.ticker)}
              className="cursor-pointer border-t border-terminal-border/50 hover:bg-terminal-raised"
            >
              <td className="px-3 py-1 font-semibold tracking-[0.04em]">
                {position.ticker}
              </td>
              <td
                data-testid={`position-quantity-${position.ticker}`}
                className="tabular px-3 py-1 text-right"
              >
                {formatQuantity(position.quantity)}
              </td>
              <td className="tabular px-3 py-1 text-right text-terminal-muted">
                {formatMoney(position.avg_cost)}
              </td>
              <td className="px-3 py-1 text-right">
                <PriceCell
                  price={position.current_price}
                  testId={`position-price-${position.ticker}`}
                />
              </td>
              <td className="tabular px-3 py-1 text-right">
                {formatMoney(position.market_value)}
              </td>
              <td
                data-testid={`position-pnl-${position.ticker}`}
                className={`tabular px-3 py-1 text-right ${pnlClass(position.unrealized_pnl)}`}
              >
                {formatSigned(position.unrealized_pnl)}
              </td>
              <td
                className={`tabular px-3 py-1 text-right ${pnlClass(position.pnl_percent)}`}
              >
                {formatPercent(position.pnl_percent)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
