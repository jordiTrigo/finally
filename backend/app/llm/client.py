"""LiteLLM call to gpt-oss-20b on OpenRouter, pinned to the Cerebras provider.

LiteLLM calls `load_dotenv()` when it imports in its default DEV mode, which pushes the
project `.env` into the process environment behind the app's back - `MASSIVE_API_KEY`
included, silently switching the market data source. PRODUCTION mode skips that load and
leaves the environment to whoever started the process.
"""

import json
import os

os.environ.setdefault("LITELLM_MODE", "PRODUCTION")

from litellm import completion  # noqa: E402
from pydantic import ValidationError  # noqa: E402

from app.llm.schemas import ChatResponse  # noqa: E402

MODEL = "openrouter/openai/gpt-oss-20b:free"
EXTRA_BODY = {"provider": {"order": ["cerebras"]}}
FALLBACK_MESSAGE = "I could not read that response. Ask me again."


def complete(messages: list[dict]) -> ChatResponse:
    """One structured-output completion, parsed into the response schema."""
    response = completion(
        model=MODEL,
        messages=messages,
        response_format=ChatResponse,
        reasoning_effort="low",
        allowed_openai_params=["reasoning_effort"],
        extra_body=EXTRA_BODY,
    )
    return parse_response(response.choices[0].message.content)


def parse_response(content: str | None) -> ChatResponse:
    """Structured response, degrading to a plain message when the JSON does not hold."""
    text = _strip_fences(content or "")
    for candidate in (text, _leading_object(text)):
        try:
            return ChatResponse.model_validate_json(candidate)
        except ValidationError:
            continue
    return ChatResponse(message=_as_prose(text))


def _leading_object(text: str) -> str:
    """Providers that ignore the schema sometimes trail characters past the last brace."""
    try:
        _, end = json.JSONDecoder().raw_decode(text)
    except ValueError:
        return ""
    return text[:end]


def _strip_fences(text: str) -> str:
    """Models occasionally wrap the JSON in a markdown code fence."""
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped
    body = stripped.split("\n", 1)[-1].removesuffix("```")
    return body.strip()


def _as_prose(text: str) -> str:
    """Broken JSON is not worth showing the user; anything else is a usable answer."""
    if not text or text.startswith("{"):
        return FALLBACK_MESSAGE
    return text
