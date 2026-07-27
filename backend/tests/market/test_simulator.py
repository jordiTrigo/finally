import asyncio
import contextlib

import numpy as np
import pytest

import app.market.simulator as simulator_module
from app.market.cache import PriceCache
from app.market.models import ChangeDirection, PriceUpdate
from app.market.simulator import (
    TICK_INTERVAL_SECONDS,
    SimulatorMarketDataSource,
    TickerState,
)

TICKS_PER_HOUR = int(3600 / TICK_INTERVAL_SECONDS)


@pytest.fixture
def fast_ticks(monkeypatch):
    """Shrink the tick interval so lifecycle tests do not wait on the real cadence."""
    monkeypatch.setattr(simulator_module, "TICK_INTERVAL_SECONDS", 0.01)


class RecordingCache(PriceCache):
    """PriceCache that keeps every update, not just the latest per ticker.

    Sampling the live cache would miss ticks, and the chaining invariant below
    only holds between consecutive updates.
    """

    def __init__(self):
        super().__init__()
        self.history: list[PriceUpdate] = []

    def update(self, price_update: PriceUpdate) -> None:
        self.history.append(price_update)
        super().update(price_update)

    def history_for(self, ticker: str) -> list[PriceUpdate]:
        return [u for u in self.history if u.ticker == ticker]


@contextlib.asynccontextmanager
async def running(source, cache, get_tickers):
    task = asyncio.create_task(source.run(cache, get_tickers))
    try:
        yield task
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


# --- Shared conformance (MarketDataSource protocol) -------------------------


async def test_source_populates_cache(fast_ticks):
    cache = PriceCache()
    source = SimulatorMarketDataSource(seed=42)

    async with running(source, cache, lambda: ["AAPL", "MSFT"]):
        await asyncio.sleep(0.05)

    snap = cache.snapshot()
    assert {u.ticker for u in snap} == {"AAPL", "MSFT"}
    assert all(isinstance(u, PriceUpdate) and u.price > 0 for u in snap)


async def test_source_tolerates_empty_watchlist(fast_ticks):
    cache = PriceCache()
    source = SimulatorMarketDataSource(seed=1)

    async with running(source, cache, lambda: []):
        await asyncio.sleep(0.05)

    assert cache.snapshot() == []


async def test_each_update_chains_previous_price_from_the_prior_tick(fast_ticks):
    """The UI's flash direction depends on this chaining, so pin it down."""
    cache = RecordingCache()
    source = SimulatorMarketDataSource(seed=17)

    async with running(source, cache, lambda: ["AAPL"]):
        await asyncio.sleep(0.1)

    history = cache.history_for("AAPL")
    assert len(history) >= 3, "expected several ticks to land"
    for earlier, later in zip(history, history[1:]):
        assert later.previous_price == earlier.price
        if later.price > earlier.price:
            assert later.direction == ChangeDirection.UP
        elif later.price < earlier.price:
            assert later.direction == ChangeDirection.DOWN
        else:
            assert later.direction == ChangeDirection.FLAT


async def test_first_update_for_a_ticker_starts_from_its_seed_price(fast_ticks):
    cache = RecordingCache()
    source = SimulatorMarketDataSource(seed=8)

    async with running(source, cache, lambda: ["AAPL"]):
        await asyncio.sleep(0.05)

    assert cache.history_for("AAPL")[0].previous_price == 190.00  # SEED_PRICES["AAPL"]


# --- Lazy ticker initialization ----------------------------------------------


async def test_ticker_added_mid_run_is_lazily_initialized(fast_ticks):
    cache = RecordingCache()
    source = SimulatorMarketDataSource(seed=3)
    tickers = ["AAPL"]

    async with running(source, cache, lambda: list(tickers)):
        await asyncio.sleep(0.05)
        assert cache.get("MSFT") is None

        tickers.append("MSFT")
        await asyncio.sleep(0.05)

    history = cache.history_for("MSFT")
    assert history, "ticker added mid-run never produced an update"
    assert history[0].previous_price == 420.00  # seeded from SEED_PRICES, not a default


async def test_unseeded_ticker_uses_the_fallback_seed(fast_ticks):
    """Every user-added symbol outside the default ten takes this path."""
    cache = RecordingCache()
    source = SimulatorMarketDataSource(seed=4)

    async with running(source, cache, lambda: ["ZZZZ"]):
        await asyncio.sleep(0.05)

    assert cache.history_for("ZZZZ")[0].previous_price == 100.0  # DEFAULT_SEED_PRICE


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


# --- Volatility budget -------------------------------------------------------------


def _simulate_ticks(source, states, n_ticks):
    """Drive the same per-tick factor draws that `run` performs, without the clock."""
    prices = {t: [] for t in states}
    for _ in range(n_ticks):
        z_market = source._rng.standard_normal()
        z_sector: dict[str, float] = {}
        for ticker, state in states.items():
            if state.sector not in z_sector:
                z_sector[state.sector] = source._rng.standard_normal()
            z = source._combine(z_market, z_sector[state.sector], source._rng.standard_normal())
            state.price = source._step(state, z)
            prices[ticker].append(state.price)
    return {t: np.diff(np.log(np.array(p))) for t, p in prices.items()}


def test_hourly_volatility_is_consistent_with_the_sector_sigma():
    """A tech ticker at sigma=0.35 should move about 0.9% over a trading hour.

    A trading year is 252 days x 6.5h = 1638 hours, so 0.35 annualized implies
    0.35/sqrt(1638) = 0.87% per hour. Event jumps add to that, but must not
    dominate it - if they do, the GBM parameters stop meaning anything and seed
    prices wander far from their realistic starting levels.
    """
    hourly_returns = []
    for seed in range(40):
        source = SimulatorMarketDataSource(seed=seed)
        state = TickerState(price=190.0, sector="tech")
        _simulate_ticks(source, {"AAPL": state}, TICKS_PER_HOUR)
        hourly_returns.append(state.price / 190.0 - 1.0)

    hourly_std = float(np.std(hourly_returns))
    assert 0.004 < hourly_std < 0.020, f"hourly volatility {hourly_std:.1%} off target ~0.9%"


# --- Correlation -----------------------------------------------------------------


def test_same_sector_tickers_correlate_more_than_cross_sector(monkeypatch):
    """Correlation is a property of the factor model, so measure the diffusion term.

    Event jumps are drawn independently per ticker, so leaving them on measures
    the jump process rather than the correlation structure under test.
    """
    monkeypatch.setattr(simulator_module, "EVENT_PROB", 0.0)
    source = SimulatorMarketDataSource(seed=7)
    tickers = {"AAPL": "tech", "MSFT": "tech", "JPM": "financials"}
    states = {t: TickerState(price=100.0, sector=sector) for t, sector in tickers.items()}

    log_returns = _simulate_ticks(source, states, 5_000)

    same_sector_corr = np.corrcoef(log_returns["AAPL"], log_returns["MSFT"])[0, 1]
    cross_sector_corr = np.corrcoef(log_returns["AAPL"], log_returns["JPM"])[0, 1]

    # Weights imply (0.4^2 + 0.3^2)/0.34 = 0.735 same-sector, 0.4^2/0.34 = 0.471 cross.
    assert same_sector_corr > 0.6
    assert cross_sector_corr > 0.3
    assert same_sector_corr > cross_sector_corr


def test_event_jumps_do_not_swamp_the_correlated_component():
    """Guards the parameter balance that the correlation test above depends on."""
    with_events = _simulate_ticks(
        SimulatorMarketDataSource(seed=11),
        {"AAPL": TickerState(price=100.0, sector="tech"),
         "MSFT": TickerState(price=100.0, sector="tech")},
        20_000,
    )
    corr = np.corrcoef(with_events["AAPL"], with_events["MSFT"])[0, 1]

    assert corr > 0.3, f"events reduced same-sector correlation to {corr:.3f}"
