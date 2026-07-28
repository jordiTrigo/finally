import pytest
from httpx import ASGITransport, AsyncClient

from app.db import init_db
from app.main import app
from app.market import PriceCache
from app.market.models import PriceUpdate, compute_direction

SEED_PRICES = {"AAPL": 190.0, "MSFT": 400.0}


def price_update(ticker: str, price: float, previous: float | None = None) -> PriceUpdate:
    previous = price if previous is None else previous
    return PriceUpdate(
        ticker=ticker,
        price=price,
        previous_price=previous,
        timestamp="2026-07-28T12:00:00+00:00",
        direction=compute_direction(price, previous),
    )


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
    """HTTP client over the ASGI app. Lifespan is not run - the fixtures do that wiring."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client
