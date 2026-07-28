"""Chat history. `actions` is stored as JSON and returned as a dict."""

import json

from app.db.common import new_id, now_iso
from app.db.connection import connect
from app.db.schema import DEFAULT_USER_ID


def get_chat_messages(
    limit: int | None = None, user_id: str = DEFAULT_USER_ID
) -> list[dict]:
    """Messages oldest first. With a limit, the most recent `limit` messages."""
    sql = (
        "SELECT id, role, content, actions, created_at FROM chat_messages "
        "WHERE user_id = ? ORDER BY created_at DESC, rowid DESC"
    )
    params: list = [user_id]
    if limit is not None:
        sql += " LIMIT ?"
        params.append(limit)
    with connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_to_message(row) for row in reversed(rows)]


def add_chat_message(
    role: str,
    content: str,
    actions: dict | None = None,
    user_id: str = DEFAULT_USER_ID,
) -> dict:
    """Append a message and return it."""
    message = {
        "id": new_id(),
        "role": role,
        "content": content,
        "actions": actions,
        "created_at": now_iso(),
    }
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO chat_messages (id, user_id, role, content, actions, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                message["id"],
                user_id,
                role,
                content,
                json.dumps(actions) if actions is not None else None,
                message["created_at"],
            ),
        )
    return message


def _to_message(row) -> dict:
    message = dict(row)
    message["actions"] = json.loads(row["actions"]) if row["actions"] else None
    return message
