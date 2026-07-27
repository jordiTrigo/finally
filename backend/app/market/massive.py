import asyncio
import logging
import os
from datetime import UTC, datetime
from typing import Callable

from massive import RESTClient

from app.market.cache import PriceCache
from app.market.models import PriceUpdate, direction

logger = logging.getLogger(__name__)

DEFAULT_POLL_INTERVAL_SECONDS = 15.0


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
