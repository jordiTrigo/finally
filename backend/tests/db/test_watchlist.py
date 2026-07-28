from app.db import add_to_watchlist, get_watchlist, remove_from_watchlist


def test_add_appends_to_the_end(db):
    add_to_watchlist("PYPL")
    assert get_watchlist()[-1] == "PYPL"


def test_add_uppercases_the_ticker(db):
    add_to_watchlist("pypl")
    assert "PYPL" in get_watchlist()


def test_add_returns_false_when_already_present(db):
    assert add_to_watchlist("AAPL") is False


def test_remove_returns_true_and_drops_the_ticker(db):
    assert remove_from_watchlist("AAPL") is True
    assert "AAPL" not in get_watchlist()


def test_remove_is_case_insensitive(db):
    assert remove_from_watchlist("aapl") is True


def test_remove_returns_false_when_absent(db):
    assert remove_from_watchlist("ZZZZ") is False


def test_watchlist_is_per_user(db):
    add_to_watchlist("PYPL", user_id="other")
    assert get_watchlist(user_id="other") == ["PYPL"]
