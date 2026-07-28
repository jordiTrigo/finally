"use client";

import { useEffect, useRef, useState } from "react";
import { formatClock } from "@/lib/format";
import type { ChatAction, ChatMessage } from "@/lib/types";

interface ChatPanelProps {
  messages: ChatMessage[];
  pending: boolean;
  error: string | null;
  onSend: (text: string) => Promise<void>;
}

function ActionChip({ action }: { action: ChatAction }) {
  const executed = action.status === "executed";

  return (
    <li
      data-testid="chat-action"
      data-status={action.status}
      className={`flex items-start gap-1.5 border-l-2 px-2 py-1 ${
        executed
          ? "border-terminal-up bg-terminal-up/10 text-terminal-up"
          : "border-terminal-down bg-terminal-down/10 text-terminal-down"
      }`}
    >
      <span className="text-[10px] uppercase tracking-[0.08em] opacity-80">
        {action.type}
      </span>
      <span className="min-w-0 flex-1 break-words">{action.detail}</span>
    </li>
  );
}

function Message({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";

  return (
    <li
      data-testid={`chat-message-${message.role}`}
      data-role={message.role}
      className="flex flex-col gap-1"
    >
      <span className="text-[10px] uppercase tracking-[0.08em] text-terminal-muted">
        {isUser ? "You" : "FinAlly"} &middot; {formatClock(message.created_at)}
      </span>
      <p
        className={`whitespace-pre-wrap break-words border px-2.5 py-1.5 ${
          isUser
            ? "border-terminal-blue/40 bg-terminal-blue/10"
            : "border-terminal-border bg-terminal-raised"
        }`}
      >
        {message.content}
      </p>
      {message.actions && message.actions.length > 0 && (
        <ul className="flex flex-col gap-1">
          {message.actions.map((action, index) => (
            <ActionChip key={index} action={action} />
          ))}
        </ul>
      )}
    </li>
  );
}

/** Collapsible AI sidebar. History arrives from `GET /api/chat` on mount. */
export function ChatPanel({ messages, pending, error, onSend }: ChatPanelProps) {
  const [draft, setDraft] = useState("");
  const bottom = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottom.current?.scrollIntoView({ block: "end" });
  }, [messages, pending]);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    const text = draft.trim();
    if (!text || pending) return;
    setDraft("");
    await onSend(text);
  }

  return (
    <aside
      data-testid="chat-panel"
      className="flex w-[340px] shrink-0 flex-col border-l border-terminal-border bg-terminal-panel"
    >
      <header className="flex shrink-0 items-center gap-2 border-b border-terminal-border px-3 py-1.5">
        <h2 className="text-[11px] font-medium uppercase tracking-[0.08em] text-terminal-muted">
          AI Assistant
        </h2>
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto px-3 py-3">
        {messages.length === 0 && !pending && (
          <p data-testid="chat-empty" className="text-terminal-muted">
            Ask FinAlly to analyze the portfolio, place a trade, or manage the
            watchlist.
          </p>
        )}

        <ul className="flex flex-col gap-3">
          {messages.map((message) => (
            <Message key={message.id} message={message} />
          ))}
        </ul>

        {pending && (
          <p data-testid="chat-loading" className="mt-3 text-terminal-accent">
            FinAlly is thinking...
          </p>
        )}

        {error && (
          <p data-testid="chat-error" role="alert" className="mt-3 text-terminal-down">
            {error}
          </p>
        )}

        <div ref={bottom} />
      </div>

      <form
        onSubmit={submit}
        className="flex shrink-0 items-center gap-2 border-t border-terminal-border px-3 py-2"
      >
        <input
          data-testid="chat-input"
          aria-label="Message FinAlly"
          placeholder="Ask FinAlly..."
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          className="min-w-0 flex-1 border border-terminal-border bg-terminal-bg px-2 py-1 outline-none placeholder:text-terminal-muted/70 focus:border-terminal-blue"
        />
        <button
          type="submit"
          data-testid="chat-send"
          disabled={pending}
          className="bg-terminal-purple px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.08em] text-white transition-opacity hover:opacity-85 disabled:opacity-50"
        >
          Send
        </button>
      </form>
    </aside>
  );
}
