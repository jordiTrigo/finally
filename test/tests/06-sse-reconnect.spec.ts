import { expect, test } from "@playwright/test";
import { AppProxy } from "./proxy";

/**
 * The stream is dropped by taking down a proxy in front of the app rather than
 * the container itself: the browser sees exactly what a restarting backend
 * looks like, and the test needs no control over Docker from inside the
 * browser image.
 */
test.describe("SSE resilience", () => {
  let proxy: AppProxy;

  test.beforeEach(async ({ baseURL }) => {
    proxy = await AppProxy.start(baseURL ?? "http://localhost:8001");
  });

  test.afterEach(async () => {
    await proxy.close();
  });

  test("recovers from a dropped stream without a reload", async ({ page }) => {
    await page.goto(proxy.url);

    const dot = page.getByTestId("connection-dot");
    const price = page.getByTestId("watchlist-price-AAPL");
    await expect(dot).toHaveAttribute("data-status", "connected");
    await expect(price).not.toHaveText("--");

    proxy.stop();

    await expect(dot).toHaveAttribute("data-status", /reconnecting|disconnected/);
    await expect(page.getByTestId("connection-label")).not.toHaveText("live");
    // The stall watchdog must also land on "disconnected": that is the branch
    // where the frontend retries itself, since a CLOSED EventSource never does.
    await expect(dot).toHaveAttribute("data-status", "disconnected");
    const frozen = await price.textContent();

    proxy.resume();

    await expect(dot).toHaveAttribute("data-status", "connected", { timeout: 30_000 });
    await expect(page.getByTestId("connection-label")).toHaveText("live");
    // Ticking again, and the page was never reloaded.
    await expect(price).not.toHaveText(frozen ?? "");
    await expect(page.getByTestId("watchlist-row-AAPL")).toBeVisible();
  });
});
