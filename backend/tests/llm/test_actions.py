"""Auto-execution: trades and watchlist edits, including the ones that get rejected."""

from app.db import get_cash_balance, get_position, get_snapshots, get_watchlist
from app.llm.actions import execute_actions
from app.llm.schemas import ChatResponse, TradeInstruction, WatchlistChange


def response(**kwargs) -> ChatResponse:
    return ChatResponse(message="ok", **kwargs)


def test_trade_executes_at_the_cache_price(cache):
    actions = execute_actions(
        response(trades=[TradeInstruction(ticker="AAPL", side="buy", quantity=10)]),
        cache,
    )

    assert actions[0].type == "trade"
    assert actions[0].status == "executed"
    assert actions[0].detail == "buy 10 AAPL filled at $190.00"
    assert get_position("AAPL")["quantity"] == 10
    assert get_cash_balance() == 10000.0 - 1900.0


def test_trade_records_a_snapshot(cache):
    execute_actions(
        response(trades=[TradeInstruction(ticker="AAPL", side="buy", quantity=1)]), cache
    )
    assert len(get_snapshots()) == 1


def test_rejected_trade_is_reported_not_raised(cache):
    actions = execute_actions(
        response(trades=[TradeInstruction(ticker="AAPL", side="buy", quantity=1000)]),
        cache,
    )

    assert actions[0].status == "failed"
    assert "Insufficient cash" in actions[0].detail
    assert get_position("AAPL") is None
    assert get_cash_balance() == 10000.0


def test_sell_without_shares_is_reported(cache):
    actions = execute_actions(
        response(trades=[TradeInstruction(ticker="MSFT", side="sell", quantity=5)]), cache
    )
    assert actions[0].status == "failed"
    assert "Insufficient shares" in actions[0].detail


def test_trade_on_an_unpriced_ticker_is_reported(cache):
    actions = execute_actions(
        response(trades=[TradeInstruction(ticker="ZZZZ", side="buy", quantity=1)]), cache
    )
    assert actions[0].status == "failed"
    assert actions[0].detail == "buy 1 ZZZZ rejected: no price available"


def test_a_failed_trade_does_not_stop_the_next_one(cache):
    actions = execute_actions(
        response(
            trades=[
                TradeInstruction(ticker="AAPL", side="buy", quantity=1000),
                TradeInstruction(ticker="AAPL", side="buy", quantity=2),
            ]
        ),
        cache,
    )

    assert [action.status for action in actions] == ["failed", "executed"]
    assert get_position("AAPL")["quantity"] == 2


def test_watchlist_add_and_remove(cache):
    actions = execute_actions(
        response(
            watchlist_changes=[
                WatchlistChange(ticker="PYPL", action="add"),
                WatchlistChange(ticker="NFLX", action="remove"),
            ]
        ),
        cache,
    )

    assert [action.status for action in actions] == ["executed", "executed"]
    assert actions[0].detail == "Added PYPL to the watchlist"
    assert "PYPL" in get_watchlist()
    assert "NFLX" not in get_watchlist()


def test_duplicate_add_and_missing_remove_are_reported(cache):
    actions = execute_actions(
        response(
            watchlist_changes=[
                WatchlistChange(ticker="AAPL", action="add"),
                WatchlistChange(ticker="ZZZZ", action="remove"),
            ]
        ),
        cache,
    )

    assert [action.status for action in actions] == ["failed", "failed"]
    assert actions[0].detail == "AAPL is already on the watchlist"
    assert actions[1].detail == "ZZZZ is not on the watchlist"


def test_no_actions_yields_no_records(cache):
    assert execute_actions(response(), cache) == []
