"""One chat turn: context, model call, auto-execution, persistence."""

from app.db import add_chat_message, get_chat_messages
from app.llm.actions import execute_actions
from app.llm.client import complete
from app.llm.context import build_context
from app.llm.mock import mock_enabled, mock_response
from app.llm.prompt import build_messages
from app.llm.schemas import ChatAction, ChatResponse
from app.market import PriceCache

HISTORY_LIMIT = 20


def respond(user_message: str, cache: PriceCache) -> tuple[str, list[ChatAction]]:
    """Answer one message, executing whatever the model asked for along the way."""
    history = get_chat_messages(limit=HISTORY_LIMIT)
    add_chat_message("user", user_message)

    response = _generate(user_message, history, cache)
    actions = execute_actions(response, cache)

    add_chat_message("assistant", response.message, _to_json(actions))
    return response.message, actions


def _generate(
    user_message: str, history: list[dict], cache: PriceCache
) -> ChatResponse:
    if mock_enabled():
        return mock_response(user_message)
    return complete(build_messages(user_message, history, build_context(cache)))


def _to_json(actions: list[ChatAction]) -> list[dict] | None:
    """Stored on the assistant message so a page reload replays the actions too."""
    return [action.model_dump() for action in actions] or None
