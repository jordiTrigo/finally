from app.db import add_to_watchlist, db_path, get_cash_balance, get_watchlist, init_db
from app.db.connection import DEFAULT_DB_PATH, connect
from app.db.schema import DEFAULT_WATCHLIST

TABLES = {
    "users_profile",
    "watchlist",
    "positions",
    "trades",
    "portfolio_snapshots",
    "chat_messages",
}


def table_names() -> set[str]:
    with connect() as conn:
        rows = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    return {row["name"] for row in rows}


def test_db_path_defaults_to_project_root(monkeypatch):
    monkeypatch.delenv("FINALLY_DB_PATH", raising=False)
    assert db_path() == DEFAULT_DB_PATH
    assert db_path().parts[-2:] == ("db", "finally.db")


def test_db_path_uses_environment_variable(monkeypatch):
    monkeypatch.setenv("FINALLY_DB_PATH", "/tmp/elsewhere.db")
    assert str(db_path()) == "/tmp/elsewhere.db"


def test_init_creates_all_tables(db):
    assert TABLES <= table_names()


def test_init_creates_missing_parent_directory(empty_db_path):
    init_db()
    assert empty_db_path.exists()


def test_init_seeds_profile_with_ten_thousand(db):
    assert get_cash_balance() == 10000.0


def test_init_seeds_default_watchlist_in_order(db):
    assert get_watchlist() == DEFAULT_WATCHLIST


def test_init_is_idempotent(db):
    init_db()
    init_db()
    assert get_watchlist() == DEFAULT_WATCHLIST
    assert get_cash_balance() == 10000.0


def test_reinit_does_not_restore_removed_tickers(db):
    add_to_watchlist("PYPL")
    init_db()
    assert get_watchlist() == [*DEFAULT_WATCHLIST, "PYPL"]


def test_watchlist_ticker_is_unique_per_user(db):
    assert add_to_watchlist("PYPL") is True
    assert add_to_watchlist("PYPL") is False
