interface PanelProps {
  title: string;
  children: React.ReactNode;
  actions?: React.ReactNode;
  className?: string;
  bodyClassName?: string;
  testId?: string;
}

/** A bordered terminal pane with an uppercase caption bar. */
export function Panel({
  title,
  children,
  actions,
  className = "",
  bodyClassName = "",
  testId,
}: PanelProps) {
  return (
    <section
      data-testid={testId}
      className={`flex min-h-0 min-w-0 flex-col border border-terminal-border bg-terminal-panel ${className}`}
    >
      <header className="flex shrink-0 items-center gap-2 border-b border-terminal-border px-3 py-1.5">
        <h2 className="text-[11px] font-medium uppercase tracking-[0.08em] text-terminal-muted">
          {title}
        </h2>
        <div className="ml-auto flex items-center gap-2">{actions}</div>
      </header>
      <div className={`min-h-0 flex-1 ${bodyClassName}`}>{children}</div>
    </section>
  );
}
