import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { Header } from "./Header";
import type { StreamStatus } from "@/hooks/usePriceStream";

function renderHeader(status: StreamStatus = "connected", onToggleChat = vi.fn()) {
  render(
    <Header
      totalValue={10_500}
      cashBalance={8_000}
      unrealizedPnl={500}
      status={status}
      chatOpen
      onToggleChat={onToggleChat}
    />,
  );
  return onToggleChat;
}

describe("Header", () => {
  it("shows total value, cash, and P&L", () => {
    renderHeader();

    expect(screen.getByTestId("total-value")).toHaveTextContent("$10,500.00");
    expect(screen.getByTestId("cash-balance")).toHaveTextContent("$8,000.00");
    expect(screen.getByTestId("total-pnl")).toHaveTextContent("+$500.00");
    expect(screen.getByTestId("total-pnl")).toHaveTextContent("+5.00%");
  });

  it("colours a loss red", () => {
    render(
      <Header
        totalValue={9_500}
        cashBalance={8_000}
        unrealizedPnl={-500}
        status="connected"
        chatOpen
        onToggleChat={vi.fn()}
      />,
    );

    expect(screen.getByTestId("total-pnl")).toHaveClass("text-terminal-down");
  });

  it.each([
    ["connected", "live"],
    ["reconnecting", "reconnecting"],
    ["disconnected", "disconnected"],
    ["connecting", "connecting"],
  ] as const)("reports %s on the connection dot", (status, label) => {
    renderHeader(status);

    expect(screen.getByTestId("connection-dot")).toHaveAttribute(
      "data-status",
      status,
    );
    expect(screen.getByTestId("connection-label")).toHaveTextContent(label);
  });

  it("toggles the chat panel", async () => {
    const onToggleChat = renderHeader("connected");

    await userEvent.click(screen.getByTestId("chat-toggle"));

    expect(onToggleChat).toHaveBeenCalled();
  });
});
