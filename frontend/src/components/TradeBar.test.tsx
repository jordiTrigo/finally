import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { TradeBar } from "./TradeBar";
import type { PriceUpdate, TradeReceipt } from "@/lib/types";

const prices: Record<string, PriceUpdate> = {
  AAPL: {
    ticker: "AAPL",
    price: 190,
    previous_price: 189,
    timestamp: "2026-07-28T12:00:00+00:00",
    direction: "up",
  },
};

const receipt: TradeReceipt = {
  ticker: "AAPL",
  side: "buy",
  quantity: 2,
  price: 190,
  executed_at: "2026-07-28T12:00:00+00:00",
  cash_balance: 9620,
};

describe("TradeBar", () => {
  it("prefills the ticker from the current selection", () => {
    render(<TradeBar selectedTicker="AAPL" prices={prices} onTrade={vi.fn()} />);

    expect(screen.getByTestId("trade-ticker")).toHaveValue("AAPL");
  });

  it("estimates the order value from the live price", async () => {
    render(<TradeBar selectedTicker="AAPL" prices={prices} onTrade={vi.fn()} />);

    await userEvent.clear(screen.getByTestId("trade-quantity"));
    await userEvent.type(screen.getByTestId("trade-quantity"), "3");

    expect(screen.getByTestId("trade-estimate")).toHaveTextContent("$570.00");
  });

  it("submits a buy at the entered quantity", async () => {
    const onTrade = vi.fn().mockResolvedValue(receipt);
    render(<TradeBar selectedTicker="AAPL" prices={prices} onTrade={onTrade} />);

    await userEvent.clear(screen.getByTestId("trade-quantity"));
    await userEvent.type(screen.getByTestId("trade-quantity"), "2");
    await userEvent.click(screen.getByTestId("trade-buy"));

    expect(onTrade).toHaveBeenCalledWith("AAPL", "buy", 2);
    expect(await screen.findByTestId("trade-receipt")).toHaveTextContent("BUY 2 AAPL");
  });

  it("submits a sell", async () => {
    const onTrade = vi.fn().mockResolvedValue({ ...receipt, side: "sell" });
    render(<TradeBar selectedTicker="AAPL" prices={prices} onTrade={onTrade} />);

    await userEvent.click(screen.getByTestId("trade-sell"));

    expect(onTrade).toHaveBeenCalledWith("AAPL", "sell", 1);
  });

  it("shows the backend rejection inline instead of a dialog", async () => {
    const onTrade = vi
      .fn()
      .mockRejectedValue(new Error("Insufficient cash: need $500, have $100"));
    render(<TradeBar selectedTicker="AAPL" prices={prices} onTrade={onTrade} />);

    await userEvent.click(screen.getByTestId("trade-buy"));

    expect(await screen.findByTestId("trade-error")).toHaveTextContent(
      "Insufficient cash: need $500, have $100",
    );
    expect(screen.queryByTestId("trade-receipt")).toBeNull();
  });

  it("rejects a non-positive quantity without calling the API", async () => {
    const onTrade = vi.fn();
    render(<TradeBar selectedTicker="AAPL" prices={prices} onTrade={onTrade} />);

    await userEvent.clear(screen.getByTestId("trade-quantity"));
    await userEvent.type(screen.getByTestId("trade-quantity"), "0");
    await userEvent.click(screen.getByTestId("trade-buy"));

    expect(onTrade).not.toHaveBeenCalled();
    expect(screen.getByTestId("trade-error")).toHaveTextContent(
      "Quantity must be greater than zero",
    );
  });

  it("rejects an empty ticker without calling the API", async () => {
    const onTrade = vi.fn();
    render(<TradeBar selectedTicker={null} prices={prices} onTrade={onTrade} />);

    await userEvent.click(screen.getByTestId("trade-buy"));

    expect(onTrade).not.toHaveBeenCalled();
    expect(screen.getByTestId("trade-error")).toHaveTextContent("Enter a ticker");
  });
});
