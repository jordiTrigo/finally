import { expect, test } from "@playwright/test";
import { openTerminal, trade } from "./helpers";

/**
 * Runs last: it deliberately leaves a held ticker off the watchlist.
 *
 * The market source is fed by the watchlist alone, so a position whose ticker
 * is removed stops being repriced while the UI still reports it as live. See
 * "Removing a held ticker freezes its position price" in E2E_REPORT.md.
 */
test.describe("position pricing", () => {
  test("keeps pricing a position after its ticker leaves the watchlist", async ({
    page,
  }) => {
    await openTerminal(page);

    await trade(page, "buy", "TSLA", 2);
    const price = page.getByTestId("position-price-TSLA");
    await expect(price).not.toHaveText("--");

    // Streaming while the ticker is still watched.
    const watched = await price.textContent();
    await expect(price).not.toHaveText(watched ?? "");

    await page.getByTestId("watchlist-remove-TSLA").click();
    await expect(page.getByTestId("watchlist-row-TSLA")).toHaveCount(0);

    const unwatched = await price.textContent();
    await expect(page.getByTestId("connection-dot")).toHaveAttribute(
      "data-status",
      "connected",
    );
    // The position is still held, so it must still be repriced.
    await expect(price).not.toHaveText(unwatched ?? "", { timeout: 10_000 });
  });
});
