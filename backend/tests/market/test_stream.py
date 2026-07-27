import json
from types import SimpleNamespace

import pytest
from sse_starlette.sse import EventSourceResponse

import app.market.stream as stream_module
from app.market.cache import PriceCache
from app.market.models import ChangeDirection, PriceUpdate
from app.market.stream import price_event_generator, stream_prices


class FakeRequest:
    """Mimics the subset of `fastapi.Request` the stream endpoint touches."""

    def __init__(self, app=None, disconnect_after: int | None = None):
        self.app = app
        self._calls = 0
        self._disconnect_after = disconnect_after

    async def is_disconnected(self) -> bool:
        self._calls += 1
        if self._disconnect_after is None:
            return False
        return self._calls > self._disconnect_after


def make_update(ticker: str, price: float, previous: float, direction: ChangeDirection) -> PriceUpdate:
    return PriceUpdate(
        ticker=ticker,
        price=price,
        previous_price=previous,
        timestamp="2026-01-01T00:00:00+00:00",
        direction=direction,
    )


async def test_generator_emits_one_event_per_cached_ticker():
    cache = PriceCache()
    cache.update(make_update("AAPL", 190.0, 189.0, ChangeDirection.UP))
    cache.update(make_update("MSFT", 420.0, 420.0, ChangeDirection.FLAT))
    request = FakeRequest()

    gen = price_event_generator(request, cache)
    events = [await gen.__anext__() for _ in range(2)]

    payloads = [json.loads(e["data"]) for e in events]
    tickers = {p["ticker"] for p in payloads}
    assert tickers == {"AAPL", "MSFT"}
    for payload in payloads:
        assert set(payload.keys()) == {"ticker", "price", "previous_price", "timestamp", "direction"}


async def test_generator_exits_cleanly_on_disconnect():
    cache = PriceCache()
    cache.update(make_update("AAPL", 190.0, 189.0, ChangeDirection.UP))
    request = FakeRequest(disconnect_after=0)  # already disconnected

    gen = price_event_generator(request, cache)

    with pytest.raises(StopAsyncIteration):
        await gen.__anext__()


async def test_generator_re_reads_cache_snapshot_each_cycle(monkeypatch):
    monkeypatch.setattr(stream_module, "SSE_INTERVAL_SECONDS", 0.01)
    cache = PriceCache()
    cache.update(make_update("AAPL", 190.0, 189.0, ChangeDirection.UP))
    request = FakeRequest()
    gen = price_event_generator(request, cache)

    first_event = await gen.__anext__()
    assert json.loads(first_event["data"])["price"] == 190.0

    cache.update(make_update("AAPL", 191.0, 190.0, ChangeDirection.UP))
    second_event = await gen.__anext__()
    assert json.loads(second_event["data"])["price"] == 191.0


async def test_stream_prices_route_streams_the_cache_held_in_app_state():
    cache = PriceCache()
    cache.update(make_update("AAPL", 190.0, 189.0, ChangeDirection.UP))
    app = SimpleNamespace(state=SimpleNamespace(price_cache=cache))
    request = FakeRequest(app=app)

    response = await stream_prices(request)
    first_event = await response.body_iterator.__anext__()

    assert isinstance(response, EventSourceResponse)
    assert json.loads(first_event["data"])["ticker"] == "AAPL"
