import { expect, test } from "@playwright/test";
import { DEFAULT_TICKERS, flashCount, installFlashRecorder } from "./helpers";

/**
 * Runs first and against a fresh database, so the seeded values are still
 * intact. Every later spec trades and therefore moves them.
 */
test.describe("fresh start", () => {
  test.beforeEach(async ({ page }) => {
    await installFlashRecorder(page);
    await page.goto("/");
  });

  test("shows the ten seeded tickers", async ({ page }) => {
    await expect(page.getByTestId("watchlist")).toBeVisible();
    for (const ticker of DEFAULT_TICKERS) {
      await expect(page.getByTestId(`watchlist-row-${ticker}`)).toBeVisible();
    }
    await expect(page.getByTestId("watchlist-empty")).toHaveCount(0);
  });

  test("starts with $10,000 cash, no positions and no load error", async ({ page }) => {
    await expect(page.getByTestId("cash-balance")).toHaveText("$10,000.00");
    await expect(page.getByTestId("total-value")).toHaveText("$10,000.00");
    await expect(page.getByTestId("total-pnl")).toHaveText("+$0.00 (+0.00%)");
    await expect(page.getByTestId("positions-empty")).toBeVisible();
    await expect(page.getByTestId("heatmap-empty")).toBeVisible();
    await expect(page.getByTestId("load-error")).toHaveCount(0);
  });

  test("connects the stream and quotes every ticker", async ({ page }) => {
    await expect(page.getByTestId("connection-dot")).toHaveAttribute(
      "data-status",
      "connected",
    );
    await expect(page.getByTestId("connection-label")).toHaveText("live");

    for (const ticker of DEFAULT_TICKERS) {
      await expect(page.getByTestId(`watchlist-price-${ticker}`)).not.toHaveText("--");
    }
  });

  test("keeps prices moving and flashes the change", async ({ page }) => {
    const price = page.getByTestId("watchlist-price-AAPL");
    await expect(price).not.toHaveText("--");

    const first = await price.textContent();
    await expect(price).not.toHaveText(first ?? "");

    // The flash class lives for 300ms; the recorder catches it either way.
    await expect.poll(() => flashCount(page), { timeout: 20_000 }).toBeGreaterThan(0);
  });

  test("draws a sparkline per ticker once ticks accumulate", async ({ page }) => {
    await expect(page.getByTestId("sparkline-AAPL")).toBeVisible();
    await expect(
      page.getByTestId("sparkline-AAPL").locator("polyline"),
    ).toHaveCount(1);
  });
});
