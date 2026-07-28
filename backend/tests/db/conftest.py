import pytest

from app.db import init_db


@pytest.fixture
def db(tmp_path, monkeypatch):
    """A seeded database in a temporary directory."""
    monkeypatch.setenv("FINALLY_DB_PATH", str(tmp_path / "test.db"))
    init_db()
    return tmp_path / "test.db"


@pytest.fixture
def empty_db_path(tmp_path, monkeypatch):
    """A database path pointing at no file yet."""
    path = tmp_path / "nested" / "test.db"
    monkeypatch.setenv("FINALLY_DB_PATH", str(path))
    return path
