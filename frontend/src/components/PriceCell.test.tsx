import { render, screen } from "@testing-library/react";
import { act } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { FLASH_MS, PriceCell } from "./PriceCell";

describe("PriceCell", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("renders the price to two decimals", () => {
    render(<PriceCell price={190.5} testId="cell" />);
    expect(screen.getByTestId("cell")).toHaveTextContent("190.50");
  });

  it("does not flash on first render", () => {
    render(<PriceCell price={190} testId="cell" />);
    expect(screen.getByTestId("cell").className).not.toMatch(/flash-/);
  });

  it("applies flash-up on an uptick", () => {
    const { rerender } = render(<PriceCell price={190} testId="cell" />);
    rerender(<PriceCell price={191} testId="cell" />);

    expect(screen.getByTestId("cell")).toHaveClass("flash-up");
  });

  it("applies flash-down on a downtick", () => {
    const { rerender } = render(<PriceCell price={190} testId="cell" />);
    rerender(<PriceCell price={189} testId="cell" />);

    expect(screen.getByTestId("cell")).toHaveClass("flash-down");
  });

  it("does not flash when the price is unchanged", () => {
    const { rerender } = render(<PriceCell price={190} testId="cell" />);
    rerender(<PriceCell price={190} testId="cell" />);

    expect(screen.getByTestId("cell").className).not.toMatch(/flash-/);
  });

  it("clears the flash class so the CSS transition can fade it out", () => {
    const { rerender } = render(<PriceCell price={190} testId="cell" />);
    rerender(<PriceCell price={191} testId="cell" />);
    expect(screen.getByTestId("cell")).toHaveClass("flash-up");

    act(() => vi.advanceTimersByTime(FLASH_MS + 10));

    expect(screen.getByTestId("cell").className).not.toMatch(/flash-/);
  });

  it("shows a dash while the ticker has no price", () => {
    render(<PriceCell price={null} testId="cell" />);
    expect(screen.getByTestId("cell")).toHaveTextContent("--");
  });
});
