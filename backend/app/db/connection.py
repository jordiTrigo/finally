"""SQLite connection handling.

One short-lived connection per call. SQLite writes to a local file in microseconds,
so an async endpoint can make these calls directly without a thread pool, and a
fresh connection per call sidesteps sqlite3's thread affinity entirely.
"""

import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DB_PATH = PROJECT_ROOT / "db" / "finally.db"


def db_path() -> Path:
    """Database file location, from FINALLY_DB_PATH or the project-root default."""
    configured = os.environ.get("FINALLY_DB_PATH")
    return Path(configured) if configured else DEFAULT_DB_PATH


def get_connection() -> sqlite3.Connection:
    """Open a connection with row access by name and WAL journaling."""
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=5.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    """Connection that commits on success, rolls back on error, and always closes."""
    conn = get_connection()
    try:
        with conn:
            yield conn
    finally:
        conn.close()
