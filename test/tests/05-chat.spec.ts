import { expect, test } from "@playwright/test";
import { chat, openTerminal, readCash } from "./helpers";

test.describe.configure({ mode: "serial" });

/** LLM_MOCK=true: a command parser stands in for the model, but the actions it
    returns run through the same execution path a real response would. */
test.describe("AI chat", () => {
  test.beforeEach(async ({ page }) => {
    await openTerminal(page);
    await expect(page.getByTestId("chat-panel")).toBeVisible();
  });

  test("answers a message it has no action for", async ({ page }) => {
    await chat(page, "how is my portfolio doing");

    await expect(page.getByTestId("chat-message-user").last()).toContainText(
      "how is my portfolio doing",
    );
    await expect(page.getByTestId("chat-message-assistant").last()).toContainText(
      "Mock mode: no model was called",
    );
    await expect(page.getByTestId("chat-action")).toHaveCount(0);
    await expect(page.getByTestId("chat-error")).toHaveCount(0);
  });

  test("executes a trade and confirms it inline", async ({ page }) => {
    const cashBefore = await readCash(page);

    await chat(page, "buy 6 TSLA");

    await expect(page.getByTestId("chat-message-assistant").last()).toContainText(
      "Mock mode: executing buy 6 TSLA",
    );
    const action = page.getByTestId("chat-action").last();
    await expect(action).toHaveAttribute("data-status", "executed");
    await expect(action).toContainText("buy 6 TSLA filled at $");

    await expect(page.getByTestId("position-row-TSLA")).toBeVisible();
    await expect(page.getByTestId("position-quantity-TSLA")).toHaveText("6");
    await expect.poll(() => readCash(page)).toBeLessThan(cashBefore);
  });

  test("changes the watchlist and confirms it inline", async ({ page }) => {
    await chat(page, "add PYPL to the watchlist");

    const action = page.getByTestId("chat-action").last();
    await expect(action).toHaveAttribute("data-status", "executed");
    await expect(action).toContainText("Added PYPL to the watchlist");
    await expect(page.getByTestId("watchlist-row-PYPL")).toBeVisible();

    await chat(page, "remove PYPL from the watchlist");

    await expect(page.getByTestId("chat-action").last()).toContainText(
      "Removed PYPL from the watchlist",
    );
    await expect(page.getByTestId("watchlist-row-PYPL")).toHaveCount(0);
  });

  test("reports a rejected trade as a failed action", async ({ page }) => {
    await chat(page, "sell 40 META");

    const action = page.getByTestId("chat-action").last();
    await expect(action).toHaveAttribute("data-status", "failed");
    await expect(action).toContainText("rejected");
    await expect(page.getByTestId("position-row-META")).toHaveCount(0);
  });

  test("reloads the conversation from the server", async ({ page }) => {
    const before = await page.getByTestId("chat-message-user").count();
    expect(before).toBeGreaterThan(0);

    await page.reload();

    await expect(page.getByTestId("chat-message-user")).toHaveCount(before);
    await expect(page.getByTestId("chat-empty")).toHaveCount(0);
  });

  test("collapses and reopens the panel", async ({ page }) => {
    await page.getByTestId("chat-toggle").click();
    await expect(page.getByTestId("chat-panel")).toHaveCount(0);

    await page.getByTestId("chat-toggle").click();
    await expect(page.getByTestId("chat-panel")).toBeVisible();
  });
});
