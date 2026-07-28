import pytest


@pytest.fixture(scope="session", autouse=True)
def isolated_db(tmp_path_factory):
    """Keep the whole suite off the real database file.

    Tests that need a fresh database point `FINALLY_DB_PATH` at their own tmp_path;
    this fixture covers the rest, notably the tests that run the app's lifespan.
    """
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("FINALLY_DB_PATH", str(tmp_path_factory.mktemp("db") / "finally.db"))
        yield
