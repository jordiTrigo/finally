# FinAlly E2E Report

Suite: `test/` (Playwright 1.62, Chromium). 26 tests, single worker, no retries.
Run against the production image with `LLM_MOCK=true` and `MASSIVE_API_KEY` empty, on a
fresh database each run.

## Current result - all green

Against a freshly built image carrying the Backend API fix:

```
$ docker compose -f test/docker-compose.test.yml up --build \
      --abort-on-container-exit --exit-code-from playwright
...
playwright-1  | Running 26 tests using 1 worker
playwright-1  |   ...
playwright-1  |   ✓  26 [chromium] › tests/07-position-pricing.spec.ts:12:7 › position pricing ›
playwright-1  |      keeps pricing a position after its ticker leaves the watchlist (2.0s)
playwright-1  |   26 passed (30.5s)
COMPOSE_EXIT=0
```

Run twice back to back, both 26/26. The formerly failing spec now finishes in 2.0s instead
of burning its full 10s timeout - it sees the price move almost immediately.

## First run - one failure

```
$ docker compose -f test/docker-compose.test.yml up --build \
      --abort-on-container-exit --exit-code-from playwright
...
  25 passed (41.8s)
  1 failed
    [chromium] tests/07-position-pricing.spec.ts:12:7 position pricing
      keeps pricing a position after its ticker leaves the watchlist
```

Two consecutive compose runs and four host runs (`BASE_URL=http://localhost:8002
npx playwright test`) gave the same result every time: the same 25 pass, the same one
fails. Nothing in the suite is flaky.

## Coverage

| Scenario | Spec | Result |
| --- | --- | --- |
| Fresh start: ten seeded tickers, $10,000, streaming, flashing, sparklines | `01-fresh-start` | pass (5) |
| Watchlist add, duplicate rejection, remove, selection | `02-watchlist` | pass (4) |
| Buy, partial sell, close-out, insufficient cash, insufficient shares | `03-trading` | pass (5) |
| Price chart, heatmap colouring, P&L chart, positions table | `04-visualizations` | pass (4) |
| Mocked chat: idle reply, executed trade, watchlist change, failed action, history reload, collapse | `05-chat` | pass (6) |
| SSE drop and recovery without a reload | `06-sse-reconnect` | pass (1) |
| Position pricing after its ticker leaves the watchlist | `07-position-pricing` | pass (1), was failing |

Every element is selected by `data-testid`. The whole inventory the Frontend Engineer
published is present in the build - nothing had to fall back to CSS or text, and there is
nothing missing to report.

## Findings

### Removing a held ticker freezes its position price - RESOLVED
Owner:    Backend API
Status:   Fixed and verified. `get_watchlist_tickers()` in `backend/app/main.py` now
          returns the watchlist unioned with the tickers currently held, deduped and
          order-preserving:

          ```python
          held = (position["ticker"] for position in get_positions())
          return list(dict.fromkeys([*get_watchlist(), *held]))
          ```

          Re-verified against a freshly built image. `07-position-pricing` passes, and the
          same manual reproduction now shows both positions repricing after TSLA is
          removed from the watchlist:

          ```
          --- 3s after removal ---
          AAPL 190.04373716274276 0.044461562708562496
          TSLA 250.02585740413483 0.07962695245942086
          --- 5s later ---
          AAPL 190.0400759502892 0.04080035025501161
          TSLA 250.01908715078645 0.06608644576266443
          ```

          The stream carries genuinely new TSLA ticks rather than re-pushing one frozen
          event, with a moving timestamp and a real direction:

          ```
          data: {"ticker": "TSLA", "price": 250.01908715078645, "previous_price": 250.0155450699417,
                 "timestamp": "2026-07-28T20:26:21.828207+00:00", "direction": "up"}
          data: {"ticker": "TSLA", "price": 250.00819507831503, "previous_price": 250.01908715078645,
                 "timestamp": "2026-07-28T20:26:22.329541+00:00", "direction": "down"}
          data: {"ticker": "TSLA", "price": 249.99490502676088, "previous_price": 250.00819507831503,
                 "timestamp": "2026-07-28T20:26:22.830394+00:00", "direction": "down"}
          ```

The original write-up follows.

Steps:    Buy 2 TSLA from the trade bar, confirm the position price is ticking, then
          click `watchlist-remove-TSLA`. Watch `position-price-TSLA` and the connection
          dot.

Expected: A position that is still held keeps being repriced. The watchlist is a display
          preference; it is not a statement about what the portfolio holds.

Actual:   The price freezes at the last value before removal and never moves again, while
          `connection-dot` stays `connected` and every other ticker keeps flashing. The
          header total value, unrealized P&L, the positions row and the heatmap colour all
          silently go stale with nothing to indicate it.

          Playwright, 10s after the removal:

          ```
          Expected: not "250.11"
          Received: "250.11"
            3 x <span data-testid="position-price-TSLA" ... flash-up>250.11</span>
           21 x <span data-testid="position-price-TSLA" ...>250.11</span>
          ```

          At the API, with 2 TSLA held and TSLA removed from the watchlist:

          ```
          $ curl -s localhost:8002/api/portfolio   # 3s after removal
          AAPL 189.8549461557139 -0.13578462722236395
          TSLA 249.77152025286694 0.0
          $ curl -s localhost:8002/api/portfolio   # 5s later
          AAPL 189.8749628212345 -0.1157679617017493
          TSLA 249.77152025286694 0.0
          ```

          The SSE stream keeps re-emitting the identical stale event forever - same price,
          same `previous_price`, and a timestamp frozen at the moment of removal:

          ```
          data: {"ticker": "TSLA", "price": 249.77152025286694,
                 "previous_price": 249.8071563960809,
                 "timestamp": "2026-07-28T20:05:04.540486+00:00", "direction": "down"}
          data: {"ticker": "TSLA", "price": 249.77152025286694,
                 "previous_price": 249.8071563960809,
                 "timestamp": "2026-07-28T20:05:04.540486+00:00", "direction": "down"}
          ```

          Root cause: `get_watchlist_tickers()` in `backend/app/main.py` is the ticker set
          the market source steps, and it returns `get_watchlist()` alone. Once a ticker
          leaves the watchlist the simulator stops stepping it, the cache keeps its last
          entry, and the stream re-pushes that entry indefinitely. The frontend is
          behaving correctly on the data it is given.

Verdict:  product bug. Not flaky - reproduced on every run, at both the UI and the API.

          The fix is one line in a Backend API file: feed the market source the union of
          the watchlist and the tickers currently held. No other layer needs to change,
          and `backend/app/market/` stays closed.

## Notes on the test infrastructure

Three things cost real time and are worth recording so nobody rediscovers them.

- **The app service cannot be called `app`.** `.app` is an HSTS-preloaded gTLD, and
  Chromium force-upgrades a single-label host named `app` to HTTPS, so every navigation
  died with `net::ERR_SSL_PROTOCOL_ERROR at http://app:8001/`. curl and `node fetch` from
  the same container were fine, which is what isolated it to the browser; the same page
  loaded over `http://finally-app:8001` and over the container IP returned 200. The
  compose service is named `finally-app`.

- **`context.setOffline` cannot simulate a backend drop.** It does not abort a response
  that is already streaming, so the SSE connection survived it and the dot stayed green.
  The reconnection spec instead runs a pass-through proxy in front of the app
  (`test/tests/proxy.ts`), destroys its sockets and then answers 503 - which is what a
  restarting server looks like. The dot goes `reconnecting`, the stall watchdog takes it
  to `disconnected`, and it returns to `connected` with prices ticking, no reload.

- **State is shared, so the suite is ordered.** One app instance and one SQLite file mean
  spec files run in numeric order on one worker. `01` asserts the seeded $10,000 and the
  ten default tickers before anything trades; later specs assert relative changes. The
  compose file mounts a tmpfs at `/app/db` so every run genuinely starts empty - running
  against the long-lived `finally-data` volume would break the fresh-start assertions.
