"""User profile: cash balance."""

from app.db.connection import connect
from app.db.schema import DEFAULT_USER_ID


def get_profile(user_id: str = DEFAULT_USER_ID) -> dict | None:
    """Profile row as {"id", "cash_balance", "created_at"}, or None if absent."""
    with connect() as conn:
        row = conn.execute(
            "SELECT id, cash_balance, created_at FROM users_profile WHERE id = ?",
            (user_id,),
        ).fetchone()
    return dict(row) if row else None


def get_cash_balance(user_id: str = DEFAULT_USER_ID) -> float:
    with connect() as conn:
        row = conn.execute(
            "SELECT cash_balance FROM users_profile WHERE id = ?", (user_id,)
        ).fetchone()
    return row["cash_balance"]


def set_cash_balance(amount: float, user_id: str = DEFAULT_USER_ID) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE users_profile SET cash_balance = ? WHERE id = ?", (amount, user_id)
        )
