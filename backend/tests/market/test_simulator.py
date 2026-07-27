import asyncio
import contextlib

import numpy as np
import pytest

from app.market.cache import PriceCache
from app.market.models import PriceUpdate
from app.market.simulator import SimulatorMarketDataSource, TickerState


# --- Shared conformance (MarketDataSource protocol) -------------------------


@pytest.mark.asyncio
async def test_source_populates_cache():
    cache = PriceCache()
    source = SimulatorMarketDataSource(seed=42)
    task = asyncio.create_task(source.run(cache, lambda: ["AAPL", "MSFT"]))
    await asyncio.sleep(0.6)  # let one tick land
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task

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
    with contextlib.suppress(asyncio.CancelledError):
        await task
    assert cache.snapshot() == []


# --- Lazy ticker initialization ----------------------------------------------


@pytest.mark.asyncio
async def test_ticker_added_mid_run_is_lazily_initialized():
    cache = PriceCache()
    source = SimulatorMarketDataSource(seed=3)
    tickers = ["AAPL"]
    task = asyncio.create_task(source.run(cache, lambda: list(tickers)))
    await asyncio.sleep(0.6)
    assert cache.get("MSFT") is None

    tickers.append("MSFT")
    await asyncio.sleep(0.6)
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task

    update = cache.get("MSFT")
    assert update is not None
    assert update.price > 0


# --- Determinism --------------------------------------------------------------


def test_step_is_deterministic_given_seed():
    """Two identically-seeded instances stepped identically produce identical prices."""
    source_a = SimulatorMarketDataSource(seed=99)
    source_b = SimulatorMarketDataSource(seed=99)
    state_a = TickerState(price=100.0, sector="tech")
    state_b = TickerState(price=100.0, sector="tech")

    for _ in range(500):
        z_a = source_a._rng.standard_normal()
        z_b = source_b._rng.standard_normal()
        assert z_a == z_b

        price_a = source_a._step(state_a, z_a)
        price_b = source_b._step(state_b, z_b)
        assert price_a == price_b

        state_a.price = price_a
        state_b.price = price_b


def test_different_seeds_diverge():
    source_a = SimulatorMarketDataSource(seed=1)
    source_b = SimulatorMarketDataSource(seed=2)
    state_a = TickerState(price=100.0, sector="tech")
    state_b = TickerState(price=100.0, sector="tech")

    for _ in range(50):
        price_a = source_a._step(state_a, source_a._rng.standard_normal())
        price_b = source_b._step(state_b, source_b._rng.standard_normal())
        state_a.price = price_a
        state_b.price = price_b

    assert state_a.price != state_b.price


# --- Positivity ----------------------------------------------------------------


def test_prices_stay_positive_over_long_run():
    source = SimulatorMarketDataSource(seed=123)
    state = TickerState(price=100.0, sector="tech")

    for _ in range(20_000):
        z = source._combine(
            source._rng.standard_normal(),
            source._rng.standard_normal(),
            source._rng.standard_normal(),
        )
        new_price = source._step(state, z)
        assert new_price > 0
        state.price = new_price


# --- Correlation -----------------------------------------------------------------


def test_same_sector_tickers_correlate_more_than_cross_sector():
    source = SimulatorMarketDataSource(seed=7)
    tickers = {"AAPL": "tech", "MSFT": "tech", "JPM": "financials"}
    states = {t: TickerState(price=100.0, sector=sector) for t, sector in tickers.items()}
    prices = {t: [] for t in tickers}

    n_ticks = 5_000
    for _ in range(n_ticks):
        z_market = source._rng.standard_normal()
        z_sector: dict[str, float] = {}
        for ticker, state in states.items():
            z_sector.setdefault(state.sector, source._rng.standard_normal())
            z = source._combine(z_market, z_sector[state.sector], source._rng.standard_normal())
            new_price = source._step(state, z)
            prices[ticker].append(new_price)
            state.price = new_price

    log_returns = {
        t: np.diff(np.log(np.array(p))) for t, p in prices.items()
    }
    same_sector_corr = np.corrcoef(log_returns["AAPL"], log_returns["MSFT"])[0, 1]
    cross_sector_corr = np.corrcoef(log_returns["AAPL"], log_returns["JPM"])[0, 1]

    assert same_sector_corr > 0.3
    assert cross_sector_corr > 0.05
    assert same_sector_corr > cross_sector_corr
