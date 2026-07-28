import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { PositionsTable } from "./PositionsTable";
import type { Position } from "@/lib/types";

const positions: Position[] = [
  {
    ticker: "AAPL",
    quantity: 10,
    avg_cost: 180,
    current_price: 190,
    market_value: 1_900,
    unrealized_pnl: 100,
    pnl_percent: 5.5556,
  },
  {
    ticker: "TSLA",
    quantity: 2.5,
    avg_cost: 240,
    current_price: 220,
    market_value: 550,
    unrealized_pnl: -50,
    pnl_percent: -8.3333,
  },
];

describe("PositionsTable", () => {
  it("renders a row per position", () => {
    render(<PositionsTable positions={positions} onSelect={vi.fn()} />);

    expect(screen.getByTestId("position-row-AAPL")).toBeInTheDocument();
    expect(screen.getByTestId("position-row-TSLA")).toBeInTheDocument();
  });

  it("shows fractional quantities without trailing zeros", () => {
    render(<PositionsTable positions={positions} onSelect={vi.fn()} />);

    expect(screen.getByTestId("position-quantity-AAPL")).toHaveTextContent("10");
    expect(screen.getByTestId("position-quantity-TSLA")).toHaveTextContent("2.5");
  });

  it("colours gains green and losses red", () => {
    render(<PositionsTable positions={positions} onSelect={vi.fn()} />);

    expect(screen.getByTestId("position-pnl-AAPL")).toHaveTextContent("+$100.00");
    expect(screen.getByTestId("position-pnl-AAPL")).toHaveClass("text-terminal-up");
    expect(screen.getByTestId("position-pnl-TSLA")).toHaveTextContent("-$50.00");
    expect(screen.getByTestId("position-pnl-TSLA")).toHaveClass("text-terminal-down");
  });

  it("selects the ticker when a row is clicked", async () => {
    const onSelect = vi.fn();
    render(<PositionsTable positions={positions} onSelect={onSelect} />);

    await userEvent.click(screen.getByTestId("position-row-TSLA"));

    expect(onSelect).toHaveBeenCalledWith("TSLA");
  });

  it("explains the empty state", () => {
    render(<PositionsTable positions={[]} onSelect={vi.fn()} />);

    expect(screen.getByTestId("positions-empty")).toBeInTheDocument();
    expect(screen.queryByTestId("positions-table")).toBeNull();
  });
});
