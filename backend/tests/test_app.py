"""End-to-end tests over a real uvicorn server.

`httpx.ASGITransport` buffers the whole response, so an endless SSE generator
never yields under it. These tests therefore drive a real server on a real
socket - the only way to observe the stream incrementally.
"""

import asyncio
import contextlib
import json

import uvicorn
from httpx import AsyncClient

from app.main import DEFAULT_WATCHLIST, app


@contextlib.asynccontextmanager
async def serving():
    config = uvicorn.Config(app, host="127.0.0.1", port=0, log_level="warning")
    server = uvicorn.Server(config)
    task = asyncio.create_task(server.serve())
    try:
        while not server.started:
            await asyncio.sleep(0.01)
        port = server.servers[0].sockets[0].getsockname()[1]
        async with AsyncClient(base_url=f"http://127.0.0.1:{port}") as client:
            yield client
    finally:
        server.should_exit = True
        with contextlib.suppress(asyncio.CancelledError):
            await task


async def read_events(client, count, timeout=10.0):
    events = []
    async with asyncio.timeout(timeout):
        async with client.stream("GET", "/api/stream/prices") as response:
            assert response.status_code == 200
            assert response.headers["content-type"].startswith("text/event-stream")
            async for line in response.aiter_lines():
                if line.startswith("data:"):
                    events.append(json.loads(line[len("data:"):]))
                if len(events) >= count:
                    break
    return events


async def test_streamed_event_carries_exactly_the_fields_the_frontend_reads():
    async with serving() as client:
        events = await read_events(client, 1)

    assert set(events[0]) == {"ticker", "price", "previous_price", "timestamp", "direction"}


async def test_stream_covers_the_whole_watchlist_with_valid_prices():
    async with serving() as client:
        events = await read_events(client, len(DEFAULT_WATCHLIST))

    assert {e["ticker"] for e in events} == set(DEFAULT_WATCHLIST)
    assert all(e["price"] > 0 for e in events)
    assert {e["direction"] for e in events} <= {"up", "down", "flat"}


async def test_background_source_keeps_refreshing_prices():
    """A frozen cache would still stream, so assert the prices actually move."""
    async with serving() as client:
        events = await read_events(client, 3 * len(DEFAULT_WATCHLIST))

    aapl = [e["price"] for e in events if e["ticker"] == "AAPL"]
    assert len(set(aapl)) > 1, "AAPL price never changed across ticks"
