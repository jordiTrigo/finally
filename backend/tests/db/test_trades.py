import pytest

from app.db import (
    execute_trade,
    get_cash_balance,
    get_position,
    get_positions,
    get_trades,
)


def test_buy_deducts_cash_and_opens_position(db):
    result = execute_trade("AAPL", "buy", 10, 100.0)
    assert result.success is True
    assert result.cash_balance == 9000.0
    assert get_cash_balance() == 9000.0
    position = get_position("AAPL")
    assert position["quantity"] == 10
    assert position["avg_cost"] == 100.0


def test_buy_returns_the_trade_row(db):
    trade = execute_trade("AAPL", "buy", 10, 100.0).trade
    assert trade["ticker"] == "AAPL"
    assert trade["side"] == "buy"
    assert trade["quantity"] == 10
    assert trade["price"] == 100.0
    assert trade["executed_at"]


def test_buy_uppercases_the_ticker(db):
    execute_trade("aapl", "buy", 1, 100.0)
    assert get_position("AAPL") is not None


def test_insufficient_cash_is_rejected_without_writing(db):
    result = execute_trade("AAPL", "buy", 1000, 100.0)
    assert result.success is False
    assert result.error == "Insufficient cash: need $100000.00, have $10000.00"
    assert result.cash_balance == 10000.0
    assert get_positions() == []
    assert get_trades() == []


def test_buy_of_exactly_all_cash_is_allowed(db):
    assert execute_trade("AAPL", "buy", 100, 100.0).success is True
    assert get_cash_balance() == 0.0


def test_average_cost_after_multiple_buys(db):
    execute_trade("AAPL", "buy", 10, 100.0)
    execute_trade("AAPL", "buy", 30, 200.0)
    position = get_position("AAPL")
    assert position["quantity"] == 40
    assert position["avg_cost"] == 175.0


def test_sell_adds_cash_and_reduces_quantity(db):
    execute_trade("AAPL", "buy", 10, 100.0)
    result = execute_trade("AAPL", "sell", 4, 150.0)
    assert result.success is True
    assert result.cash_balance == pytest.approx(9600.0)
    position = get_position("AAPL")
    assert position["quantity"] == 6
    assert position["avg_cost"] == 100.0


def test_sell_of_entire_position_removes_it(db):
    execute_trade("AAPL", "buy", 10, 100.0)
    execute_trade("AAPL", "sell", 10, 90.0)
    assert get_position("AAPL") is None
    assert get_positions() == []
    assert get_cash_balance() == pytest.approx(9900.0)


def test_sell_more_than_owned_is_rejected(db):
    execute_trade("AAPL", "buy", 5, 100.0)
    result = execute_trade("AAPL", "sell", 6, 100.0)
    assert result.success is False
    assert result.error == "Insufficient shares: need 6, have 5"
    assert get_position("AAPL")["quantity"] == 5


def test_sell_without_a_position_is_rejected(db):
    result = execute_trade("AAPL", "sell", 1, 100.0)
    assert result.success is False
    assert result.error == "Insufficient shares: need 1, have 0"


def test_fractional_buy_and_sell(db):
    execute_trade("AAPL", "buy", 0.5, 100.0)
    execute_trade("AAPL", "buy", 0.25, 200.0)
    position = get_position("AAPL")
    assert position["quantity"] == pytest.approx(0.75)
    assert position["avg_cost"] == pytest.approx(133.3333333, rel=1e-6)

    execute_trade("AAPL", "sell", 0.25, 100.0)
    assert get_position("AAPL")["quantity"] == pytest.approx(0.5)


def test_fractional_sell_to_zero_closes_the_position(db):
    execute_trade("AAPL", "buy", 0.3, 100.0)
    execute_trade("AAPL", "sell", 0.1, 100.0)
    execute_trade("AAPL", "sell", 0.2, 100.0)
    assert get_position("AAPL") is None


def test_invalid_side_is_rejected(db):
    result = execute_trade("AAPL", "short", 1, 100.0)
    assert result.success is False
    assert result.error == "Invalid side: short"


@pytest.mark.parametrize("quantity", [0, -5])
def test_non_positive_quantity_is_rejected(db, quantity):
    result = execute_trade("AAPL", "buy", quantity, 100.0)
    assert result.success is False
    assert result.error == "Quantity must be positive"


def test_positions_are_listed_alphabetically(db):
    execute_trade("MSFT", "buy", 1, 100.0)
    execute_trade("AAPL", "buy", 1, 100.0)
    assert [p["ticker"] for p in get_positions()] == ["AAPL", "MSFT"]


def test_get_position_returns_none_when_absent(db):
    assert get_position("AAPL") is None


def test_trades_are_returned_newest_first(db):
    execute_trade("AAPL", "buy", 1, 100.0)
    execute_trade("MSFT", "buy", 1, 100.0)
    assert [t["ticker"] for t in get_trades()] == ["MSFT", "AAPL"]


def test_get_trades_honours_the_limit(db):
    execute_trade("AAPL", "buy", 1, 100.0)
    execute_trade("MSFT", "buy", 1, 100.0)
    assert [t["ticker"] for t in get_trades(limit=1)] == ["MSFT"]


def test_rejected_trade_is_not_logged(db):
    execute_trade("AAPL", "sell", 1, 100.0)
    assert get_trades() == []
