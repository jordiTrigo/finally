"""GET and POST /api/chat, driven through mock mode so no network is touched."""

import pytest

from app.db import add_chat_message, get_cash_balance, get_chat_messages, get_watchlist


@pytest.fixture(autouse=True)
def mock_mode(monkeypatch):
    monkeypatch.setenv("LLM_MOCK", "true")


async def test_history_starts_empty(client):
    response = await client.get("/api/chat")

    assert response.status_code == 200
    assert response.json() == {"messages": []}


async def test_history_returns_stored_messages(client):
    add_chat_message("user", "hello")
    add_chat_message("assistant", "hi", [{"type": "trade", "status": "executed", "detail": "x"}])

    messages = (await client.get("/api/chat")).json()["messages"]

    assert [m["role"] for m in messages] == ["user", "assistant"]
    assert messages[0]["actions"] is None
    assert messages[1]["actions"] == [
        {"type": "trade", "status": "executed", "detail": "x"}
    ]


async def test_post_executes_a_trade_and_returns_the_action(client):
    response = await client.post("/api/chat", json={"message": "buy 10 AAPL"})

    body = response.json()
    assert response.status_code == 200
    assert body["message"] == "Mock mode: executing buy 10 AAPL."
    assert body["actions"] == [
        {"type": "trade", "status": "executed", "detail": "buy 10 AAPL filled at $190.00"}
    ]
    assert get_cash_balance() == 10000.0 - 1900.0


async def test_post_applies_a_watchlist_change(client):
    body = (
        await client.post("/api/chat", json={"message": "add PYPL to the watchlist"})
    ).json()

    assert body["actions"] == [
        {"type": "watchlist", "status": "executed", "detail": "Added PYPL to the watchlist"}
    ]
    assert "PYPL" in get_watchlist()


async def test_post_returns_a_failed_action_without_failing_the_request(client):
    response = await client.post("/api/chat", json={"message": "buy 1000 AAPL"})

    assert response.status_code == 200
    action = response.json()["actions"][0]
    assert action["status"] == "failed"
    assert "Insufficient cash" in action["detail"]


async def test_post_persists_both_turns(client):
    await client.post("/api/chat", json={"message": "buy 10 AAPL"})

    messages = get_chat_messages()
    assert [m["role"] for m in messages] == ["user", "assistant"]
    assert messages[0]["content"] == "buy 10 AAPL"
    assert messages[1]["actions"][0]["status"] == "executed"


async def test_empty_message_is_rejected(client):
    assert (await client.post("/api/chat", json={"message": ""})).status_code == 422
