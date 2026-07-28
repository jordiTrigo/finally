from app.db import add_chat_message, get_chat_messages


def test_no_messages_initially(db):
    assert get_chat_messages() == []


def test_add_returns_the_stored_message(db):
    message = add_chat_message("user", "buy 10 AAPL")
    assert message["role"] == "user"
    assert message["content"] == "buy 10 AAPL"
    assert message["actions"] is None
    assert message["id"] and message["created_at"]


def test_messages_are_returned_oldest_first(db):
    add_chat_message("user", "first")
    add_chat_message("assistant", "second")
    assert [m["content"] for m in get_chat_messages()] == ["first", "second"]


def test_limit_returns_the_most_recent_messages_in_order(db):
    for i in range(5):
        add_chat_message("user", str(i))
    assert [m["content"] for m in get_chat_messages(limit=3)] == ["2", "3", "4"]


def test_actions_round_trip_as_a_dict(db):
    actions = {"trades": [{"ticker": "AAPL", "side": "buy", "quantity": 10}]}
    add_chat_message("assistant", "Bought 10 AAPL", actions)
    assert get_chat_messages()[0]["actions"] == actions
