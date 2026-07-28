"""Structured output parsing, and what happens when the model does not comply."""

from types import SimpleNamespace

import pytest

from app.llm.client import EXTRA_BODY, FALLBACK_MESSAGE, MODEL, complete, parse_response
from app.llm.schemas import ChatResponse


def test_parses_message_only():
    response = parse_response('{"message": "You hold 10 AAPL."}')
    assert response.message == "You hold 10 AAPL."
    assert response.trades == []
    assert response.watchlist_changes == []


def test_parses_trades_and_watchlist_changes():
    response = parse_response(
        '{"message": "Done.",'
        ' "trades": [{"ticker": "aapl", "side": "buy", "quantity": 10}],'
        ' "watchlist_changes": [{"ticker": "pypl", "action": "add"}]}'
    )
    assert response.trades[0].ticker == "AAPL"
    assert response.trades[0].side == "buy"
    assert response.trades[0].quantity == 10
    assert response.watchlist_changes[0].ticker == "PYPL"
    assert response.watchlist_changes[0].action == "add"


def test_parses_json_wrapped_in_a_markdown_fence():
    response = parse_response('```json\n{"message": "Fenced."}\n```')
    assert response.message == "Fenced."


@pytest.mark.parametrize(
    "content",
    ['{"message": "unterminated', '{"unexpected": "shape"}', "", None],
)
def test_unusable_json_degrades_to_the_fallback_message(content):
    response = parse_response(content)
    assert response.message == FALLBACK_MESSAGE
    assert response.trades == []


@pytest.mark.parametrize(
    "content",
    ['{"message": "Trailing brace."}}', '{"message": "Trailing brace."} and then some'],
)
def test_characters_trailing_the_object_are_ignored(content):
    assert parse_response(content).message == "Trailing brace."


def test_prose_response_is_kept_as_the_message():
    response = parse_response("I cannot format JSON today.")
    assert response.message == "I cannot format JSON today."


def test_complete_calls_cerebras_with_structured_output(monkeypatch):
    captured = {}

    def fake_completion(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content='{"message": "ok"}'))]
        )

    monkeypatch.setattr("app.llm.client.completion", fake_completion)
    response = complete([{"role": "user", "content": "hi"}])

    assert response == ChatResponse(message="ok")
    assert captured["model"] == MODEL
    assert captured["extra_body"] == EXTRA_BODY
    assert captured["reasoning_effort"] == "low"
    assert captured["response_format"] is ChatResponse
