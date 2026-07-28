import { expect, test } from "@playwright/test";
import { openTerminal } from "./helpers";

test.describe.configure({ mode: "serial" });

test.describe("watchlist", () => {
  test.beforeEach(async ({ page }) => {
    await openTerminal(page);
  });

  test("adds a ticker and starts quoting it", async ({ page }) => {
    await expect(page.getByTestId("watchlist-row-PYPL")).toHaveCount(0);

    await page.getByTestId("watchlist-add-input").fill("PYPL");
    await page.getByTestId("watchlist-add-button").click();

    await expect(page.getByTestId("watchlist-row-PYPL")).toBeVisible();
    // A ticker the cache has not seen renders "--" for about a tick.
    await expect(page.getByTestId("watchlist-price-PYPL")).not.toHaveText("--");
    await expect(page.getByTestId("watchlist-error")).toHaveCount(0);
    await expect(page.getByTestId("watchlist-add-input")).toHaveValue("");
  });

  test("rejects a duplicate with an inline error", async ({ page }) => {
    await page.getByTestId("watchlist-add-input").fill("AAPL");
    await page.getByTestId("watchlist-add-button").click();

    await expect(page.getByTestId("watchlist-error")).toHaveText(
      "AAPL is already on the watchlist",
    );
    await expect(page.getByTestId("watchlist-row-AAPL")).toHaveCount(1);
  });

  test("removes a ticker", async ({ page }) => {
    await expect(page.getByTestId("watchlist-row-PYPL")).toBeVisible();

    await page.getByTestId("watchlist-remove-PYPL").click();

    await expect(page.getByTestId("watchlist-row-PYPL")).toHaveCount(0);
    await expect(page.getByTestId("watchlist-row-AAPL")).toBeVisible();
  });

  test("selects a ticker for the main chart", async ({ page }) => {
    await page.getByTestId("watchlist-row-NVDA").click();

    await expect(page.getByTestId("watchlist-row-NVDA")).toHaveAttribute(
      "data-selected",
      "true",
    );
    await expect(page.getByTestId("price-chart")).toContainText("NVDA - price");
    await expect(page.getByTestId("trade-ticker")).toHaveValue("NVDA");
  });
});
