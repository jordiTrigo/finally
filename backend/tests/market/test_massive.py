import asyncio
import contextlib
import sys
import types
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

# `massive` is a real PyPI dependency in production, but the test environment
# may not have network access to install it. Inject a stub so this module can
# always be imported; every test below replaces RESTClient with its own fake
# client anyway, so the stub's behavior is never actually exercised.
if "massive" not in sys.modules:
    _stub = types.ModuleType("massive")
    _stub.RESTClient = MagicMock()
    sys.modules["massive"] = _stub

import app.market.massive as massive_module  # noqa: E402
from app.market.cache import PriceCache  # noqa: E402
from app.market.massive import MassiveMarketDataSource  # noqa: E402
from app.market.models import ChangeDirection, PriceUpdate  # noqa: E402


def make_snapshot(ticker, last_trade_price=None, day_close=None, prev_day_close=None):
    return SimpleNamespace(
        ticker=ticker,
        last_trade=SimpleNamespace(price=last_trade_price) if last_trade_price is not None else None,
        day=SimpleNamespace(close=day_close),
        prev_day=SimpleNamespace(close=prev_day_close),
    )


@pytest.fixture
def fake_client():
    return MagicMock()


@pytest.fixture
def source(monkeypatch, fake_client):
    monkeypatch.setattr(massive_module, "RESTClient", lambda *a, **kw: fake_client)
    monkeypatch.delenv("MASSIVE_POLL_INTERVAL_SECONDS", raising=False)
    return MassiveMarketDataSource()


# --- Construction --------------------------------------------------------------


def test_default_poll_interval_is_15_seconds(source):
    assert source._interval == 15.0


def test_poll_interval_reads_env_var(monkeypatch, fake_client):
    monkeypatch.setattr(massive_module, "RESTClient", lambda *a, **kw: fake_client)
    monkeypatch.setenv("MASSIVE_POLL_INTERVAL_SECONDS", "5")
    source = MassiveMarketDataSource()
    assert source._interval == 5.0


# --- Parsing -------------------------------------------------------------------


@pytest.mark.asyncio
async def test_poll_uses_last_trade_price_when_available(source, fake_client):
    fake_client.get_snapshot_all.return_value = [
        make_snapshot("AAPL", last_trade_price=191.5, day_close=190.0, prev_day_close=188.0),
    ]
    cache = PriceCache()

    await source._poll(cache, ["AAPL"])

    update = cache.get("AAPL")
    assert update.ticker == "AAPL"
    assert update.price == 191.5
    assert update.previous_price == 188.0  # no prior cache entry -> falls back to prev_day.close
    assert update.direction == ChangeDirection.UP


@pytest.mark.asyncio
async def test_poll_falls_back_to_day_close_when_no_last_trade(source, fake_client):
    fake_client.get_snapshot_all.return_value = [
        make_snapshot("AAPL", last_trade_price=None, day_close=189.0, prev_day_close=188.0),
    ]
    cache = PriceCache()

    await source._poll(cache, ["AAPL"])

    assert cache.get("AAPL").price == 189.0


@pytest.mark.asyncio
async def test_poll_passes_watchlist_tickers_to_client(source, fake_client):
    fake_client.get_snapshot_all.return_value = []
    cache = PriceCache()

    await source._poll(cache, ["AAPL", "MSFT"])

    fake_client.get_snapshot_all.assert_called_once_with(
        market_type="stocks", tickers=["AAPL", "MSFT"]
    )


# --- Cache-on-failure ------------------------------------------------------------


@pytest.mark.asyncio
async def test_poll_keeps_previous_cache_entry_on_failure(source, fake_client):
    cache = PriceCache()
    cache.update(PriceUpdate(
        ticker="AAPL", price=100.0, previous_price=99.0,
        timestamp="t0", direction=ChangeDirection.UP,
    ))
    fake_client.get_snapshot_all.side_effect = RuntimeError("network error")

    await source._poll(cache, ["AAPL"])

    update = cache.get("AAPL")
    assert update.price == 100.0


@pytest.mark.asyncio
async def test_run_keeps_polling_after_a_failed_poll(source, fake_client):
    fake_client.get_snapshot_all.side_effect = RuntimeError("boom")
    source._interval = 0.05
    cache = PriceCache()

    task = asyncio.create_task(source.run(cache, lambda: ["AAPL"]))
    await asyncio.sleep(0.2)
    assert not task.done()

    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task

    assert fake_client.get_snapshot_all.call_count >= 2


# --- FLAT direction between unchanged polls --------------------------------------


@pytest.mark.asyncio
async def test_direction_is_flat_when_price_unchanged_between_polls(source, fake_client):
    cache = PriceCache()
    fake_client.get_snapshot_all.return_value = [
        make_snapshot("AAPL", last_trade_price=190.0, day_close=190.0, prev_day_close=188.0),
    ]

    await source._poll(cache, ["AAPL"])
    first = cache.get("AAPL")
    assert first.price == 190.0
    assert first.direction == ChangeDirection.UP  # vs. prev_day.close=188.0

    await source._poll(cache, ["AAPL"])
    second = cache.get("AAPL")
    assert second.previous_price == first.price  # read from cache, not prev_day.close
    assert second.direction == ChangeDirection.FLAT


# --- Empty watchlist ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_skips_poll_when_watchlist_is_empty(source, fake_client):
    source._interval = 0.05
    cache = PriceCache()

    task = asyncio.create_task(source.run(cache, lambda: []))
    await asyncio.sleep(0.15)
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task

    fake_client.get_snapshot_all.assert_not_called()
