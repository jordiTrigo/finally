"""Request and response models. Shapes are frozen by planning/TEAM.md section 4."""

from typing import Literal

from pydantic import BaseModel, Field, field_validator

Direction = Literal["up", "down", "flat"]


class TickerRequest(BaseModel):
    ticker: str = Field(min_length=1)

    @field_validator("ticker")
    @classmethod
    def normalize(cls, value: str) -> str:
        return value.strip().upper()


class TickerOut(BaseModel):
    ticker: str


class TradeRequest(TickerRequest):
    side: Literal["buy", "sell"]
    quantity: float = Field(gt=0)


class TradeOut(BaseModel):
    id: str
    ticker: str
    side: str
    quantity: float
    price: float
    executed_at: str
    cash_balance: float


class PositionOut(BaseModel):
    ticker: str
    quantity: float
    avg_cost: float
    current_price: float
    market_value: float
    unrealized_pnl: float
    pnl_percent: float


class PortfolioOut(BaseModel):
    cash_balance: float
    positions: list[PositionOut]
    positions_value: float
    total_value: float
    total_unrealized_pnl: float


class SnapshotOut(BaseModel):
    total_value: float
    recorded_at: str


class HistoryOut(BaseModel):
    snapshots: list[SnapshotOut]


class WatchlistTickerOut(BaseModel):
    ticker: str
    price: float | None
    previous_price: float | None
    direction: Direction


class WatchlistOut(BaseModel):
    tickers: list[WatchlistTickerOut]
