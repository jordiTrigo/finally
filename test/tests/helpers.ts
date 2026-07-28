import { expect, type Page } from "@playwright/test";

export const DEFAULT_TICKERS = [
  "AAPL",
  "GOOGL",
  "MSFT",
  "AMZN",
  "TSLA",
  "NVDA",
  "META",
  "JPM",
  "V",
  "NFLX",
];

/** "$9,812.34" -> 9812.34. Also handles the header's "+$12.34" / "-$12.34". */
export function parseMoney(text: string | null): number {
  const cleaned = (text ?? "").replace(/[^0-9.-]/g, "");
  return Number(cleaned);
}

export async function readCash(page: Page): Promise<number> {
  return parseMoney(await page.getByTestId("cash-balance").textContent());
}

/** Open the terminal and wait until the stream is live with a real quote. */
export async function openTerminal(page: Page): Promise<void> {
  await installFlashRecorder(page);
  await page.goto("/");
  await expect(page.getByTestId("header")).toBeVisible();
  await expect(page.getByTestId("connection-dot")).toHaveAttribute(
    "data-status",
    "connected",
  );
  await expect(page.getByTestId("watchlist-price-AAPL")).not.toHaveText("--");
}

/**
 * Record every flash class the app applies, before the app boots. The class is
 * removed after 300ms, so polling the DOM for it would be a race; a mutation
 * observer catches it whenever it happens.
 */
export async function installFlashRecorder(page: Page): Promise<void> {
  await page.addInitScript(() => {
    const flashes: string[] = [];
    (window as unknown as { __flashes: string[] }).__flashes = flashes;

    const observer = new MutationObserver((records) => {
      for (const record of records) {
        const className = (record.target as HTMLElement).className;
        if (typeof className !== "string") continue;
        if (className.includes("flash-up")) flashes.push("up");
        else if (className.includes("flash-down")) flashes.push("down");
      }
    });

    document.addEventListener("DOMContentLoaded", () => {
      observer.observe(document.body, {
        subtree: true,
        attributes: true,
        attributeFilter: ["class"],
      });
    });
  });
}

export function flashCount(page: Page): Promise<number> {
  return page.evaluate(
    () => (window as unknown as { __flashes: string[] }).__flashes.length,
  );
}

/** Place a market order through the trade bar and wait for the receipt. */
export async function trade(
  page: Page,
  side: "buy" | "sell",
  ticker: string,
  quantity: number,
): Promise<void> {
  await page.getByTestId("trade-ticker").fill(ticker);
  await page.getByTestId("trade-quantity").fill(String(quantity));
  await page.getByTestId(side === "buy" ? "trade-buy" : "trade-sell").click();
  await expect(page.getByTestId("trade-receipt")).toContainText(
    `${side.toUpperCase()} ${quantity} ${ticker}`,
  );
}

/** Send a chat message and wait for the assistant's reply to land. */
export async function chat(page: Page, message: string): Promise<void> {
  const replies = page.getByTestId("chat-message-assistant");
  const before = await replies.count();
  await page.getByTestId("chat-input").fill(message);
  await page.getByTestId("chat-send").click();
  await expect(replies).toHaveCount(before + 1);
}
