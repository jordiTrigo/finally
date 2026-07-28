"""Portfolio valuation: holdings marked to the shared price cache."""

from app.api.models import PortfolioOut, PositionOut
from app.db import get_cash_balance, get_positions
from app.market import PriceCache


def build_portfolio(cache: PriceCache) -> PortfolioOut:
    """Positions marked to market, plus cash and the derived totals."""
    cash = get_cash_balance()
    positions = [_value_position(position, cache) for position in get_positions()]
    positions_value = sum(position.market_value for position in positions)
    return PortfolioOut(
        cash_balance=cash,
        positions=positions,
        positions_value=positions_value,
        total_value=cash + positions_value,
        total_unrealized_pnl=sum(position.unrealized_pnl for position in positions),
    )


def total_value(cache: PriceCache) -> float:
    """Total portfolio value, as written to the snapshot log."""
    return build_portfolio(cache).total_value


def _value_position(position: dict, cache: PriceCache) -> PositionOut:
    """Mark one holding to market.

    A ticker the cache has not seen yet - the window between startup and the first
    tick - is valued at its average cost, so totals stay numeric and P&L reads zero.
    """
    update = cache.get(position["ticker"])
    price = update.price if update else position["avg_cost"]
    quantity = position["quantity"]
    market_value = quantity * price
    cost_basis = quantity * position["avg_cost"]
    unrealized_pnl = market_value - cost_basis
    return PositionOut(
        ticker=position["ticker"],
        quantity=quantity,
        avg_cost=position["avg_cost"],
        current_price=price,
        market_value=market_value,
        unrealized_pnl=unrealized_pnl,
        pnl_percent=unrealized_pnl / cost_basis * 100,
    )
