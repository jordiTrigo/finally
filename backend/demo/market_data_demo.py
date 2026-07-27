"""Market Data Demo - watch the live price stream in a browser.

Runs the real FastAPI app from `app.main` and serves a small page that consumes
`/api/stream/prices` through the native EventSource API. The demo route is added
to the app object here at runtime, so nothing in production code changes.

    uv run python demo/market_data_demo.py
    uv run python demo/market_data_demo.py --port 9000 --no-browser
"""

import argparse
import pathlib
import threading
import webbrowser

import uvicorn
from fastapi.responses import HTMLResponse

from app.main import DEFAULT_WATCHLIST, app
from app.market.factory import create_market_data_source

PAGE = pathlib.Path(__file__).with_name("index.html")


@app.get("/", include_in_schema=False)
async def demo_page() -> HTMLResponse:
    return HTMLResponse(PAGE.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description="FinAlly market data demo")
    parser.add_argument("--port", type=int, default=8020)
    parser.add_argument("--no-browser", action="store_true", help="do not open a browser")
    args = parser.parse_args()

    url = f"http://127.0.0.1:{args.port}"
    source = type(create_market_data_source()).__name__

    print("FinAlly - Market Data Demo")
    print(f"  source:    {source}")
    print(f"  watchlist: {', '.join(DEFAULT_WATCHLIST)}")
    print(f"  open:      {url}")
    print("  stop:      ctrl-c")

    if not args.no_browser:
        threading.Timer(1.0, webbrowser.open, args=(url,)).start()

    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
