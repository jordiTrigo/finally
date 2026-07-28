from app.db.schema import DEFAULT_WATCHLIST
from tests.api.conftest import price_update


async def tickers(client) -> list[dict]:
    return (await client.get("/api/watchlist")).json()["tickers"]


async def test_seeded_watchlist_is_returned_in_order(client):
    assert [row["ticker"] for row in await tickers(client)] == DEFAULT_WATCHLIST


async def test_cached_ticker_carries_price_and_direction(client, cache):
    cache.update(price_update("AAPL", 191.0, previous=190.0))

    aapl = next(row for row in await tickers(client) if row["ticker"] == "AAPL")

    assert aapl == {
        "ticker": "AAPL",
        "price": 191.0,
        "previous_price": 190.0,
        "direction": "up",
    }


async def test_uncached_ticker_reports_null_prices(client):
    tsla = next(row for row in await tickers(client) if row["ticker"] == "TSLA")

    assert tsla == {
        "ticker": "TSLA",
        "price": None,
        "previous_price": None,
        "direction": "flat",
    }


async def test_add_returns_created_and_appears_in_the_list(client):
    response = await client.post("/api/watchlist", json={"ticker": "PYPL"})

    assert response.status_code == 201
    assert response.json() == {"ticker": "PYPL"}
    assert "PYPL" in [row["ticker"] for row in await tickers(client)]


async def test_add_normalizes_to_uppercase(client):
    response = await client.post("/api/watchlist", json={"ticker": " pypl "})

    assert response.status_code == 201
    assert response.json() == {"ticker": "PYPL"}


async def test_adding_a_present_ticker_conflicts(client):
    response = await client.post("/api/watchlist", json={"ticker": "AAPL"})

    assert response.status_code == 409
    assert response.json()["detail"] == "AAPL is already on the watchlist"


async def test_add_rejects_an_empty_ticker(client):
    response = await client.post("/api/watchlist", json={"ticker": ""})

    assert response.status_code == 422


async def test_remove_returns_no_content_and_drops_the_ticker(client):
    response = await client.delete("/api/watchlist/AAPL")

    assert response.status_code == 204
    assert "AAPL" not in [row["ticker"] for row in await tickers(client)]


async def test_remove_accepts_lowercase(client):
    assert (await client.delete("/api/watchlist/aapl")).status_code == 204


async def test_removing_an_absent_ticker_is_not_found(client):
    response = await client.delete("/api/watchlist/PYPL")

    assert response.status_code == 404
    assert response.json()["detail"] == "PYPL is not on the watchlist"
