"""Portfolio context: what the model knows about the account when it answers."""

from app.api.models import PortfolioOut, PositionOut
from app.api.valuation import build_portfolio
from app.db import get_watchlist
from app.market import PriceCache


def build_context(cache: PriceCache) -> str:
    """Cash, positions with P&L, watchlist quotes and totals, as plain text."""
    portfolio = build_portfolio(cache)
    return "\n".join(
        [
            "Current account state:",
            f"Cash: ${portfolio.cash_balance:,.2f}",
            f"Positions value: ${portfolio.positions_value:,.2f}",
            f"Total portfolio value: ${portfolio.total_value:,.2f}",
            f"Total unrealized P&L: ${portfolio.total_unrealized_pnl:,.2f}",
            "",
            _positions_block(portfolio),
            "",
            _watchlist_block(cache),
        ]
    )


def _positions_block(portfolio: PortfolioOut) -> str:
    if not portfolio.positions:
        return "Positions: none. The account is all cash."
    lines = [_position_line(position) for position in portfolio.positions]
    return "\n".join(["Positions:", *lines])


def _position_line(position: PositionOut) -> str:
    return (
        f"- {position.ticker}: {position.quantity:g} shares, "
        f"avg cost ${position.avg_cost:,.2f}, now ${position.current_price:,.2f}, "
        f"value ${position.market_value:,.2f}, "
        f"P&L ${position.unrealized_pnl:,.2f} ({position.pnl_percent:+.2f}%)"
    )


def _watchlist_block(cache: PriceCache) -> str:
    quotes = [_quote(ticker, cache) for ticker in get_watchlist()]
    return f"Watchlist: {', '.join(quotes) if quotes else 'empty'}"


def _quote(ticker: str, cache: PriceCache) -> str:
    """A ticker the cache has not seen yet has no price to report."""
    update = cache.get(ticker)
    return f"{ticker} ${update.price:,.2f}" if update else f"{ticker} (no price yet)"
