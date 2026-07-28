import pytest

from app.main import app
from app.market import PriceCache
from tests.api.conftest import price_update


async def buy(client, ticker="AAPL", quantity=2.0):
    return await client.post(
        "/api/portfolio/trade",
        json={"ticker": ticker, "side": "buy", "quantity": quantity},
    )


async def test_fresh_portfolio_is_all_cash(client):
    body = (await client.get("/api/portfolio")).json()

    assert body == {
        "cash_balance": 10000.0,
        "positions": [],
        "positions_value": 0.0,
        "total_value": 10000.0,
        "total_unrealized_pnl": 0.0,
    }


async def test_position_is_marked_to_the_current_cache_price(client, cache):
    await buy(client, "AAPL", 2.0)
    cache.update(price_update("AAPL", 200.0, previous=190.0))

    body = (await client.get("/api/portfolio")).json()
    position = body["positions"][0]

    assert position == {
        "ticker": "AAPL",
        "quantity": 2.0,
        "avg_cost": 190.0,
        "current_price": 200.0,
        "market_value": 400.0,
        "unrealized_pnl": 20.0,
        "pnl_percent": pytest.approx(5.263, abs=1e-3),
    }
    assert body["cash_balance"] == pytest.approx(9620.0)
    assert body["positions_value"] == 400.0
    assert body["total_value"] == pytest.approx(10020.0)
    assert body["total_unrealized_pnl"] == 20.0


async def test_position_without_a_cached_price_is_valued_at_cost(client):
    await buy(client, "AAPL", 2.0)
    app.state.price_cache = PriceCache()

    position = (await client.get("/api/portfolio")).json()["positions"][0]

    assert position["current_price"] == 190.0
    assert position["unrealized_pnl"] == 0.0


async def test_buy_fills_at_the_cache_price(client):
    response = await buy(client, "AAPL", 2.0)

    assert response.status_code == 200
    body = response.json()
    assert body["ticker"] == "AAPL"
    assert body["side"] == "buy"
    assert body["quantity"] == 2.0
    assert body["price"] == 190.0
    assert body["cash_balance"] == pytest.approx(9620.0)
    assert body["executed_at"]
    assert body["id"]


async def test_ticker_is_normalized_to_uppercase(client):
    body = (await buy(client, "aapl", 1.0)).json()

    assert body["ticker"] == "AAPL"


async def test_sell_closes_the_position_and_returns_the_cash(client):
    await buy(client, "AAPL", 2.0)

    response = await client.post(
        "/api/portfolio/trade",
        json={"ticker": "AAPL", "side": "sell", "quantity": 2.0},
    )

    assert response.status_code == 200
    assert response.json()["cash_balance"] == pytest.approx(10000.0)
    assert (await client.get("/api/portfolio")).json()["positions"] == []


async def test_buy_beyond_cash_is_rejected(client):
    response = await buy(client, "AAPL", 1000.0)

    assert response.status_code == 400
    assert response.json()["detail"].startswith("Insufficient cash")


async def test_sell_beyond_holdings_is_rejected(client):
    response = await client.post(
        "/api/portfolio/trade",
        json={"ticker": "AAPL", "side": "sell", "quantity": 5.0},
    )

    assert response.status_code == 400
    assert response.json()["detail"].startswith("Insufficient shares")


async def test_trade_on_an_unpriced_ticker_is_rejected(client):
    response = await buy(client, "PYPL", 1.0)

    assert response.status_code == 400
    assert response.json()["detail"] == "No price available for PYPL"


@pytest.mark.parametrize(
    "payload",
    [
        {"ticker": "AAPL", "side": "buy", "quantity": 0},
        {"ticker": "AAPL", "side": "buy", "quantity": -1},
        {"ticker": "AAPL", "side": "hold", "quantity": 1},
        {"ticker": "", "side": "buy", "quantity": 1},
    ],
)
async def test_malformed_trade_is_unprocessable(client, payload):
    response = await client.post("/api/portfolio/trade", json=payload)

    assert response.status_code == 422


async def test_a_trade_records_a_snapshot(client):
    assert (await client.get("/api/portfolio/history")).json()["snapshots"] == []

    await buy(client, "AAPL", 2.0)

    snapshots = (await client.get("/api/portfolio/history")).json()["snapshots"]
    assert len(snapshots) == 1
    assert snapshots[0]["total_value"] == pytest.approx(10000.0)
    assert snapshots[0]["recorded_at"]


async def test_a_rejected_trade_records_no_snapshot(client):
    await buy(client, "AAPL", 1000.0)

    assert (await client.get("/api/portfolio/history")).json()["snapshots"] == []


async def test_history_is_oldest_first(client):
    await buy(client, "AAPL", 1.0)
    await buy(client, "MSFT", 1.0)

    snapshots = (await client.get("/api/portfolio/history")).json()["snapshots"]

    assert len(snapshots) == 2
    assert snapshots[0]["recorded_at"] <= snapshots[1]["recorded_at"]
