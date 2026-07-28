import type { StreamStatus } from "@/hooks/usePriceStream";

const APPEARANCE: Record<StreamStatus, { color: string; label: string }> = {
  connecting: { color: "bg-terminal-muted", label: "connecting" },
  connected: { color: "bg-terminal-up shadow-[0_0_6px_rgba(38,166,91,0.8)]", label: "live" },
  reconnecting: { color: "bg-terminal-accent", label: "reconnecting" },
  disconnected: { color: "bg-terminal-down", label: "disconnected" },
};

/** Green live, yellow reconnecting, red disconnected. */
export function ConnectionDot({ status }: { status: StreamStatus }) {
  const { color, label } = APPEARANCE[status];

  return (
    <div className="flex items-center gap-2">
      <span
        data-testid="connection-dot"
        data-status={status}
        title={label}
        className={`inline-block h-2 w-2 rounded-full transition-colors duration-200 ${color}`}
      />
      <span
        data-testid="connection-label"
        className="text-[11px] uppercase tracking-[0.08em] text-terminal-muted"
      >
        {label}
      </span>
    </div>
  );
}
