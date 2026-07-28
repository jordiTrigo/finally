"""Trade execution - the single source of truth for portfolio math.

The API layer and the LLM layer both call `execute_trade`. A rejected trade is a
result value, not an exception: nothing is written and `error` explains why.
"""

from dataclasses import dataclass

from app.db.common import new_id, now_iso
from app.db.connection import connect
from app.db.positions import fetch_position
from app.db.schema import DEFAULT_USER_ID

# Below this many shares a position is closed rather than left as float dust.
DUST = 1e-9


@dataclass(frozen=True)
class TradeResult:
    success: bool
    cash_balance: float
    error: str | None = None
    trade: dict | None = None


def execute_trade(
    ticker: str,
    side: str,
    quantity: float,
    price: float,
    user_id: str = DEFAULT_USER_ID,
) -> TradeResult:
    """Execute a market order at `price`, updating cash, position and trade log."""
    ticker = ticker.upper()
    with connect() as conn:
        # Read-modify-write on cash and position: take the write lock before reading
        # so two concurrent trades cannot both price against the same balance.
        conn.execute("BEGIN IMMEDIATE")
        cash = conn.execute(
            "SELECT cash_balance FROM users_profile WHERE id = ?", (user_id,)
        ).fetchone()["cash_balance"]

        if side not in ("buy", "sell"):
            return TradeResult(False, cash, f"Invalid side: {side}")
        if quantity <= 0:
            return TradeResult(False, cash, "Quantity must be positive")

        position = fetch_position(conn, ticker, user_id)
        if side == "buy":
            error = _check_cash(cash, quantity, price)
        else:
            error = _check_shares(position, quantity)
        if error:
            return TradeResult(False, cash, error)

        cash = cash - quantity * price if side == "buy" else cash + quantity * price
        conn.execute(
            "UPDATE users_profile SET cash_balance = ? WHERE id = ?", (cash, user_id)
        )
        _apply_to_position(conn, position, ticker, side, quantity, price, user_id)
        trade = _log_trade(conn, ticker, side, quantity, price, user_id)

    return TradeResult(True, cash, trade=trade)


def get_trades(limit: int | None = None, user_id: str = DEFAULT_USER_ID) -> list[dict]:
    """Trade history, newest first."""
    sql = (
        "SELECT id, ticker, side, quantity, price, executed_at FROM trades "
        "WHERE user_id = ? ORDER BY executed_at DESC, rowid DESC"
    )
    params: list = [user_id]
    if limit is not None:
        sql += " LIMIT ?"
        params.append(limit)
    with connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(row) for row in rows]


def _check_cash(cash: float, quantity: float, price: float) -> str | None:
    cost = quantity * price
    if cost > cash:
        return f"Insufficient cash: need ${cost:.2f}, have ${cash:.2f}"
    return None


def _check_shares(position, quantity: float) -> str | None:
    owned = position["quantity"] if position else 0.0
    if quantity > owned + DUST:
        return f"Insufficient shares: need {quantity:g}, have {owned:g}"
    return None


def _apply_to_position(conn, position, ticker, side, quantity, price, user_id) -> None:
    """Add to, reduce, or close the position for this ticker."""
    if side == "buy":
        held = position["quantity"] if position else 0.0
        cost_basis = held * position["avg_cost"] if position else 0.0
        new_quantity = held + quantity
        avg_cost = (cost_basis + quantity * price) / new_quantity
        _upsert_position(conn, ticker, new_quantity, avg_cost, user_id)
        return

    remaining = position["quantity"] - quantity
    if remaining < DUST:
        conn.execute(
            "DELETE FROM positions WHERE user_id = ? AND ticker = ?", (user_id, ticker)
        )
        return
    _upsert_position(conn, ticker, remaining, position["avg_cost"], user_id)


def _upsert_position(conn, ticker, quantity, avg_cost, user_id) -> None:
    conn.execute(
        """
        INSERT INTO positions (id, user_id, ticker, quantity, avg_cost, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT (user_id, ticker) DO UPDATE
        SET quantity = excluded.quantity,
            avg_cost = excluded.avg_cost,
            updated_at = excluded.updated_at
        """,
        (new_id(), user_id, ticker, quantity, avg_cost, now_iso()),
    )


def _log_trade(conn, ticker, side, quantity, price, user_id) -> dict:
    trade = {
        "id": new_id(),
        "ticker": ticker,
        "side": side,
        "quantity": quantity,
        "price": price,
        "executed_at": now_iso(),
    }
    conn.execute(
        """
        INSERT INTO trades (id, user_id, ticker, side, quantity, price, executed_at)
        VALUES (:id, :user_id, :ticker, :side, :quantity, :price, :executed_at)
        """,
        {**trade, "user_id": user_id},
    )
    return trade
