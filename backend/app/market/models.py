from dataclasses import dataclass
from enum import Enum


class ChangeDirection(str, Enum):
    UP = "up"
    DOWN = "down"
    FLAT = "flat"


@dataclass(frozen=True)
class PriceUpdate:
    ticker: str
    price: float
    previous_price: float
    timestamp: str  # ISO 8601, UTC
    direction: ChangeDirection


def direction(price: float, previous: float) -> ChangeDirection:
    if price > previous:
        return ChangeDirection.UP
    if price < previous:
        return ChangeDirection.DOWN
    return ChangeDirection.FLAT
