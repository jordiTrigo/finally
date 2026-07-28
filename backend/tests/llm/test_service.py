"""One chat turn end to end, with the model call stubbed out."""

from app.db import add_chat_message, get_chat_messages, get_position
from app.llm.client import FALLBACK_MESSAGE
from app.llm.schemas import ChatResponse
from app.llm.service import HISTORY_LIMIT, respond


def stub_model(monkeypatch, content: str) -> list[list[dict]]:
    """Replace the network call with a fixed raw completion body."""
    calls: list[list[dict]] = []

    def fake_complete(messages):
        calls.append(messages)
        from app.llm.client import parse_response

        return parse_response(content)

    monkeypatch.setattr("app.llm.service.complete", fake_complete)
    return calls


def test_turn_executes_actions_and_persists_both_messages(cache, monkeypatch):
    stub_model(
        monkeypatch,
        '{"message": "Buying.",'
        ' "trades": [{"ticker": "AAPL", "side": "buy", "quantity": 2}]}',
    )

    message, actions = respond("buy some apple", cache)

    assert message == "Buying."
    assert actions[0].status == "executed"
    assert get_position("AAPL")["quantity"] == 2
    stored = get_chat_messages()
    assert [m["content"] for m in stored] == ["buy some apple", "Buying."]
    assert stored[1]["actions"][0]["detail"] == "buy 2 AAPL filled at $190.00"


def test_turn_with_no_actions_stores_null_actions(cache, monkeypatch):
    stub_model(monkeypatch, '{"message": "You are all cash."}')

    _, actions = respond("how am I doing?", cache)

    assert actions == []
    assert get_chat_messages()[1]["actions"] is None


def test_malformed_response_degrades_to_a_plain_message(cache, monkeypatch):
    stub_model(monkeypatch, '{"message": "half a resp')

    message, actions = respond("hello", cache)

    assert message == FALLBACK_MESSAGE
    assert actions == []
    assert get_chat_messages()[1]["content"] == FALLBACK_MESSAGE


def test_prompt_carries_at_most_twenty_prior_messages(cache, monkeypatch):
    calls = stub_model(monkeypatch, '{"message": "ok"}')
    for index in range(30):
        add_chat_message("user", f"message {index}")

    respond("and now?", cache)

    history = calls[0][1:-1]
    assert len(history) == HISTORY_LIMIT
    assert history[0]["content"] == "message 10"
    assert calls[0][-1] == {"role": "user", "content": "and now?"}


def test_mock_mode_never_calls_the_model(cache, monkeypatch):
    monkeypatch.setenv("LLM_MOCK", "true")
    calls = stub_model(monkeypatch, '{"message": "unused"}')

    message, actions = respond("buy 1 MSFT", cache)

    assert calls == []
    assert message == "Mock mode: executing buy 1 MSFT."
    assert actions[0].detail == "buy 1 MSFT filled at $400.00"


def test_response_schema_defaults_are_empty_lists():
    response = ChatResponse(message="hi")
    assert response.trades == []
    assert response.watchlist_changes == []
