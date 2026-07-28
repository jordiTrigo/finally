"""Portfolio value over time, for the P&L chart."""

from app.db.common import new_id, now_iso
from app.db.connection import connect
from app.db.schema import DEFAULT_USER_ID


def record_snapshot(total_value: float, user_id: str = DEFAULT_USER_ID) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO portfolio_snapshots (id, user_id, total_value, recorded_at)
            VALUES (?, ?, ?, ?)
            """,
            (new_id(), user_id, total_value, now_iso()),
        )


def get_snapshots(user_id: str = DEFAULT_USER_ID) -> list[dict]:
    """Full snapshot history, oldest first."""
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT total_value, recorded_at FROM portfolio_snapshots
            WHERE user_id = ? ORDER BY recorded_at, rowid
            """,
            (user_id,),
        ).fetchall()
    return [dict(row) for row in rows]
