import json
from dataclasses import FrozenInstanceError, asdict

import pytest

from app.market.models import ChangeDirection, PriceUpdate, compute_direction


@pytest.mark.parametrize(
    "price, previous, expected",
    [
        (101.0, 100.0, ChangeDirection.UP),
        (99.0, 100.0, ChangeDirection.DOWN),
        (100.0, 100.0, ChangeDirection.FLAT),
    ],
)
def test_direction(price, previous, expected):
    assert compute_direction(price, previous) == expected


def test_change_direction_values_are_plain_strings():
    assert ChangeDirection.UP.value == "up"
    assert ChangeDirection.DOWN.value == "down"
    assert ChangeDirection.FLAT.value == "flat"


def test_price_update_is_frozen():
    update = PriceUpdate(
        ticker="AAPL",
        price=190.0,
        previous_price=189.0,
        timestamp="2026-01-01T00:00:00+00:00",
        direction=ChangeDirection.UP,
    )
    with pytest.raises(FrozenInstanceError):
        update.price = 200.0


def test_price_update_serializes_with_plain_json_dumps():
    update = PriceUpdate(
        ticker="AAPL",
        price=190.0,
        previous_price=189.0,
        timestamp="2026-01-01T00:00:00+00:00",
        direction=ChangeDirection.UP,
    )
    parsed = json.loads(json.dumps(asdict(update)))
    assert parsed == {
        "ticker": "AAPL",
        "price": 190.0,
        "previous_price": 189.0,
        "timestamp": "2026-01-01T00:00:00+00:00",
        "direction": "up",
    }
