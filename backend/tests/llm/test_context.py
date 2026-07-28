"""The portfolio context handed to the model with every message."""

from app.db import execute_trade
from app.llm.context import build_context
from app.llm.prompt import SYSTEM_PROMPT, build_messages


def test_all_cash_account(cache):
    context = build_context(cache)

    assert "Cash: $10,000.00" in context
    assert "Total portfolio value: $10,000.00" in context
    assert "Positions: none. The account is all cash." in context


def test_positions_carry_price_and_pnl(cache):
    execute_trade("AAPL", "buy", 10, 180.0)

    context = build_context(cache)

    assert "Cash: $8,200.00" in context
    assert (
        "- AAPL: 10 shares, avg cost $180.00, now $190.00, value $1,900.00, "
        "P&L $100.00 (+5.56%)" in context
    )
    assert "Total portfolio value: $10,100.00" in context


def test_watchlist_shows_live_prices_and_gaps(cache):
    context = build_context(cache)

    assert "AAPL $190.00" in context
    assert "MSFT $400.00" in context
    assert "GOOGL (no price yet)" in context


def test_messages_put_context_in_the_system_turn_and_history_before_the_user(cache):
    history = [
        {"role": "user", "content": "what do I hold?"},
        {"role": "assistant", "content": "all cash"},
    ]

    messages = build_messages("buy something", history, build_context(cache))

    assert messages[0]["role"] == "system"
    assert SYSTEM_PROMPT in messages[0]["content"]
    assert "Cash: $10,000.00" in messages[0]["content"]
    assert messages[1:3] == history
    assert messages[3] == {"role": "user", "content": "buy something"}
