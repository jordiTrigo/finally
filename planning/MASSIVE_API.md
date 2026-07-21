# Massive API Reference (formerly Polygon.io)

Reference documentation for the Massive REST API as used in FinAlly, current as of July 2026. Massive is the market-data provider formerly known as Polygon.io — Polygon.io rebranded to Massive on 2025-10-30. Existing Polygon.io API keys and integrations continue to work unchanged.

## Overview

- **Base URL**: `https://api.massive.com` (legacy `https://api.polygon.io` still accepted)
- **Python package**: `massive` — install via `uv add massive`
- **Min Python version**: 3.9+
- **Auth**: API key via the `MASSIVE_API_KEY` env var, or passed explicitly to `RESTClient(api_key=...)`. If neither is set, the client raises `Must specify env var MASSIVE_API_KEY or pass api_key in constructor`.

## Rate Limits and Data Freshness

| Tier | Requests | Data freshness |
|------|----------|-----------------|
| Free (Basic) | 5 requests/minute | End-of-day bars, and **15-minute-delayed** snapshots/quotes/trades |
| Paid | Unlimited (stay under 100 req/s) | Real-time |

This matters for FinAlly: on the free tier, prices returned by Massive are not truly live — they lag the market by ~15 minutes. The app should poll at an interval matched to the free tier's rate limit (`MASSIVE_POLL_INTERVAL_SECONDS`, default 15s — see `PLAN.md` §5), and nothing in the free-tier response indicates the 15-minute lag, so the UI has no way to distinguish it from real-time. Users on a paid plan get true real-time data and can lower the poll interval accordingly.

## Client Initialization

```python
from massive import RESTClient

# Reads MASSIVE_API_KEY from the environment automatically
client = RESTClient()

# Or pass explicitly
client = RESTClient(api_key="your_key_here")
```

## Endpoints Used in FinAlly

### 1. Snapshot — Multiple Tickers (primary polling endpoint)

Gets current prices for a set of tickers in a single API call. This is what the Massive market-data source polls on a timer to refresh the shared price cache (PLAN.md §6).

**REST**: `GET /v2/snapshot/locale/us/markets/stocks/tickers?tickers=AAPL,GOOGL,MSFT`

**Python client**:
```python
snapshots = client.get_snapshot_all(
    market_type="stocks",
    tickers=["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA"],
)

for snap in snapshots:
    print(f"{snap.ticker}: last={snap.last_trade.price} prev_close={snap.prev_day.close}")
```

**Response shape** (`tickers[]` in the raw JSON, `TickerSnapshot` objects in the client):

| Field | Description |
|-------|-------------|
| `ticker` | Symbol |
| `day` | Today's aggregate bar so far: `open`, `high`, `low`, `close`, `volume`, `vwap` |
| `prev_day` | Previous full trading day's bar (same shape as `day`) |
| `min` | Most recent minute bar |
| `last_trade` | `price`, `size`, `exchange`, `timestamp` (present depending on plan) |
| `last_quote` | `bid_price`, `ask_price`, `bid_size`, `ask_size`, `timestamp` |
| `todays_change` / `todays_change_perc` | Change vs. previous close |
| `updated` | Last-updated timestamp (Unix ns) |

**Fields FinAlly extracts**: `last_trade.price` as the current price (falling back to `day.close` if no trade is present), `prev_day.close` to compute the change direction, `updated` for the cache timestamp.

Notes:
- `tickers` is a case-sensitive comma-separated list; an empty value returns the entire market (10,000+ symbols) — always pass the watchlist explicitly to avoid an oversized response.
- Snapshot data resets daily around 3:30 AM ET and repopulates as exchanges report, starting ~4:00 AM ET. Very early in the morning, snapshots may be empty or reflect the prior session.

### 2. Previous Close (end-of-day price)

Used for a ticker's prior-day close, e.g. when a ticker is first added to the watchlist and there's no `prev_day` yet, or for any end-of-day-only reporting.

**REST**: `GET /v2/aggs/ticker/{ticker}/prev`

**Python client**:
```python
prev = client.get_previous_close_agg("AAPL", adjusted=True)
print(f"prev close: {prev.close}, volume: {prev.volume}")
```

**Response shape** (`PreviousCloseAgg`): `ticker`, `open` (`o`), `high` (`h`), `low` (`l`), `close` (`c`), `volume` (`v`), `vwap` (`vw`), `timestamp` (`t`, Unix ms).

`adjusted=True` (the default) returns prices adjusted for splits; set `False` for raw prices.

### 3. Single-Ticker Snapshot (not used for polling, available if needed)

**Python client**: `client.get_snapshot_ticker(market_type="stocks", ticker="AAPL")` — same response shape as one entry from `get_snapshot_all`. FinAlly always polls the full watchlist in one call instead of one call per ticker, to stay within the free tier's 5 requests/minute.

## Error Handling

The client raises `massive.exceptions.BadResponse` (or a plain `HTTPError` depending on client version) for non-2xx responses — e.g. an invalid ticker or a rate-limit rejection (HTTP 429). FinAlly's Massive market-data source should catch these around each poll, log, and leave the previous cached prices in place rather than crashing the background task — a single failed poll should not take down the price stream.

## Reference Docs

- API docs: https://massive.com/docs
- Rebrand announcement: https://massive.com/blog/polygon-is-now-massive
- Python client: https://github.com/massive-com/client-python
