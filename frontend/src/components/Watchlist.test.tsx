import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { Watchlist } from "./Watchlist";
import type { PricePoint } from "@/hooks/usePriceStream";
import type { PriceUpdate, WatchlistEntry } from "@/lib/types";

const entries: WatchlistEntry[] = [
  { ticker: "AAPL", price: 190, previous_price: 189, direction: "up" },
  { ticker: "MSFT", price: null, previous_price: null, direction: "flat" },
];

const prices: Record<string, PriceUpdate> = {
  AAPL: {
    ticker: "AAPL",
    price: 191.25,
    previous_price: 190,
    timestamp: "2026-07-28T12:00:00+00:00",
    direction: "up",
  },
};

const history: Record<string, PricePoint[]> = {
  AAPL: [
    { time: 1, value: 190 },
    { time: 2, value: 191.25 },
  ],
};

function renderWatchlist(overrides: Partial<Parameters<typeof Watchlist>[0]> = {}) {
  const props = {
    entries,
    prices,
    history,
    selected: "AAPL",
    onSelect: vi.fn(),
    onAdd: vi.fn().mockResolvedValue(undefined),
    onRemove: vi.fn().mockResolvedValue(undefined),
    ...overrides,
  };
  render(<Watchlist {...props} />);
  return props;
}

describe("Watchlist", () => {
  it("renders a row per watched ticker", () => {
    renderWatchlist();

    expect(screen.getByTestId("watchlist-row-AAPL")).toBeInTheDocument();
    expect(screen.getByTestId("watchlist-row-MSFT")).toBeInTheDocument();
  });

  it("prefers the streamed price over the price from the watchlist fetch", () => {
    renderWatchlist();

    expect(screen.getByTestId("watchlist-price-AAPL")).toHaveTextContent("191.25");
  });

  it("renders a dash for a ticker the cache has not seen", () => {
    renderWatchlist();

    expect(screen.getByTestId("watchlist-price-MSFT")).toHaveTextContent("--");
  });

  it("shows session change against the first sample seen", () => {
    renderWatchlist();

    expect(screen.getByTestId("watchlist-change-AAPL")).toHaveTextContent("+0.66%");
    expect(screen.getByTestId("watchlist-change-MSFT")).toHaveTextContent("--");
  });

  it("draws a sparkline once there are at least two samples", () => {
    const { container } = render(
      <Watchlist
        entries={entries}
        prices={prices}
        history={history}
        selected={null}
        onSelect={vi.fn()}
        onAdd={vi.fn()}
        onRemove={vi.fn()}
      />,
    );

    expect(
      container.querySelector('[data-testid="sparkline-AAPL"] polyline'),
    ).toBeInTheDocument();
    expect(
      container.querySelector('[data-testid="sparkline-MSFT"] polyline'),
    ).toBeNull();
  });

  it("marks the selected row", () => {
    renderWatchlist();

    expect(screen.getByTestId("watchlist-row-AAPL")).toHaveAttribute(
      "data-selected",
      "true",
    );
    expect(screen.getByTestId("watchlist-row-MSFT")).toHaveAttribute(
      "data-selected",
      "false",
    );
  });

  it("selects a ticker when its row is clicked", async () => {
    const props = renderWatchlist();

    await userEvent.click(screen.getByTestId("watchlist-row-MSFT"));

    expect(props.onSelect).toHaveBeenCalledWith("MSFT");
  });

  it("adds an uppercased ticker and clears the field", async () => {
    const props = renderWatchlist();

    await userEvent.type(screen.getByTestId("watchlist-add-input"), "pypl");
    await userEvent.click(screen.getByTestId("watchlist-add-button"));

    expect(props.onAdd).toHaveBeenCalledWith("PYPL");
    expect(screen.getByTestId("watchlist-add-input")).toHaveValue("");
  });

  it("shows an inline error when the add is rejected", async () => {
    renderWatchlist({ onAdd: vi.fn().mockRejectedValue(new Error("Already watched")) });

    await userEvent.type(screen.getByTestId("watchlist-add-input"), "AAPL");
    await userEvent.click(screen.getByTestId("watchlist-add-button"));

    expect(await screen.findByTestId("watchlist-error")).toHaveTextContent(
      "Already watched",
    );
  });

  it("clears the add error as soon as the field is edited", async () => {
    renderWatchlist({ onAdd: vi.fn().mockRejectedValue(new Error("Already watched")) });

    await userEvent.type(screen.getByTestId("watchlist-add-input"), "AAPL");
    await userEvent.click(screen.getByTestId("watchlist-add-button"));
    expect(await screen.findByTestId("watchlist-error")).toBeInTheDocument();

    await userEvent.type(screen.getByTestId("watchlist-add-input"), "P");

    expect(screen.queryByTestId("watchlist-error")).toBeNull();
  });

  it("removes a ticker without selecting it", async () => {
    const props = renderWatchlist();

    await userEvent.click(screen.getByTestId("watchlist-remove-MSFT"));

    expect(props.onRemove).toHaveBeenCalledWith("MSFT");
    expect(props.onSelect).not.toHaveBeenCalled();
  });

  it("invites the user to add a ticker when the list is empty", () => {
    renderWatchlist({ entries: [] });

    expect(screen.getByTestId("watchlist-empty")).toBeInTheDocument();
  });
});
