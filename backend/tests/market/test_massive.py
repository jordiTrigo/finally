import asyncio
import contextlib
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import app.market.massive as massive_module
from app.market.cache import PriceCache
from app.market.massive import MassiveMarketDataSource
from app.market.models import ChangeDirection, PriceUpdate


ABSENT = object()
"""Marks a sub-object omitted from the payload, which the real client maps to None."""


def make_snapshot(ticker, last_trade_price=None, day_close=ABSENT, prev_day_close=ABSENT):
    """Mirror `massive.rest.models.snapshot.TickerSnapshot`.

    Verified against massive 2.8.0: `TickerSnapshot.from_dict({"ticker": "AAPL"})`
    leaves `last_trade`, `day` and `prev_day` as None, so absent sub-objects are
    None rather than objects holding None.
    """
    return SimpleNamespace(
        ticker=ticker,
        last_trade=SimpleNamespace(price=last_trade_price) if last_trade_price is not None else None,
        day=None if day_close is ABSENT else SimpleNamespace(close=day_close),
        prev_day=None if prev_day_close is ABSENT else SimpleNamespace(close=prev_day_close),
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


async def test_poll_falls_back_to_day_close_when_no_last_trade(source, fake_client):
    fake_client.get_snapshot_all.return_value = [
        make_snapshot("AAPL", last_trade_price=None, day_close=189.0, prev_day_close=188.0),
    ]
    cache = PriceCache()

    await source._poll(cache, ["AAPL"])

    assert cache.get("AAPL").price == 189.0


async def test_poll_passes_watchlist_tickers_to_client(source, fake_client):
    fake_client.get_snapshot_all.return_value = []
    cache = PriceCache()

    await source._poll(cache, ["AAPL", "MSFT"])

    fake_client.get_snapshot_all.assert_called_once_with(
        market_type="stocks", tickers=["AAPL", "MSFT"]
    )


# --- Cache-on-failure ------------------------------------------------------------


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


# --- Malformed / partial snapshots -----------------------------------------------
#
# MASSIVE_API.md: snapshot data resets around 3:30 AM ET and repopulates as exchanges
# report, so a poll can legitimately return entries with no price fields at all.


async def test_poll_skips_snapshot_with_no_price_and_keeps_the_rest(source, fake_client):
    fake_client.get_snapshot_all.return_value = [
        make_snapshot("AAPL"),  # no last_trade, no day bar
        make_snapshot("MSFT", last_trade_price=420.0, prev_day_close=418.0),
    ]
    cache = PriceCache()

    await source._poll(cache, ["AAPL", "MSFT"])

    assert cache.get("AAPL") is None
    assert cache.get("MSFT").price == 420.0


async def test_poll_reports_flat_when_prev_day_absent_and_ticker_is_new(source, fake_client):
    fake_client.get_snapshot_all.return_value = [
        make_snapshot("AAPL", last_trade_price=191.5),  # no prev_day to compare against
    ]
    cache = PriceCache()

    await source._poll(cache, ["AAPL"])

    update = cache.get("AAPL")
    assert update.price == 191.5
    assert update.previous_price == 191.5
    assert update.direction == ChangeDirection.FLAT


async def test_run_keeps_polling_after_a_malformed_snapshot(source, fake_client):
    """A partial payload must not kill the background task and freeze prices forever."""
    fake_client.get_snapshot_all.return_value = [make_snapshot("AAPL")]
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


async def test_poll_leaves_a_requested_ticker_absent_when_the_api_omits_it(source, fake_client):
    """The API may not return every requested symbol; the rest must still cache."""
    fake_client.get_snapshot_all.return_value = [
        make_snapshot("AAPL", last_trade_price=191.5, prev_day_close=188.0),
    ]
    cache = PriceCache()

    await source._poll(cache, ["AAPL", "MSFT"])

    assert cache.get("AAPL").price == 191.5
    assert cache.get("MSFT") is None


async def test_run_skips_poll_when_watchlist_is_empty(source, fake_client):
    source._interval = 0.05
    cache = PriceCache()

    task = asyncio.create_task(source.run(cache, lambda: []))
    await asyncio.sleep(0.15)
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task

    fake_client.get_snapshot_all.assert_not_called()
