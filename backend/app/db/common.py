"""Row primitives shared by every repository module."""

import uuid
from datetime import UTC, datetime


def new_id() -> str:
    """Primary key for a new row."""
    return str(uuid.uuid4())


def now_iso() -> str:
    """Current time as an ISO-8601 UTC string."""
    return datetime.now(UTC).isoformat()
