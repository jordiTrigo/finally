import { expect, test } from "@playwright/test";
import { openTerminal, trade } from "./helpers";

test.describe.configure({ mode: "serial" });

test.describe("visualizations", () => {
  test.beforeEach(async ({ page }) => {
    await openTerminal(page);
  });

  test("the price chart draws the selected ticker", async ({ page }) => {
    await page.getByTestId("watchlist-row-MSFT").click();

    const chart = page.getByTestId("price-chart");
    await expect(chart).toContainText("MSFT - price");
    await expect(chart.locator("canvas").first()).toBeVisible();
    await expect(chart).not.toContainText("Accumulating MSFT ticks");
  });

  test("the heatmap renders a cell per position, coloured by P&L", async ({ page }) => {
    await trade(page, "buy", "NVDA", 3);
    await trade(page, "buy", "JPM", 2);

    await expect(page.getByTestId("portfolio-heatmap")).toBeVisible();
    const cell = page.getByTestId("heatmap-cell-NVDA");
    await expect(cell).toBeVisible();
    await expect(page.getByTestId("heatmap-cell-JPM")).toBeVisible();

    // Green above zero, red below - the fill is the only carrier of that signal.
    const fill = await cell.locator("rect").getAttribute("fill");
    expect(fill).toMatch(/rgba\((38, 166, 91|224, 69, 62), /);
  });

  test("the P&L chart has data once a snapshot exists", async ({ page }) => {
    const chart = page.getByTestId("pnl-chart");
    await expect(chart).toBeVisible();
    await expect(chart.locator("canvas").first()).toBeVisible();
    await expect(chart).not.toContainText("Waiting for the first snapshot");
  });

  test("the positions table reports quantity, price and P&L", async ({ page }) => {
    await expect(page.getByTestId("positions-table")).toBeVisible();
    await expect(page.getByTestId("position-quantity-NVDA")).toHaveText("3");
    await expect(page.getByTestId("position-price-NVDA")).not.toHaveText("--");
    await expect(page.getByTestId("position-pnl-NVDA")).toContainText("$");
  });
});
