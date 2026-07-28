import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { PortfolioHeatmap } from "./PortfolioHeatmap";
import type { Position } from "@/lib/types";

const positions: Position[] = [
  {
    ticker: "AAPL",
    quantity: 10,
    avg_cost: 180,
    current_price: 190,
    market_value: 1_900,
    unrealized_pnl: 100,
    pnl_percent: 5.56,
  },
];

describe("PortfolioHeatmap", () => {
  it("renders the treemap when there are positions", () => {
    render(<PortfolioHeatmap positions={positions} />);

    expect(screen.getByTestId("portfolio-heatmap")).toBeInTheDocument();
    expect(screen.queryByTestId("heatmap-empty")).toBeNull();
  });

  it("explains the empty state instead of drawing an empty chart", () => {
    render(<PortfolioHeatmap positions={[]} />);

    expect(screen.getByTestId("heatmap-empty")).toBeInTheDocument();
    expect(screen.queryByTestId("portfolio-heatmap")).toBeNull();
  });

  it("ignores positions that have no market value", () => {
    render(
      <PortfolioHeatmap
        positions={[{ ...positions[0], market_value: 0 }]}
      />,
    );

    expect(screen.getByTestId("heatmap-empty")).toBeInTheDocument();
  });
});
