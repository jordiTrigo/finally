"""SQLite persistence layer. The interface here is frozen by planning/TEAM.md section 3."""

from app.db.chat import add_chat_message, get_chat_messages
from app.db.connection import db_path, get_connection
from app.db.positions import get_position, get_positions
from app.db.profile import get_cash_balance, get_profile, set_cash_balance
from app.db.schema import init_db
from app.db.snapshots import get_snapshots, record_snapshot
from app.db.trades import TradeResult, execute_trade, get_trades
from app.db.watchlist import add_to_watchlist, get_watchlist, remove_from_watchlist

__all__ = [
    "init_db",
    "get_connection",
    "db_path",
    "get_profile",
    "get_cash_balance",
    "set_cash_balance",
    "get_watchlist",
    "add_to_watchlist",
    "remove_from_watchlist",
    "get_positions",
    "get_position",
    "TradeResult",
    "execute_trade",
    "get_trades",
    "record_snapshot",
    "get_snapshots",
    "get_chat_messages",
    "add_chat_message",
]
