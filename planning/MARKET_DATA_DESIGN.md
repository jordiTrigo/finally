# Market Data Backend — Implementation Design

Implementation-ready design for FinAlly's market data backend, per `PLAN.md` §6. This
document consolidates the conceptual designs in `MARKET_INTERFACE.md` (the unified
interface), `MARKET_SIMULATOR.md` (the GBM simulator), and `MASSIVE_API.md` (the Massive
client) into one concrete, buildable spec with complete code for every module.

A backend engineer should be able to implement the entire market data layer from this
document. Where a design decision is already argued in one of the three source docs, this
document states the decision and gives the code rather than re-arguing it.

## 1. Scope

The market data layer owns:

- A single background task that produces live prices for the current watchlist.
- Two interchangeable price sources — a GBM **simulator** (default) and a **Massive** REST
  poller (when `MASSIVE_API_KEY` is set) — chosen once at startup.
- A shared in-memory **price cache** holding the latest `PriceUpdate` per ticker.
- The **SSE endpoint** (`GET /api/stream/prices`) that streams the cache to the browser.

It does **not** own: the watchlist store (SQLite, owned by the API layer), the portfolio
math, or the LLM. The market layer reads the watchlist through a callback and never writes
to the database.

## 2. Module Layout

```
backend/app/market/
├── __init__.py        # public exports: PriceCache, create_market_data_source, router
├── models.py          # PriceUpdate, ChangeDirection, direction()
├── cache.py           # PriceCache
├── source.py          # MarketDataSource protocol
├── factory.py         # create_market_data_source()
├── seed_prices.py     # seed price / sector table + sector params
├── simulator.py       # SimulatorMarketDataSource (default)
├── massive.py         # MassiveMarketDataSource (MASSIVE_API_KEY set)
└── stream.py          # SSE APIRouter for /api/stream/prices
```

Small, flat package — ten tickers and one model don't justify sub-packages
(`MARKET_SIMULATOR.md` §Code Structure). The simulator and Massive source each live in one
module and share nothing but the `MarketDataSource` shape and the `PriceUpdate` model.

## 3. Dependencies

Add to `backend/pyproject.toml` via `uv add`:

```toml
[project]
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.32",
    "sse-starlette>=2.1",   # EventSourceResponse for the SSE endpoint
    "numpy>=2.1",           # simulator RNG + GBM math
    "massive>=1.0",         # Massive (ex-Polygon) REST client; see MASSIVE_API.md
]
```

`massive` is only imported inside `massive.py`, which is only imported by the factory when
`MASSIVE_API_KEY` is set, so a simulator-only deployment never touches it at runtime — but
it stays a hard dependency to keep the lockfile and image reproducible.

## 4. Data Model — `models.py`

Both sources produce `PriceUpdate`; the SSE layer serializes it verbatim. `direction` is
computed once at construction so nothing downstream recomputes it (`MARKET_INTERFACE.md`
§Data Model).

```python
from dataclasses import dataclass
from enum import Enum


class ChangeDirection(str, Enum):
    UP = "up"
    DOWN = "down"
    FLAT = "flat"


@dataclass(frozen=True)
class PriceUpdate:
    ticker: str
    price: float
    previous_price: float
    timestamp: str  # ISO 8601, UTC
    direction: ChangeDirection


def direction(price: float, previous: float) -> ChangeDirection:
    if price > previous:
        return ChangeDirection.UP
    if price < previous:
        return ChangeDirection.DOWN
    return ChangeDirection.FLAT
```

`ChangeDirection` subclasses `str` so `json.dumps(asdict(update))` serializes it as
`"up"`/`"down"`/`"flat"` with no custom encoder.

## 5. Price Cache — `cache.py`

One instance, created at startup, shared between the source task and every SSE connection
(`MARKET_INTERFACE.md` §Shared Price Cache). In-memory, single-process, no lock: FastAPI
runs one event loop and neither method `await`s mid-mutation, so there's no interleaving to
guard against.

```python
from app.market.models import PriceUpdate


class PriceCache:
    def __init__(self) -> None:
        self._latest: dict[str, PriceUpdate] = {}

    def update(self, price_update: PriceUpdate) -> None:
        self._latest[price_update.ticker] = price_update

    def get(self, ticker: str) -> PriceUpdate | None:
        return self._latest.get(ticker)

    def snapshot(self) -> list[PriceUpdate]:
        return list(self._latest.values())
```

## 6. Source Protocol — `source.py`

A `Protocol`, not an `ABC` — the two sources share a shape, not behavior
(`MARKET_INTERFACE.md` §Abstract Interface). One long-lived coroutine per process, launched
once; ticker changes arrive through the `get_tickers` callback, so a watchlist add/remove
needs no restart. No `stop()` — shutdown is ordinary asyncio task cancellation.

```python
from typing import Protocol, Callable
from app.market.cache import PriceCache


class MarketDataSource(Protocol):
    async def run(
        self, cache: PriceCache, get_tickers: Callable[[], list[str]]
    ) -> None:
        """Run forever, writing PriceUpdates for the current tickers into cache."""
```

## 7. Factory — `factory.py`

Selection happens once, from `MASSIVE_API_KEY` (`PLAN.md` §5). No runtime switching, no
registry — there are exactly two sources.

```python
import os
from app.market.source import MarketDataSource


def create_market_data_source() -> MarketDataSource:
    if os.environ.get("MASSIVE_API_KEY"):
        from app.market.massive import MassiveMarketDataSource
        return MassiveMarketDataSource()
    from app.market.simulator import SimulatorMarketDataSource
    return SimulatorMarketDataSource()
```

Imports are deferred into each branch so choosing the simulator never imports `massive` and
vice versa — keeps startup cheap and avoids importing a client whose credentials aren't set.

## 8. Seed Prices — `seed_prices.py`

Tunable data kept out of the tick logic so prices/sectors/params are easy to adjust
(`MARKET_SIMULATOR.md` §Code Structure). Seed prices approximate real July-2026 levels so
the demo looks plausible on first launch; `mu`/`sigma` are assigned per sector, not per
ticker. These are tuning knobs — shape matters more than the exact numbers.

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class SectorParams:
    mu: float     # annualized drift
    sigma: float  # annualized volatility


# Per-sector GBM params. Tech is noisier than financials; all drift slightly up
# so the market trends upward with noise rather than pure random-walking.
SECTOR_PARAMS: dict[str, SectorParams] = {
    "tech":       SectorParams(mu=0.10, sigma=0.35),
    "financials": SectorParams(mu=0.06, sigma=0.20),
    "media":      SectorParams(mu=0.08, sigma=0.30),
    "unknown":    SectorParams(mu=0.05, sigma=0.25),  # fallback for added tickers
}

# ticker -> (seed_price, sector)
SEED_PRICES: dict[str, tuple[float, str]] = {
    "AAPL":  (190.00, "tech"),
    "GOOGL": (175.00, "tech"),
    "MSFT":  (420.00, "tech"),
    "AMZN":  (185.00, "tech"),
    "TSLA":  (250.00, "tech"),
    "NVDA":  (130.00, "tech"),
    "META":  (560.00, "tech"),
    "JPM":   (210.00, "financials"),
    "V":     (275.00, "financials"),
    "NFLX":  (680.00, "media"),
}

DEFAULT_SEED_PRICE = 100.0  # for a ticker added later with no seed entry


def seed_for(ticker: str) -> tuple[float, str]:
    """Seed price and sector for a ticker, falling back for unknown symbols."""
    return SEED_PRICES.get(ticker, (DEFAULT_SEED_PRICE, "unknown"))
```

## 9. Simulator — `simulator.py`

The default source: geometric Brownian motion with market/sector/idiosyncratic correlation
and occasional dramatic events (`MARKET_SIMULATOR.md`). Fully deterministic given a seed.

### Model recap

Discrete-time GBM per ticker per 500ms tick:

```
price_next = price * exp((mu - 0.5*sigma**2) * dt + sigma * sqrt(dt) * Z)
```

with `dt = 0.5 / (252 * 6.5 * 3600)` (500ms as a fraction of a trading year: 252 days ×
6.5 hours). `Z` combines a market-wide draw, a per-sector draw, and a per-ticker draw so
sector peers and the whole market co-move (`MARKET_SIMULATOR.md` §Correlated Moves).

```python
import asyncio
import math
from dataclasses import dataclass, field
from datetime import datetime, UTC

import numpy as np

from app.market.cache import PriceCache
from app.market.models import PriceUpdate, direction
from app.market.seed_prices import SECTOR_PARAMS, seed_for
from typing import Callable

# 500ms as a fraction of a trading year (252 days x 6.5h x 3600s).
DT = 0.5 / (252 * 6.5 * 3600)

# Correlation weights, normalized so combined Z stays ~N(0,1). See _combine.
W_MARKET, W_SECTOR, W_IDIO = 0.4, 0.3, 0.3

# Occasional dramatic move: probability per ticker per tick, and its size range.
EVENT_PROB = 0.001          # ~a few per ticker per hour at 500ms ticks
EVENT_MIN, EVENT_MAX = 0.02, 0.05  # +/- 2-5% one-off jump


@dataclass
class TickerState:
    price: float
    sector: str


class SimulatorMarketDataSource:
    def __init__(self, seed: int | None = None) -> None:
        self._rng = np.random.default_rng(seed)
        self._state: dict[str, TickerState] = {}

    def _init_state(self, ticker: str) -> TickerState:
        price, sector = seed_for(ticker)
        return TickerState(price=price, sector=sector)

    def _combine(self, z_market: float, z_sector: float, z_idio: float) -> float:
        """Blend the three factors, normalized so variance stays ~1."""
        norm = math.sqrt(W_MARKET**2 + W_SECTOR**2 + W_IDIO**2)
        return (W_MARKET * z_market + W_SECTOR * z_sector + W_IDIO * z_idio) / norm

    def _step(self, state: TickerState, z: float) -> float:
        """One GBM step, plus an occasional event jump."""
        params = SECTOR_PARAMS.get(state.sector, SECTOR_PARAMS["unknown"])
        mu, sigma = params.mu, params.sigma
        drift = (mu - 0.5 * sigma**2) * DT
        shock = sigma * math.sqrt(DT) * z
        new_price = state.price * math.exp(drift + shock)
        if self._rng.random() < EVENT_PROB:
            magnitude = self._rng.uniform(EVENT_MIN, EVENT_MAX)
            sign = 1.0 if self._rng.random() < 0.5 else -1.0
            new_price *= 1.0 + sign * magnitude
        return new_price

    async def run(
        self, cache: PriceCache, get_tickers: Callable[[], list[str]]
    ) -> None:
        while True:
            z_market = self._rng.standard_normal()
            z_sector: dict[str, float] = {}
            for ticker in get_tickers():
                state = self._state.setdefault(ticker, self._init_state(ticker))
                z_sector.setdefault(state.sector, self._rng.standard_normal())
                z = self._combine(
                    z_market, z_sector[state.sector], self._rng.standard_normal()
                )
                new_price = self._step(state, z)
                cache.update(PriceUpdate(
                    ticker=ticker,
                    price=new_price,
                    previous_price=state.price,
                    timestamp=datetime.now(UTC).isoformat(),
                    direction=direction(new_price, state.price),
                ))
                state.price = new_price
            await asyncio.sleep(0.5)
```

Notes:

- One market draw and one draw per sector per tick, reused across every ticker in that
  sector — this is what produces correlation without an explicit covariance matrix.
- A ticker added mid-run is lazily initialized via `setdefault(...)` on the next tick and
  starts producing updates immediately — no restart.
- `seed=None` in production (OS entropy); tests pass a fixed seed for exact-value assertions.

## 10. Massive Source — `massive.py`

Used when `MASSIVE_API_KEY` is set. Polls the multi-ticker snapshot endpoint every
`MASSIVE_POLL_INTERVAL_SECONDS` (default 15s, matching the free tier's 5 req/min) and writes
results into the same cache (`MASSIVE_API.md`, `MARKET_INTERFACE.md` §Massive Implementation).

```python
import asyncio
import logging
import os
from datetime import datetime, UTC
from typing import Callable

from massive import RESTClient

from app.market.cache import PriceCache
from app.market.models import PriceUpdate, direction

logger = logging.getLogger(__name__)


class MassiveMarketDataSource:
    def __init__(self) -> None:
        self._client = RESTClient()  # reads MASSIVE_API_KEY from env
        self._interval = float(os.environ.get("MASSIVE_POLL_INTERVAL_SECONDS", "15"))

    async def run(
        self, cache: PriceCache, get_tickers: Callable[[], list[str]]
    ) -> None:
        while True:
            tickers = get_tickers()
            if tickers:
                await self._poll(cache, tickers)
            await asyncio.sleep(self._interval)

    async def _poll(self, cache: PriceCache, tickers: list[str]) -> None:
        try:
            # Client is synchronous; run off the event loop.
            snapshots = await asyncio.to_thread(
                self._client.get_snapshot_all,
                market_type="stocks",
                tickers=tickers,
            )
        except Exception:
            logger.exception("Massive poll failed; keeping previous cached prices")
            return
        now = datetime.now(UTC).isoformat()
        for snap in snapshots:
            price = snap.last_trade.price if snap.last_trade else snap.day.close
            previous = cache.get(snap.ticker)
            prev_price = previous.price if previous else snap.prev_day.close
            cache.update(PriceUpdate(
                ticker=snap.ticker,
                price=price,
                previous_price=prev_price,
                timestamp=now,
                direction=direction(price, prev_price),
            ))
```

Notes:

- The `massive` client is synchronous, so each poll runs via `asyncio.to_thread` to keep the
  event loop responsive (`MASSIVE_API.md`, `MARKET_INTERFACE.md`).
- A failed poll (network error, HTTP 429 rate limit, bad response) is logged and skipped; the
  cache keeps last-known prices until the next successful poll, so one bad poll never takes
  down the stream.
- `previous_price` comes from the cache's last value, not the API's `prev_day.close`, so two
  consecutive polls with an unchanged price correctly report `FLAT` instead of always
  comparing against yesterday's close.
- Between polls the cache holds the same `PriceUpdate`; the SSE layer re-sends it every 500ms
  (see §11). It is **not** this source's job to emit on the 500ms cadence.
- On the free tier, prices lag the market by ~15 minutes and nothing in the response signals
  it — the UI can't distinguish delayed from real-time (`MASSIVE_API.md` §Rate Limits).

## 11. SSE Endpoint — `stream.py`

The stream reads the cache, never the source — this is what makes the two sources fully
interchangeable (`MARKET_INTERFACE.md` §SSE Streaming). Fixed ~500ms cadence regardless of
how fast the underlying source refreshes: the simulator yields a genuinely new price each
tick; Massive yields the same price (re-sent) between its 15s polls.

```python
import asyncio
import json
from dataclasses import asdict

from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse

router = APIRouter()


@router.get("/api/stream/prices")
async def stream_prices(request: Request):
    cache = request.app.state.price_cache

    async def event_generator():
        while True:
            if await request.is_disconnected():
                break
            for update in cache.snapshot():
                yield {"data": json.dumps(asdict(update))}
            await asyncio.sleep(0.5)

    return EventSourceResponse(event_generator())
```

`sse-starlette`'s `EventSourceResponse` takes a generator yielding dicts and formats the
`data:` / `\n\n` framing, keep-alive pings, and disconnect handling. The client uses the
native `EventSource` API, which reconnects automatically (`PLAN.md` §6, §10). Each event's
payload is exactly the serialized `PriceUpdate`: `ticker`, `price`, `previous_price`,
`timestamp`, `direction`.

## 12. FastAPI Wiring — `main.py`

The source task is launched once in the lifespan handler and cancelled on shutdown. The
cache and a `get_tickers` callback live in `app.state`. `get_tickers` reads the current
watchlist from SQLite so runtime add/remove is picked up on the next source cycle without a
restart.

```python
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.market.cache import PriceCache
from app.market.factory import create_market_data_source
from app.market.stream import router as stream_router
from app.db import get_watchlist_tickers  # owned by the API/DB layer


@asynccontextmanager
async def lifespan(app: FastAPI):
    cache = PriceCache()
    app.state.price_cache = cache

    source = create_market_data_source()
    task = asyncio.create_task(source.run(cache, get_watchlist_tickers))

    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(lifespan=lifespan)
app.include_router(stream_router)
# ... other routers (portfolio, watchlist, chat) included here
```

`get_watchlist_tickers` is a plain `() -> list[str]` supplied by the DB layer. The market
package depends only on that callback signature — it never imports the watchlist model,
keeping the boundary in `PLAN.md` §4 intact. If watchlist reads ever become slow, cache the
ticker list behind the callback; the source calls it once per cycle (every 500ms for the
simulator, every 15s for Massive), so a trivially cheap query is fine at this scale.

## 13. Environment Variables

Consumed by the market layer (full list in `PLAN.md` §5):

| Variable | Default | Effect |
|----------|---------|--------|
| `MASSIVE_API_KEY` | _(unset)_ | Set and non-empty → Massive source; unset/empty → simulator. |
| `MASSIVE_POLL_INTERVAL_SECONDS` | `15` | Massive poll cadence. Lower (2–15s) on a paid plan. Ignored by the simulator. |

## 14. Testing Plan

Per `PLAN.md` §12. Both sources satisfy `MarketDataSource`, so a shared conformance test runs
against each: produces `PriceUpdate`s, populates the cache, tolerates an empty ticker list.

### Shared conformance

```python
import asyncio
import pytest

from app.market.cache import PriceCache
from app.market.models import PriceUpdate
from app.market.simulator import SimulatorMarketDataSource


@pytest.mark.asyncio
async def test_source_populates_cache():
    cache = PriceCache()
    source = SimulatorMarketDataSource(seed=42)
    task = asyncio.create_task(source.run(cache, lambda: ["AAPL", "MSFT"]))
    await asyncio.sleep(0.6)  # let one tick land
    task.cancel()

    snap = cache.snapshot()
    assert {u.ticker for u in snap} == {"AAPL", "MSFT"}
    assert all(isinstance(u, PriceUpdate) and u.price > 0 for u in snap)


@pytest.mark.asyncio
async def test_source_tolerates_empty_watchlist():
    cache = PriceCache()
    source = SimulatorMarketDataSource(seed=1)
    task = asyncio.create_task(source.run(cache, lambda: []))
    await asyncio.sleep(0.6)
    task.cancel()
    assert cache.snapshot() == []
```

### Simulator specifics (deterministic, no mocking)

- **Determinism**: two `SimulatorMarketDataSource(seed=7)` instances stepped identically
  produce identical prices — assert exact values, not ranges.
- **Positivity**: over a long simulated run, every price stays > 0 (GBM guarantees this; the
  test guards against floating-point step accumulation).
- **Correlation**: over many ticks, two same-sector tickers show returns correlation well
  above zero; cross-sector correlation is positive but weaker (the market factor).
- **Lazy add**: a ticker introduced mid-run (the `get_tickers` callback returns a new symbol)
  gets initialized from the seed table and produces updates on the next tick.

### Massive specifics (mock the client)

The HTTP call is the only thing to mock — inject a fake client or monkeypatch
`get_snapshot_all`:

- **Parsing**: a fake snapshot list maps to correct `PriceUpdate`s (`last_trade.price` used,
  falling back to `day.close` when `last_trade` is absent).
- **Cache-on-failure**: when `get_snapshot_all` raises, the previous cache entries are
  unchanged and the task keeps running.
- **FLAT between polls**: two polls returning the same price yield `direction == FLAT` because
  `previous_price` is read from the cache, not `prev_day.close`.

### SSE endpoint

- With a pre-populated cache, `GET /api/stream/prices` emits one `data:` line per cached
  ticker, each a valid `PriceUpdate` JSON with `ticker`, `price`, `previous_price`,
  `timestamp`, `direction`.
- The generator exits cleanly on client disconnect (assert via a mocked `is_disconnected`).
```
