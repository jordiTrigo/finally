"""FastAPI application: market data wiring per MARKET_DATA_DESIGN.md section 12."""

import asyncio
import contextlib
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.market import PriceCache, create_market_data_source
from app.market import router as stream_router

# PLAN.md section 7 seeds these ten tickers into SQLite. Until the DB layer lands,
# the callback serves them directly - the market layer only needs `() -> list[str]`,
# so swapping in `app.db.get_watchlist_tickers` later touches nothing else.
DEFAULT_WATCHLIST = [
    "AAPL", "GOOGL", "MSFT", "AMZN", "TSLA", "NVDA", "META", "JPM", "V", "NFLX",
]


def get_watchlist_tickers() -> list[str]:
    return list(DEFAULT_WATCHLIST)


@asynccontextmanager
async def lifespan(app: FastAPI):
    cache = PriceCache()
    app.state.price_cache = cache

    source = create_market_data_source()
    task = asyncio.create_task(source.run(cache, get_watchlist_tickers))
    try:
        yield
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


app = FastAPI(lifespan=lifespan)
app.include_router(stream_router)
