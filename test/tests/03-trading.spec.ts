import { expect, test } from "@playwright/test";
import { openTerminal, readCash, trade } from "./helpers";

test.describe.configure({ mode: "serial" });

test.describe("trading", () => {
  test.beforeEach(async ({ page }) => {
    await openTerminal(page);
  });

  test("buying takes cash and opens a position", async ({ page }) => {
    const cashBefore = await readCash(page);
    await expect(page.getByTestId("positions-empty")).toBeVisible();

    await trade(page, "buy", "AAPL", 4);

    await expect(page.getByTestId("position-row-AAPL")).toBeVisible();
    await expect(page.getByTestId("position-quantity-AAPL")).toHaveText("4");
    await expect(page.getByTestId("position-price-AAPL")).not.toHaveText("--");
    await expect(page.getByTestId("heatmap-cell-AAPL")).toBeVisible();
    await expect(page.getByTestId("heatmap-empty")).toHaveCount(0);

    await expect
      .poll(() => readCash(page))
      .toBeLessThan(cashBefore - 4 * 100);
  });

  test("selling part of a position returns cash and reduces the quantity", async ({
    page,
  }) => {
    const cashBefore = await readCash(page);

    await trade(page, "sell", "AAPL", 1.5);

    await expect(page.getByTestId("position-quantity-AAPL")).toHaveText("2.5");
    await expect.poll(() => readCash(page)).toBeGreaterThan(cashBefore);
  });

  test("selling the rest closes the position", async ({ page }) => {
    await trade(page, "sell", "AAPL", 2.5);

    await expect(page.getByTestId("position-row-AAPL")).toHaveCount(0);
    await expect(page.getByTestId("positions-empty")).toBeVisible();
    await expect(page.getByTestId("heatmap-empty")).toBeVisible();
  });

  test("a buy beyond the cash balance shows an inline error", async ({ page }) => {
    await page.getByTestId("trade-ticker").fill("AAPL");
    await page.getByTestId("trade-quantity").fill("10000");
    await page.getByTestId("trade-buy").click();

    await expect(page.getByTestId("trade-error")).toContainText("Insufficient cash");
    await expect(page.getByTestId("trade-receipt")).toHaveCount(0);
    await expect(page.getByTestId("position-row-AAPL")).toHaveCount(0);
  });

  test("a sell of shares not held shows an inline error", async ({ page }) => {
    await page.getByTestId("trade-ticker").fill("TSLA");
    await page.getByTestId("trade-quantity").fill("5");
    await page.getByTestId("trade-sell").click();

    await expect(page.getByTestId("trade-error")).toBeVisible();
    await expect(page.getByTestId("trade-receipt")).toHaveCount(0);
  });
});
