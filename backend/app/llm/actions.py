"""Auto-execution of the actions in a model response.

Trades go through `execute_trade`, the same function the manual trade route uses, so the
LLM cannot bypass the cash and share checks. A rejected action is reported as a failed
action record rather than an error - the user sees why it did not happen.
"""

from app.api.valuation import total_value
from app.db import add_to_watchlist, execute_trade, record_snapshot, remove_from_watchlist
from app.llm.schemas import ChatAction, ChatResponse, TradeInstruction, WatchlistChange
from app.market import PriceCache


def execute_actions(response: ChatResponse, cache: PriceCache) -> list[ChatAction]:
    """Run every trade then every watchlist change, in the order the model listed them."""
    trades = [_execute_trade(trade, cache) for trade in response.trades]
    changes = [_apply_change(change) for change in response.watchlist_changes]
    return trades + changes


def _execute_trade(instruction: TradeInstruction, cache: PriceCache) -> ChatAction:
    order = f"{instruction.side} {instruction.quantity:g} {instruction.ticker}"
    update = cache.get(instruction.ticker)
    if update is None:
        return _failed("trade", f"{order} rejected: no price available")

    result = execute_trade(
        instruction.ticker, instruction.side, instruction.quantity, update.price
    )
    if not result.success:
        return _failed("trade", f"{order} rejected: {result.error}")

    record_snapshot(total_value(cache))
    return _executed("trade", f"{order} filled at ${update.price:,.2f}")


def _apply_change(change: WatchlistChange) -> ChatAction:
    if change.action == "add":
        if not add_to_watchlist(change.ticker):
            return _failed("watchlist", f"{change.ticker} is already on the watchlist")
        return _executed("watchlist", f"Added {change.ticker} to the watchlist")

    if not remove_from_watchlist(change.ticker):
        return _failed("watchlist", f"{change.ticker} is not on the watchlist")
    return _executed("watchlist", f"Removed {change.ticker} from the watchlist")


def _executed(action_type: str, detail: str) -> ChatAction:
    return ChatAction(type=action_type, status="executed", detail=detail)


def _failed(action_type: str, detail: str) -> ChatAction:
    return ChatAction(type=action_type, status="failed", detail=detail)
