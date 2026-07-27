from typing import Callable, Protocol

from app.market.cache import PriceCache


class MarketDataSource(Protocol):
    async def run(
        self, cache: PriceCache, get_tickers: Callable[[], list[str]]
    ) -> None:
        """Run forever, writing PriceUpdates for the current tickers into cache."""
