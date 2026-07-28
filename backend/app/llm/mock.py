"""Deterministic responses for LLM_MOCK=true - no network, no API key.

The mock is a tiny command parser rather than a canned string, so E2E tests can drive a
real trade or a real watchlist edit through the same execution path the model uses.
Tickers must be uppercase; the verb is case-insensitive:

    buy 10 AAPL          sell 2.5 MSFT        buy 3 shares of NVDA
    add PYPL             remove NFLX to/from the watchlist
"""

import os
import re

from app.llm.schemas import ChatResponse, TradeInstruction, WatchlistChange

TRADE_PATTERN = re.compile(
    r"\b((?i:buy|sell))\s+(\d+(?:\.\d+)?)\s+(?:(?i:shares\s+of)\s+)?([A-Z]{1,5})\b"
)
WATCHLIST_PATTERN = re.compile(r"\b((?i:add|remove))\s+([A-Z]{1,5})\b")

IDLE_MESSAGE = (
    "Mock mode: no model was called. Ask me to buy or sell a ticker, for example "
    "'buy 10 AAPL', or to add or remove one, for example 'add PYPL to the watchlist'."
)


def mock_enabled() -> bool:
    """Read at call time so tests and containers can flip it without a restart."""
    return os.environ.get("LLM_MOCK", "").strip().lower() == "true"


def mock_response(user_message: str) -> ChatResponse:
    """The same structured response shape the real model returns."""
    trades = _parse_trades(user_message)
    changes = _parse_watchlist_changes(user_message)
    return ChatResponse(
        message=_summarize(trades, changes),
        trades=trades,
        watchlist_changes=changes,
    )


def _parse_trades(text: str) -> list[TradeInstruction]:
    return [
        TradeInstruction(ticker=ticker, side=verb.lower(), quantity=float(quantity))
        for verb, quantity, ticker in TRADE_PATTERN.findall(text)
    ]


def _parse_watchlist_changes(text: str) -> list[WatchlistChange]:
    return [
        WatchlistChange(ticker=ticker, action=verb.lower())
        for verb, ticker in WATCHLIST_PATTERN.findall(text)
    ]


def _summarize(
    trades: list[TradeInstruction], changes: list[WatchlistChange]
) -> str:
    parts = [f"{t.side} {t.quantity:g} {t.ticker}" for t in trades]
    parts += [f"{c.action} {c.ticker}" for c in changes]
    if not parts:
        return IDLE_MESSAGE
    return f"Mock mode: executing {', '.join(parts)}."
