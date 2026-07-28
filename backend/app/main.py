"""FastAPI application: database init, market data wiring and REST routers."""

import asyncio
import contextlib
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from starlette.exceptions import HTTPException
from starlette.staticfiles import StaticFiles

from app.api import health_router, portfolio_router, watchlist_router
from app.api.chat import router as chat_router
from app.api.valuation import total_value
from app.db import get_positions, get_watchlist, init_db, record_snapshot
from app.market import PriceCache, create_market_data_source
from app.market import router as stream_router

SNAPSHOT_INTERVAL_SECONDS = 30.0
STATIC_DIR = Path(__file__).resolve().parents[1] / "static"


class SPAStaticFiles(StaticFiles):
    """Static files that fall back to index.html so client-side routes resolve.

    An unmatched /api/* path stays a JSON 404 rather than being handed the
    frontend, and any other miss - which StaticFiles answers with the export's
    own 404.html - is replaced by index.html.
    """

    async def get_response(self, path: str, scope):
        if path.startswith("api/"):
            raise HTTPException(status_code=404)
        response = await super().get_response(path, scope)
        if response.status_code == 404:
            return await super().get_response("index.html", scope)
        return response


def get_watchlist_tickers() -> list[str]:
    """Tickers the market source prices: the watchlist plus anything still held.

    Read fresh on every tick, so an edit needs no restart. Held tickers are included
    because the watchlist is a display preference, not a statement about what the
    portfolio holds - dropping one would freeze its position at its last price.
    """
    held = (position["ticker"] for position in get_positions())
    return list(dict.fromkeys([*get_watchlist(), *held]))


async def record_snapshots(cache: PriceCache) -> None:
    """Log total portfolio value on a fixed cadence, feeding the P&L chart."""
    while True:
        await asyncio.sleep(SNAPSHOT_INTERVAL_SECONDS)
        record_snapshot(total_value(cache))


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    cache = PriceCache()
    app.state.price_cache = cache

    source = create_market_data_source()
    tasks = [
        asyncio.create_task(source.run(cache, get_watchlist_tickers)),
        asyncio.create_task(record_snapshots(cache)),
    ]
    try:
        yield
    finally:
        for task in tasks:
            task.cancel()
        for task in tasks:
            with contextlib.suppress(asyncio.CancelledError):
                await task


app = FastAPI(lifespan=lifespan)
app.include_router(stream_router)
app.include_router(health_router)
app.include_router(portfolio_router)
app.include_router(watchlist_router)
app.include_router(chat_router)

# Mounted last so the API routes above win; absent when running from source.
if STATIC_DIR.is_dir():
    app.mount("/", SPAStaticFiles(directory=STATIC_DIR, html=True), name="static")
