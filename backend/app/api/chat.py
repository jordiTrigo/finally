"""Chat routes: conversation history and one-shot message handling.

The response is complete JSON, not a token stream - Cerebras answers fast enough that a
loading indicator beats streaming. The model call is synchronous, so it runs on a worker
thread to keep the price SSE stream flowing while the assistant thinks.
"""

import asyncio

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from app.db import get_chat_messages
from app.llm import ChatAction, HISTORY_LIMIT, respond

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)


class ChatMessageOut(BaseModel):
    id: str
    role: str
    content: str
    actions: list[ChatAction] | None
    created_at: str


class ChatHistoryOut(BaseModel):
    messages: list[ChatMessageOut]


class ChatReplyOut(BaseModel):
    message: str
    actions: list[ChatAction]


@router.get("")
async def read_chat() -> ChatHistoryOut:
    return ChatHistoryOut(messages=get_chat_messages(limit=HISTORY_LIMIT))


@router.post("")
async def send_message(request: Request, body: ChatRequest) -> ChatReplyOut:
    cache = request.app.state.price_cache
    message, actions = await asyncio.to_thread(respond, body.message, cache)
    return ChatReplyOut(message=message, actions=actions)
