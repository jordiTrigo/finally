"""main.py wiring: the watchlist callback the market source reads, and the snapshot task."""

import asyncio

from app.db import get_snapshots
from app.db.schema import DEFAULT_WATCHLIST
from app.main import get_watchlist_tickers, record_snapshots
from app.market import PriceCache


async def test_watchlist_callback_reads_the_seeded_tickers(cache):
    assert get_watchlist_tickers() == DEFAULT_WATCHLIST


async def test_watchlist_callback_sees_an_edit_without_a_restart(client):
    """An unheld ticker leaves the priced set as soon as it leaves the watchlist."""
    await client.post("/api/watchlist", json={"ticker": "PYPL"})
    await client.delete("/api/watchlist/AAPL")

    tickers = get_watchlist_tickers()

    assert "PYPL" in tickers
    assert "AAPL" not in tickers


async def test_a_held_ticker_stays_priced_after_leaving_the_watchlist(client):
    """Regression: removing a held ticker used to freeze its position price forever."""
    await client.post(
        "/api/portfolio/trade",
        json={"ticker": "AAPL", "side": "buy", "quantity": 2},
    )
    await client.delete("/api/watchlist/AAPL")

    assert "AAPL" in get_watchlist_tickers()


async def test_a_held_ticker_on_the_watchlist_is_listed_once(client):
    await client.post(
        "/api/portfolio/trade",
        json={"ticker": "AAPL", "side": "buy", "quantity": 2},
    )

    assert get_watchlist_tickers() == DEFAULT_WATCHLIST


async def test_a_closed_position_stops_being_priced(client):
    """Selling out removes the only reason to keep pricing an unwatched ticker."""
    await client.post(
        "/api/portfolio/trade",
        json={"ticker": "AAPL", "side": "buy", "quantity": 2},
    )
    await client.delete("/api/watchlist/AAPL")
    await client.post(
        "/api/portfolio/trade",
        json={"ticker": "AAPL", "side": "sell", "quantity": 2},
    )

    assert "AAPL" not in get_watchlist_tickers()


async def test_snapshot_task_records_on_its_cadence(cache, monkeypatch):
    monkeypatch.setattr("app.main.SNAPSHOT_INTERVAL_SECONDS", 0.01)
    task = asyncio.create_task(record_snapshots(PriceCache()))
    await asyncio.sleep(0.05)
    task.cancel()

    snapshots = get_snapshots()

    assert snapshots
    assert snapshots[0]["total_value"] == 10000.0
