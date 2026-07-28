"""Watchlist routes.

The market source reads the same table through `get_watchlist_tickers`, so an add or
remove reaches the price feed on its next tick without a restart.
"""

from fastapi import APIRouter, HTTPException, Request

from app.api.models import TickerOut, TickerRequest, WatchlistOut, WatchlistTickerOut
from app.db import add_to_watchlist, get_watchlist, remove_from_watchlist
from app.market import PriceCache

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])


@router.get("")
async def read_watchlist(request: Request) -> WatchlistOut:
    cache = request.app.state.price_cache
    return WatchlistOut(tickers=[_quote(ticker, cache) for ticker in get_watchlist()])


@router.post("", status_code=201)
async def add_ticker(body: TickerRequest) -> TickerOut:
    if not add_to_watchlist(body.ticker):
        raise HTTPException(409, f"{body.ticker} is already on the watchlist")
    return TickerOut(ticker=body.ticker)


@router.delete("/{ticker}", status_code=204)
async def remove_ticker(ticker: str) -> None:
    if not remove_from_watchlist(ticker):
        raise HTTPException(404, f"{ticker.upper()} is not on the watchlist")


def _quote(ticker: str, cache: PriceCache) -> WatchlistTickerOut:
    """Latest cached price. Prices are null until the source has seen the ticker."""
    update = cache.get(ticker)
    if update is None:
        return WatchlistTickerOut(
            ticker=ticker, price=None, previous_price=None, direction="flat"
        )
    return WatchlistTickerOut(
        ticker=ticker,
        price=update.price,
        previous_price=update.previous_price,
        direction=update.direction,
    )
