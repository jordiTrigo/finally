"""LLM_MOCK=true: deterministic, offline, and still able to drive real actions."""

import pytest

from app.llm.mock import IDLE_MESSAGE, mock_enabled, mock_response


@pytest.mark.parametrize(
    "value,expected", [("true", True), ("TRUE", True), ("false", False), ("", False)]
)
def test_mock_enabled_reads_the_environment(monkeypatch, value, expected):
    monkeypatch.setenv("LLM_MOCK", value)
    assert mock_enabled() is expected


def test_mock_is_off_when_the_variable_is_absent():
    assert mock_enabled() is False


@pytest.mark.parametrize(
    "prompt,side,quantity,ticker",
    [
        ("buy 10 AAPL", "buy", 10, "AAPL"),
        ("Buy 2.5 shares of MSFT please", "buy", 2.5, "MSFT"),
        ("sell 3 NVDA now", "sell", 3, "NVDA"),
    ],
)
def test_trade_prompts_produce_a_trade(prompt, side, quantity, ticker):
    response = mock_response(prompt)

    assert len(response.trades) == 1
    assert response.trades[0].side == side
    assert response.trades[0].quantity == quantity
    assert response.trades[0].ticker == ticker


@pytest.mark.parametrize(
    "prompt,action,ticker",
    [
        ("add PYPL to the watchlist", "add", "PYPL"),
        ("remove NFLX from the watchlist", "remove", "NFLX"),
        ("Add SHOP", "add", "SHOP"),
    ],
)
def test_watchlist_prompts_produce_a_change(prompt, action, ticker):
    response = mock_response(prompt)

    assert len(response.watchlist_changes) == 1
    assert response.watchlist_changes[0].action == action
    assert response.watchlist_changes[0].ticker == ticker


def test_one_prompt_can_carry_both_kinds_of_action():
    response = mock_response("buy 5 AAPL and add PYPL to the watchlist")

    assert response.trades[0].ticker == "AAPL"
    assert response.watchlist_changes[0].ticker == "PYPL"
    assert response.message == "Mock mode: executing buy 5 AAPL, add PYPL."


def test_prompt_without_an_uppercase_ticker_does_nothing():
    response = mock_response("add more cash to my account")

    assert response.trades == []
    assert response.watchlist_changes == []
    assert response.message == IDLE_MESSAGE


def test_mock_is_deterministic():
    assert mock_response("buy 10 AAPL") == mock_response("buy 10 AAPL")
