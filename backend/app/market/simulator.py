import asyncio
import math
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Callable

import numpy as np

from app.market.cache import PriceCache
from app.market.models import PriceUpdate, direction
from app.market.seed_prices import SECTOR_PARAMS, seed_for

# 500ms as a fraction of a trading year (252 days x 6.5h x 3600s).
DT = 0.5 / (252 * 6.5 * 3600)

# Correlation weights, normalized so combined Z stays ~N(0,1). See _combine.
W_MARKET, W_SECTOR, W_IDIO = 0.4, 0.3, 0.3

# Occasional dramatic move: probability per ticker per tick, and its size range.
EVENT_PROB = 0.001          # ~a few per ticker per hour at 500ms ticks
EVENT_MIN, EVENT_MAX = 0.02, 0.05  # +/- 2-5% one-off jump

TICK_INTERVAL_SECONDS = 0.5


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
            await asyncio.sleep(TICK_INTERVAL_SECONDS)
