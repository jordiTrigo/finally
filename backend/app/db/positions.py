"""Current holdings. Mutation happens only through execute_trade."""

from app.db.connection import connect
from app.db.schema import DEFAULT_USER_ID

POSITION_COLUMNS = "ticker, quantity, avg_cost, updated_at"


def get_positions(user_id: str = DEFAULT_USER_ID) -> list[dict]:
    """All open positions, alphabetical by ticker."""
    with connect() as conn:
        rows = conn.execute(
            f"SELECT {POSITION_COLUMNS} FROM positions WHERE user_id = ? ORDER BY ticker",
            (user_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def get_position(ticker: str, user_id: str = DEFAULT_USER_ID) -> dict | None:
    with connect() as conn:
        row = fetch_position(conn, ticker.upper(), user_id)
    return dict(row) if row else None


def fetch_position(conn, ticker: str, user_id: str):
    """Position row inside an open transaction, or None."""
    return conn.execute(
        f"SELECT {POSITION_COLUMNS} FROM positions WHERE user_id = ? AND ticker = ?",
        (user_id, ticker),
    ).fetchone()
