from app.market.cache import PriceCache
from app.market.models import ChangeDirection, PriceUpdate


def make_update(ticker: str, price: float = 100.0, previous: float = 99.0) -> PriceUpdate:
    return PriceUpdate(
        ticker=ticker,
        price=price,
        previous_price=previous,
        timestamp="2026-01-01T00:00:00+00:00",
        direction=ChangeDirection.UP,
    )


def test_get_returns_none_for_unknown_ticker():
    cache = PriceCache()
    assert cache.get("AAPL") is None


def test_update_then_get_returns_latest_value():
    cache = PriceCache()
    update = make_update("AAPL")
    cache.update(update)
    assert cache.get("AAPL") == update


def test_update_overwrites_previous_value_for_same_ticker():
    cache = PriceCache()
    cache.update(make_update("AAPL", price=100.0))
    cache.update(make_update("AAPL", price=101.0))
    assert cache.get("AAPL").price == 101.0


def test_snapshot_returns_latest_update_per_ticker():
    cache = PriceCache()
    cache.update(make_update("AAPL"))
    cache.update(make_update("MSFT"))
    snapshot = cache.snapshot()
    assert {u.ticker for u in snapshot} == {"AAPL", "MSFT"}


def test_snapshot_of_empty_cache_is_empty_list():
    cache = PriceCache()
    assert cache.snapshot() == []
