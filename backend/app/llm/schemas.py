"""Structured output schema for the assistant, and the action records it produces."""

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class TradeInstruction(BaseModel):
    """A market order the model wants executed."""

    ticker: str
    side: Literal["buy", "sell"]
    quantity: float

    @field_validator("ticker")
    @classmethod
    def normalize(cls, value: str) -> str:
        return value.strip().upper()


class WatchlistChange(BaseModel):
    """A watchlist edit the model wants applied."""

    ticker: str
    action: Literal["add", "remove"]

    @field_validator("ticker")
    @classmethod
    def normalize(cls, value: str) -> str:
        return value.strip().upper()


class ChatResponse(BaseModel):
    """What the model returns: prose plus the actions to auto-execute."""

    message: str
    trades: list[TradeInstruction] = Field(default_factory=list)
    watchlist_changes: list[WatchlistChange] = Field(default_factory=list)


class ChatAction(BaseModel):
    """The outcome of one executed action, as shown in the chat panel."""

    type: Literal["trade", "watchlist"]
    status: Literal["executed", "failed"]
    detail: str
