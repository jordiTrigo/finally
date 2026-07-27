import asyncio
import logging
import os
from datetime import UTC, datetime
from typing import Callable

from massive import RESTClient

from app.market.cache import PriceCache
from app.market.models import PriceUpdate, compute_direction

logger = logging.getLogger(__name__)

DEFAULT_POLL_INTERVAL_SECONDS = 15.0


def _latest_price(snap) -> float | None:
    """Last trade price, falling back to today's close.

    Snapshot sub-objects are None when the payload omits them, which happens
    around the daily reset (MASSIVE_API.md), so both are optional.
    """
    if snap.last_trade is not None and snap.last_trade.price is not None:
        return snap.last_trade.price
    if snap.day is not None:
        return snap.day.close
    return None


def _previous_close(snap) -> float | None:
    return snap.prev_day.close if snap.prev_day is not None else None


class MassiveMarketDataSource:
    def __init__(self) -> None:
        self._client = RESTClient()  # reads MASSIVE_API_KEY from env
        self._interval = float(
            os.environ.get(
                "MASSIVE_POLL_INTERVAL_SECONDS", str(DEFAULT_POLL_INTERVAL_SECONDS)
            )
        )

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
            self._cache_snapshots(cache, snapshots)
        except Exception:
            logger.exception("Massive poll failed; keeping previous cached prices")

    def _cache_snapshots(self, cache: PriceCache, snapshots) -> None:
        now = datetime.now(UTC).isoformat()
        for snap in snapshots:
            price = _latest_price(snap)
            if price is None:
                logger.warning("Snapshot for %s carries no price; skipping", snap.ticker)
                continue
            cached = cache.get(snap.ticker)
            if cached is not None:
                prev_price = cached.price
            else:
                prev_close = _previous_close(snap)
                prev_price = prev_close if prev_close is not None else price
            cache.update(PriceUpdate(
                ticker=snap.ticker,
                price=price,
                previous_price=prev_price,
                timestamp=now,
                direction=compute_direction(price, prev_price),
            ))
