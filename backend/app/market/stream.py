import asyncio
import json
from dataclasses import asdict

from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse

from app.market.cache import PriceCache

router = APIRouter()

SSE_INTERVAL_SECONDS = 0.5


async def price_event_generator(request: Request, cache: PriceCache):
    while True:
        if await request.is_disconnected():
            break
        for update in cache.snapshot():
            yield {"data": json.dumps(asdict(update))}
        await asyncio.sleep(SSE_INTERVAL_SECONDS)


@router.get("/api/stream/prices")
async def stream_prices(request: Request):
    cache: PriceCache = request.app.state.price_cache
    return EventSourceResponse(price_event_generator(request, cache))
