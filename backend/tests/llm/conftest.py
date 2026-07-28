import pytest
from httpx import ASGITransport, AsyncClient

from app.db import init_db
from app.main import app
from app.market import PriceCache
from app.market.models import PriceUpdate, compute_direction

SEED_PRICES = {"AAPL": 190.0, "MSFT": 400.0}


def price_update(ticker: str, price: float) -> PriceUpdate:
    return PriceUpdate(
        ticker=ticker,
        price=price,
        previous_price=price,
        timestamp="2026-07-28T12:00:00+00:00",
        direction=compute_direction(price, price),
    )


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Nothing in this package may reach OpenRouter, with or without a key."""
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("LLM_MOCK", raising=False)


@pytest.fixture
def cache(tmp_path, monkeypatch):
    """A seeded temp database plus a price cache holding two known tickers."""
    monkeypatch.setenv("FINALLY_DB_PATH", str(tmp_path / "test.db"))
    init_db()
    cache = PriceCache()
    for ticker, price in SEED_PRICES.items():
        cache.update(price_update(ticker, price))
    app.state.price_cache = cache
    return cache


@pytest.fixture
async def client(cache):
    """HTTP client over the ASGI app. Lifespan is not run - the fixtures wire the state."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client
