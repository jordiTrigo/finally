# Market Data Interface Design

Design for the unified Python market-data layer described in `PLAN.md` §6. One abstract interface, two implementations (simulator, Massive), selected once at startup by an environment variable. Everything downstream — the shared price cache and the SSE stream — talks to the interface only and is agnostic to which implementation is running.

## Goals

- The simulator and the Massive-backed source must be interchangeable: same inputs, same output shape, same lifecycle.
- Selection happens once, at process startup, from `MASSIVE_API_KEY` (see `PLAN.md` §5) — no runtime switching.
- The watchlist can change while the app is running (tickers added/removed via `/api/watchlist`), so a source must pick up ticker changes without a restart.
- Keep it small: one interface, one cache, one factory function. No plugin registry, no config file — this project has exactly two sources.

## Data Model

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
    timestamp: str  # ISO 8601
    direction: ChangeDirection
```

`PriceUpdate` is what both sources produce and what the SSE stream serializes per `PLAN.md` §6 ("ticker, price, previous price, timestamp, and change direction"). `direction` is derived once when the update is created (`UP` if `price > previous_price`, `DOWN` if less, `FLAT` if equal), so nothing downstream recomputes it.

## Abstract Interface

```python
from typing import Protocol, Callable


class MarketDataSource(Protocol):
    async def run(self, cache: "PriceCache", get_tickers: Callable[[], list[str]]) -> None:
        """Run forever, writing PriceUpdates for the current ticker set into cache."""
```

- `get_tickers` is a callback rather than a fixed list because the watchlist can change at runtime; each source re-reads it on every cycle so newly added tickers start appearing without a restart.
- `run` is a single long-lived coroutine, launched once as a FastAPI background task at startup, not one task per ticker. This matches both implementations naturally: the simulator ticks its whole universe together, and Massive polls all tickers in one snapshot call.
- There is no `stop()` on the protocol — the task is cancelled via normal asyncio task cancellation on app shutdown (`asyncio.CancelledError` propagates out of `run`).

A `Protocol` rather than an `ABC` — there's no shared base behavior between the two sources worth inheriting, only a shared shape.

## Shared Price Cache

```python
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

- One `PriceCache` instance, created at startup, held in app state, and shared between the background source task and every SSE connection.
- In-memory only, per `PLAN.md` §6 — no persistence, no cross-process concerns, since this is single-user and single-process.
- Plain dict + no lock: FastAPI's default async model runs one event loop; `update`/`snapshot` don't `await` mid-mutation, so there's no interleaving to guard against. If the app ever moves to multiple worker processes this stops being true, but that's out of scope here.

## Factory

```python
import os


def create_market_data_source() -> MarketDataSource:
    if os.environ.get("MASSIVE_API_KEY"):
        return MassiveMarketDataSource()
    return SimulatorMarketDataSource()
```

Called once at FastAPI startup. The chosen source's `run()` is scheduled as a background task; the FastAPI lifespan handler cancels it on shutdown.

## Simulator Implementation (shape only — see `MARKET_SIMULATOR.md` for the model)

```python
class SimulatorMarketDataSource:
    async def run(self, cache: PriceCache, get_tickers: Callable[[], list[str]]) -> None:
        state = self._init_state(get_tickers())
        while True:
            for ticker in get_tickers():
                update = self._next_tick(ticker, state)
                cache.update(update)
            await asyncio.sleep(0.5)
```

Ticks every ~500ms per `PLAN.md` §6. New tickers are picked up each loop iteration via `get_tickers()`; state for a never-seen ticker is initialized lazily from its seed price.

## Massive Implementation (shape only — see `MASSIVE_API.md` for the client)

```python
class MassiveMarketDataSource:
    def __init__(self) -> None:
        self._client = RESTClient()  # reads MASSIVE_API_KEY
        self._interval = float(os.environ.get("MASSIVE_POLL_INTERVAL_SECONDS", "15"))

    async def run(self, cache: PriceCache, get_tickers: Callable[[], list[str]]) -> None:
        while True:
            tickers = get_tickers()
            if tickers:
                await self._poll(cache, tickers)
            await asyncio.sleep(self._interval)

    async def _poll(self, cache: PriceCache, tickers: list[str]) -> None:
        try:
            snapshots = await asyncio.to_thread(
                self._client.get_snapshot_all, market_type="stocks", tickers=tickers
            )
        except Exception:
            logger.exception("Massive poll failed, keeping previous prices")
            return
        now = datetime.now(UTC).isoformat()
        for snap in snapshots:
            previous = cache.get(snap.ticker)
            price = snap.last_trade.price if snap.last_trade else snap.day.close
            prev_price = previous.price if previous else snap.prev_day.close
            cache.update(PriceUpdate(
                ticker=snap.ticker,
                price=price,
                previous_price=prev_price,
                timestamp=now,
                direction=_direction(price, prev_price),
            ))
```

- The Massive client is synchronous, so the poll runs via `asyncio.to_thread` to avoid blocking the event loop.
- A failed poll (network error, rate limit, bad response) is logged and skipped — the cache simply keeps last-known prices until the next successful poll, per `MASSIVE_API.md`'s error-handling note.
- `previous_price` is taken from the cache's last value, not from the API's `prev_day.close`, so that consecutive polls with an unchanged price correctly report `FLAT` rather than comparing against yesterday's close every time.
- Between polls, the cache holds the same `PriceUpdate` — the SSE layer re-sends it with `direction=FLAT` on every tick per `PLAN.md` §6, rather than this source pushing updates on its own faster cadence.

## SSE Streaming Reads the Cache, Not the Source

```python
@router.get("/api/stream/prices")
async def stream_prices(request: Request):
    async def event_generator():
        while not await request.is_disconnected():
            for update in cache.snapshot():
                yield f"data: {json.dumps(asdict(update))}\n\n"
            await asyncio.sleep(0.5)

    return EventSourceResponse(event_generator())
```

The stream's cadence (~500ms) is independent of either source's update cadence — it just reads whatever `PriceCache.snapshot()` currently holds. This is what makes the two sources fully interchangeable: the stream never knows or cares whether the cache is being refreshed every 500ms (simulator) or every 15s (Massive free tier).

## Testing Implications

- Both implementations satisfy the same `MarketDataSource` protocol, so unit tests can run one shared conformance test against each (produces `PriceUpdate`s, populates the cache, tolerates an empty ticker list).
- The Massive source's HTTP call is the only part that needs mocking — inject a fake client or monkeypatch `get_snapshot_all` to test polling, caching-on-failure, and `FLAT` direction between unchanged polls.
- The simulator is fully deterministic if seeded (see `MARKET_SIMULATOR.md`), so its tests don't need mocking at all.
