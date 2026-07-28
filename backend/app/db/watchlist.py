"""Watchlist tickers."""

import sqlite3

from app.db.common import new_id, now_iso
from app.db.connection import connect
from app.db.schema import DEFAULT_USER_ID


def get_watchlist(user_id: str = DEFAULT_USER_ID) -> list[str]:
    """Watched tickers in insertion order."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT ticker FROM watchlist WHERE user_id = ? ORDER BY added_at, rowid",
            (user_id,),
        ).fetchall()
    return [row["ticker"] for row in rows]


def add_to_watchlist(ticker: str, user_id: str = DEFAULT_USER_ID) -> bool:
    """Add a ticker. False if it was already present."""
    try:
        with connect() as conn:
            conn.execute(
                "INSERT INTO watchlist (id, user_id, ticker, added_at) VALUES (?, ?, ?, ?)",
                (new_id(), user_id, ticker.upper(), now_iso()),
            )
    except sqlite3.IntegrityError:
        return False
    return True


def remove_from_watchlist(ticker: str, user_id: str = DEFAULT_USER_ID) -> bool:
    """Remove a ticker. False if it was not present."""
    with connect() as conn:
        cursor = conn.execute(
            "DELETE FROM watchlist WHERE user_id = ? AND ticker = ?",
            (user_id, ticker.upper()),
        )
    return cursor.rowcount > 0
