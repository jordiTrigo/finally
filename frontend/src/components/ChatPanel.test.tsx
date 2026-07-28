import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeAll, describe, expect, it, vi } from "vitest";
import { ChatPanel } from "./ChatPanel";
import type { ChatMessage } from "@/lib/types";

const messages: ChatMessage[] = [
  {
    id: "1",
    role: "user",
    content: "Buy 5 NVDA",
    actions: null,
    created_at: "2026-07-28T12:00:00+00:00",
  },
  {
    id: "2",
    role: "assistant",
    content: "Bought 5 NVDA.",
    actions: [
      { type: "trade", status: "executed", detail: "buy 5 NVDA @ $120.00" },
      { type: "watchlist", status: "failed", detail: "PYPL already watched" },
    ],
    created_at: "2026-07-28T12:00:02+00:00",
  },
];

beforeAll(() => {
  // jsdom has no layout engine, so the auto-scroll call needs a stub.
  Element.prototype.scrollIntoView = vi.fn();
});

describe("ChatPanel", () => {
  it("renders the conversation in order", () => {
    render(
      <ChatPanel messages={messages} pending={false} error={null} onSend={vi.fn()} />,
    );

    expect(screen.getByTestId("chat-message-user")).toHaveTextContent("Buy 5 NVDA");
    expect(screen.getByTestId("chat-message-assistant")).toHaveTextContent(
      "Bought 5 NVDA.",
    );
  });

  it("shows executed and failed actions inline", () => {
    render(
      <ChatPanel messages={messages} pending={false} error={null} onSend={vi.fn()} />,
    );

    const actions = screen.getAllByTestId("chat-action");
    expect(actions).toHaveLength(2);
    expect(actions[0]).toHaveAttribute("data-status", "executed");
    expect(actions[0]).toHaveTextContent("buy 5 NVDA @ $120.00");
    expect(actions[1]).toHaveAttribute("data-status", "failed");
  });

  it("prompts the user when there is no history", () => {
    render(<ChatPanel messages={[]} pending={false} error={null} onSend={vi.fn()} />);

    expect(screen.getByTestId("chat-empty")).toBeInTheDocument();
  });

  it("shows a loading indicator and disables send while waiting", () => {
    render(<ChatPanel messages={messages} pending error={null} onSend={vi.fn()} />);

    expect(screen.getByTestId("chat-loading")).toBeInTheDocument();
    expect(screen.getByTestId("chat-send")).toBeDisabled();
  });

  it("hides the loading indicator when idle", () => {
    render(
      <ChatPanel messages={messages} pending={false} error={null} onSend={vi.fn()} />,
    );

    expect(screen.queryByTestId("chat-loading")).toBeNull();
  });

  it("sends the trimmed draft and clears the input", async () => {
    const onSend = vi.fn().mockResolvedValue(undefined);
    render(<ChatPanel messages={[]} pending={false} error={null} onSend={onSend} />);

    await userEvent.type(screen.getByTestId("chat-input"), "  how am I doing?  ");
    await userEvent.click(screen.getByTestId("chat-send"));

    expect(onSend).toHaveBeenCalledWith("how am I doing?");
    expect(screen.getByTestId("chat-input")).toHaveValue("");
  });

  it("ignores an empty draft", async () => {
    const onSend = vi.fn();
    render(<ChatPanel messages={[]} pending={false} error={null} onSend={onSend} />);

    await userEvent.click(screen.getByTestId("chat-send"));

    expect(onSend).not.toHaveBeenCalled();
  });

  it("surfaces a chat error", () => {
    render(
      <ChatPanel
        messages={[]}
        pending={false}
        error="FinAlly did not reply"
        onSend={vi.fn()}
      />,
    );

    expect(screen.getByTestId("chat-error")).toHaveTextContent(
      "FinAlly did not reply",
    );
  });
});
