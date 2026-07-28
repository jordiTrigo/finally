import { ConnectionDot } from "./ConnectionDot";
import type { StreamStatus } from "@/hooks/usePriceStream";
import { formatMoney, formatPercent, formatSigned, pnlClass } from "@/lib/format";

interface HeaderProps {
  totalValue: number;
  cashBalance: number;
  unrealizedPnl: number;
  status: StreamStatus;
  chatOpen: boolean;
  onToggleChat: () => void;
}

interface StatProps {
  label: string;
  value: string;
  testId: string;
  className?: string;
}

function Stat({ label, value, testId, className = "" }: StatProps) {
  return (
    <div className="flex flex-col leading-tight">
      <span className="text-[10px] uppercase tracking-[0.08em] text-terminal-muted">
        {label}
      </span>
      <span data-testid={testId} className={`tabular text-sm ${className}`}>
        {value}
      </span>
    </div>
  );
}

export function Header({
  totalValue,
  cashBalance,
  unrealizedPnl,
  status,
  chatOpen,
  onToggleChat,
}: HeaderProps) {
  const investedBase = totalValue - unrealizedPnl;
  const pnlPercent = investedBase === 0 ? 0 : (unrealizedPnl / investedBase) * 100;

  return (
    <header
      data-testid="header"
      className="flex shrink-0 items-center gap-6 border-b border-terminal-border bg-terminal-panel px-4 py-2"
    >
      <h1 className="text-[15px] font-semibold uppercase tracking-[0.14em]">
        Fin<span className="text-terminal-accent">Ally</span>
      </h1>

      <Stat
        label="Total value"
        value={formatMoney(totalValue)}
        testId="total-value"
        className="text-terminal-accent"
      />
      <Stat label="Cash" value={formatMoney(cashBalance)} testId="cash-balance" />
      <Stat
        label="Unrealized P&L"
        value={`${formatSigned(unrealizedPnl)} (${formatPercent(pnlPercent)})`}
        testId="total-pnl"
        className={pnlClass(unrealizedPnl)}
      />

      <div className="ml-auto flex items-center gap-4">
        <ConnectionDot status={status} />
        <button
          type="button"
          data-testid="chat-toggle"
          aria-expanded={chatOpen}
          onClick={onToggleChat}
          className="border border-terminal-border px-2.5 py-1 text-[11px] uppercase tracking-[0.08em] text-terminal-muted transition-colors hover:border-terminal-blue hover:text-terminal-blue"
        >
          {chatOpen ? "Hide AI" : "Show AI"}
        </button>
      </div>
    </header>
  );
}
