"""Portfolio routes: valuation, trade execution and snapshot history."""

from fastapi import APIRouter, HTTPException, Request

from app.api.models import HistoryOut, PortfolioOut, TradeOut, TradeRequest
from app.api.valuation import build_portfolio, total_value
from app.db import execute_trade, get_snapshots, record_snapshot

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


@router.get("")
async def read_portfolio(request: Request) -> PortfolioOut:
    return build_portfolio(request.app.state.price_cache)


@router.post("/trade")
async def trade(request: Request, body: TradeRequest) -> TradeOut:
    """Fill a market order at the cache price and snapshot the resulting portfolio."""
    cache = request.app.state.price_cache
    update = cache.get(body.ticker)
    if update is None:
        raise HTTPException(400, f"No price available for {body.ticker}")

    result = execute_trade(body.ticker, body.side, body.quantity, update.price)
    if not result.success:
        raise HTTPException(400, result.error)

    record_snapshot(total_value(cache))
    return TradeOut(**result.trade, cash_balance=result.cash_balance)


@router.get("/history")
async def read_history() -> HistoryOut:
    return HistoryOut(snapshots=get_snapshots())
