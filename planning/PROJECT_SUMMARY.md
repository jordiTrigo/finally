# FinAlly — Project Summary

The single entry point for FinAlly. It carries the specification, the architecture, and the
current build state. The documents it was distilled from live in [`archive/`](#archive) and
remain the authority on their own subjects.

Last updated: 2026-07-27.

## 1. What FinAlly Is

FinAlly (Finance Ally) is an AI-powered trading workstation: it streams live market data,
lets the user trade a simulated portfolio, and puts an LLM assistant beside it that can
analyze positions and execute trades on request. It should look and feel like a modern
Bloomberg terminal with an AI copilot.

This is the capstone project for an agentic AI coding course, built entirely by coding
agents. Agents coordinate through files in `planning/` and `tasks/`.

**User experience.** One Docker command, browser opens `http://localhost:8001`, no login. The
user immediately sees ten default tickers with live-updating prices, $10,000 of virtual cash,
a dark data-dense terminal, and a chat panel. They can watch prices flash green/red, click a
ticker for a larger chart, buy and sell at the current price (market orders, instant fill, no
fees, no confirmation), watch a portfolio heatmap and P&L chart, and ask the AI to analyze or
trade for them.

**Visual design.** Dark backgrounds around `#0d1117`, muted gray borders, no pure black. Price
flashes fade over ~500ms. A connection dot shows green/yellow/red. Desktop-first.

Accent yellow `#ecad0a`, blue primary `#209dd7`, purple secondary `#753991` (submit buttons).

## 2. Build Status

| Area | State |
| --- | --- |
| Market data layer (`backend/app/market/`) | **Done** — simulator, Massive client, cache, SSE stream, 46 tests |
| App wiring (`backend/app/main.py`) | **Done** — lifespan, background source task, stream router |
| Market Data Demo (`backend/demo/`) | **Done** — live browser demo of the stream |
| Database layer (SQLite, schema, seed) | Not started |
| Portfolio + watchlist API | Not started |
| LLM chat integration | Not started |
| Frontend (Next.js) | Not started — `frontend/` is empty |
| Docker, scripts, E2E tests | Not started — `test/` is empty, no `scripts/` yet |

Two known stubs left deliberately in the completed work:

- `get_watchlist_tickers` in `backend/app/main.py` returns the seeded ten tickers directly.
  The DB layer replaces that one function body; nothing else in the market package changes,
  because it only depends on the `() -> list[str]` shape.
- No `/api/health` endpoint yet. It belongs to the API layer task.

## 3. Architecture

Single container, single port:

```
┌─────────────────────────────────────────────────┐
│  Docker Container (port 8001)                   │
│                                                 │
│  FastAPI (Python/uv)                            │
│  ├── /api/*          REST endpoints             │
│  ├── /api/stream/*   SSE streaming              │
│  └── /*              Static file serving        │
│                      (Next.js export)           │
│                                                 │
│  SQLite database (volume-mounted)               │
│  Background task: market data polling/sim       │
└─────────────────────────────────────────────────┘
```

| Decision | Rationale |
| --- | --- |
| SSE over WebSockets | One-way push is all that is needed; simpler, universal browser support |
| Static Next.js export | Single origin, no CORS, one port, one container |
| SQLite over Postgres | No auth means no multi-user; self-contained, zero config |
| Single Docker container | One command to run; no service orchestration |
| uv for Python | Fast, reproducible lockfile |
| Market orders only | No order book, no partial fills, simple portfolio math |

### Directory Structure

```
finally/
├── frontend/                 # Next.js TypeScript project (static export)
├── backend/                  # FastAPI uv project
│   ├── app/
│   │   ├── main.py           # FastAPI app, lifespan, market data wiring
│   │   └── market/           # Market data layer (see section 5)
│   ├── demo/                 # Market Data Demo (see section 9)
│   ├── tests/                # pytest suite
│   └── db/                   # Schema definitions, seed data, migrations
├── planning/                 # This summary, plus archive/
├── tasks/                    # Task briefs for agents
├── scripts/                  # start/stop helpers (mac + windows)
├── test/                     # Playwright E2E tests
├── db/                       # Volume mount target for finally.db
├── Dockerfile                # Multi-stage build (Node -> Python)
└── .env                      # Gitignored; .env.example committed
```

Boundaries that matter: `frontend/` knows nothing about Python and talks only to `/api/*`.
`backend/` owns all server logic. The market package never imports the watchlist model — it
receives a `() -> list[str]` callback, which is what keeps the layers separable.

## 4. Environment Variables

```bash
OPENROUTER_API_KEY=your-openrouter-api-key-here   # required for LLM chat
MASSIVE_API_KEY=                                  # optional; set -> real market data
MASSIVE_POLL_INTERVAL_SECONDS=15                  # optional; Massive poll cadence
LLM_MOCK=false                                    # optional; true -> deterministic mock LLM
```

- `MASSIVE_API_KEY` set and non-empty selects the Massive source; unset or empty selects the
  simulator.
- `MASSIVE_POLL_INTERVAL_SECONDS` defaults to 15, matching the free tier's 5 requests/minute.
  Paid plans can lower it to 2–15s.
- `LLM_MOCK=true` returns deterministic responses for E2E tests and CI.

## 5. Market Data Layer (implemented)

Two interchangeable sources write into one shared in-memory cache; the SSE endpoint reads the
cache and never the source. That indirection is what makes the sources swappable.

```
backend/app/market/
├── models.py       # PriceUpdate, ChangeDirection, compute_direction()
├── cache.py        # PriceCache
├── source.py       # MarketDataSource protocol
├── factory.py      # create_market_data_source()
├── seed_prices.py  # seed price / sector table + per-sector GBM params
├── simulator.py    # SimulatorMarketDataSource (default)
├── massive.py      # MassiveMarketDataSource (when MASSIVE_API_KEY is set)
└── stream.py       # SSE APIRouter for /api/stream/prices
```

**Data model.** Every update is a frozen `PriceUpdate(ticker, price, previous_price,
timestamp, direction)`. `ChangeDirection` subclasses `str`, so `json.dumps` emits
`"up"`/`"down"`/`"flat"` with no custom encoder. Direction is computed once at construction.

**Source protocol.** A `Protocol`, not an ABC — the two sources share a shape, not behavior.
One long-lived `run(cache, get_tickers)` coroutine per process. Ticker changes arrive through
the callback, so a watchlist add/remove needs no restart. No `stop()`; shutdown is ordinary
task cancellation.

**Simulator (default).** Geometric Brownian motion per ticker per 500ms tick, with
`dt = 0.5 / (252 * 6.5 * 3600)`. Each tick draws one market-wide factor, one factor per
sector, and one per ticker, combined with weights 0.4/0.3/0.3 (normalized) — that is what
produces correlated moves without a covariance matrix. Fully deterministic given a seed.

Occasional jumps add drama, and their size is load-bearing: at a 500ms tick the diffusion
step is only ~0.010%, so jumps must be sized against the tick, not against a daily move. The
original ±2–5% at 0.1% probability carried ~114x the diffusion variance, pushing realised
volatility to ~390% annualized and collapsing same-sector correlation to 0.008. Current
values are ±0.3–0.8% at 0.01% probability: correlation 0.547, hourly volatility 0.95%
(38% annualized against a 35% target), jumps still ~54x a normal tick.

**Massive source (optional).** Polls `get_snapshot_all` for the whole watchlist in one call
every `MASSIVE_POLL_INTERVAL_SECONDS`. The client is synchronous, so polls run via
`asyncio.to_thread`. Parsing happens inside the same `try` as the request: snapshot
sub-objects are `None` when the payload omits them, which happens around the daily reset, and
an unguarded parse would kill the background task permanently and freeze prices while the app
still looked healthy. Snapshots with no usable price are skipped individually. `previous_price`
comes from the cache rather than `prev_day.close`, so an unchanged price reports `FLAT`.

On the free tier, prices lag the market by ~15 minutes and nothing in the response signals it.

**SSE streaming.** `GET /api/stream/prices` pushes the whole cache every ~500ms at a fixed,
source-agnostic cadence. The simulator yields a genuinely new price each tick; Massive yields
the same price (re-sent, `FLAT`) between its polls. Clients use the native `EventSource` API,
which reconnects automatically.

## 6. API Endpoints

| Method | Path | Description | State |
| --- | --- | --- | --- |
| GET | `/api/stream/prices` | SSE stream of live price updates | Done |
| GET | `/api/portfolio` | Positions, cash, total value, unrealized P&L | To build |
| POST | `/api/portfolio/trade` | Execute a trade `{ticker, quantity, side}` | To build |
| GET | `/api/portfolio/history` | Portfolio value snapshots, full history, no pagination | To build |
| GET | `/api/watchlist` | Watchlist tickers with latest prices | To build |
| POST | `/api/watchlist` | Add a ticker `{ticker}` | To build |
| DELETE | `/api/watchlist/{ticker}` | Remove a ticker | To build |
| GET | `/api/chat` | Recent chat history, repopulates the panel on load | To build |
| POST | `/api/chat` | Send a message, receive message + executed actions | To build |
| GET | `/api/health` | Health check for Docker | To build |

## 7. Database

SQLite with lazy initialization: the backend creates the schema and seeds defaults on first
request if the file is missing or empty. No migration step, no manual setup. Every table
carries a `user_id` defaulting to `"default"`, so multi-user support needs no schema change.

- **users_profile** — `id`, `cash_balance` (default 10000.0), `created_at`
- **watchlist** — `id`, `user_id`, `ticker`, `added_at`; unique on `(user_id, ticker)`
- **positions** — `id`, `user_id`, `ticker`, `quantity`, `avg_cost`, `updated_at`; unique on
  `(user_id, ticker)`. Fractional shares supported
- **trades** — append-only log: `id`, `user_id`, `ticker`, `side`, `quantity`, `price`,
  `executed_at`
- **portfolio_snapshots** — `id`, `user_id`, `total_value`, `recorded_at`. Written every 30
  seconds and immediately after each trade
- **chat_messages** — `id`, `user_id`, `role`, `content`, `actions` (JSON, null for user
  messages), `created_at`

Seed data: one profile with $10,000, and ten watchlist rows — AAPL, GOOGL, MSFT, AMZN, TSLA,
NVDA, META, JPM, V, NFLX.

## 8. LLM Integration

Use the `cerebras-inference` skill: LiteLLM via OpenRouter to `openrouter/openai/gpt-oss-20b:free`
with Cerebras as the inference provider, using structured outputs.

Per message the backend loads portfolio context and the last 20 chat messages (10 turns, to
bound prompt growth), calls the LLM, parses the structured response, auto-executes any trades
and watchlist changes, persists the message and its actions, and returns the whole thing at
once — Cerebras is fast enough that a loading indicator beats token streaming.

```json
{
  "message": "Your conversational response to the user",
  "trades": [{"ticker": "AAPL", "side": "buy", "quantity": 10}],
  "watchlist_changes": [{"ticker": "PYPL", "action": "add"}]
}
```

Trades execute without a confirmation dialog — deliberately, since the money is fake and the
point is to demonstrate agentic behavior. Failed validation (insufficient cash or shares) is
returned in the response so the assistant can explain it. The system prompt casts the model as
"FinAlly, an AI trading assistant": analyze concentration and P&L, suggest trades with
reasoning, manage the watchlist, stay concise and data-driven, always emit valid JSON.

## 9. Market Data Demo

A standalone demo of the finished layer, so the streaming stack can be seen working before
the real frontend exists:

```bash
cd backend
uv run python demo/market_data_demo.py
```

It starts the real FastAPI app, serves a small page at `http://127.0.0.1:8020`, and opens a
browser. The page consumes `/api/stream/prices` through the native `EventSource` API and
renders the watchlist with flashing prices, sparklines, and a connection indicator — the same
contract the Next.js frontend will implement. `--no-browser` and `--port` are supported.

The demo adds a route to the app object at runtime, so it changes nothing in production code.

## 10. Frontend Plan

Single-page app, dense terminal layout. Component architecture is the Frontend Engineer's
call, but it must include: watchlist panel with sparklines accumulated client-side from SSE
(session-only by design — a refresh restarts them), a main chart for the selected ticker, a
portfolio treemap colored by P&L, a P&L line chart from `portfolio_snapshots`, a positions
table, a trade bar with inline errors on failure, a collapsible AI chat panel that loads
history via `GET /api/chat`, and a header with live total value, cash, and connection status.

Lightweight Charts (canvas) for the price and P&L line charts; Recharts (SVG) for the treemap,
since Lightweight Charts has no treemap primitive. Tailwind CSS with a custom dark theme.

## 11. Testing

**Backend (pytest):** market data (GBM math, correlation, volatility budget, Massive parsing
and failure handling, protocol conformance), portfolio math and trade edge cases, LLM
structured-output parsing, API route shapes and status codes.

**Frontend:** component rendering with mock data, flash animation on price change, watchlist
CRUD, portfolio calculations, chat rendering and loading state.

**E2E (Playwright, in `test/`):** a `docker-compose.test.yml` running the app plus a Playwright
container, with `LLM_MOCK=true`. Scenarios: fresh start, watchlist add/remove, buy, sell,
visualizations, mocked AI chat, SSE reconnection.

Conventions worth keeping, learned the hard way in the market data work:

- `httpx.ASGITransport` buffers whole responses, so it cannot test an endless SSE stream — it
  hangs before the status line. Drive a real uvicorn server instead (`tests/test_app.py`).
- Do not stub `massive` in `sys.modules`; the stub leaks across the session and hides real API
  drift. Monkeypatch `app.market.massive.RESTClient` instead.
- Lifecycle tests monkeypatch `TICK_INTERVAL_SECONDS` / `SSE_INTERVAL_SECONDS` rather than
  sleeping on the production cadence.

## 12. Docker and Deployment

Multi-stage build: Node 20 slim builds the Next.js static export, then Python 3.12 slim
installs `uv`, runs `uv sync` from the committed lockfile, copies the frontend build into
`static/`, exposes 8001, and runs uvicorn.

```bash
docker run -v finally-data:/app/db -p 8001:8001 --env-file .env finally
```

`scripts/start_mac.sh`, `stop_mac.sh`, `start_windows.ps1`, `stop_windows.ps1` wrap this. All
must be idempotent. Stopping never removes the volume. Cloud deployment (App Runner, Render)
is a stretch goal.

## Archive

Source documents, still authoritative on their own subjects:

| Document | Subject |
| --- | --- |
| [`archive/PLAN.md`](archive/PLAN.md) | The original full specification, including the resolved doc-review questions |
| [`archive/MARKET_DATA_DESIGN.md`](archive/MARKET_DATA_DESIGN.md) | Implementation-ready market data design, with code for every module |
| [`archive/MARKET_INTERFACE.md`](archive/MARKET_INTERFACE.md) | The unified source interface and why it is a Protocol |
| [`archive/MARKET_SIMULATOR.md`](archive/MARKET_SIMULATOR.md) | The GBM model, correlation factors, and event sizing |
| [`archive/MASSIVE_API.md`](archive/MASSIVE_API.md) | Massive (ex-Polygon) REST reference, rate limits, response shapes |
| [`archive/MARKET_DATA_REVIEW.md`](archive/MARKET_DATA_REVIEW.md) | Code review of the market data layer and how each finding was resolved |
| [`archive/PROMPT-INIT.md`](archive/PROMPT-INIT.md) | The prompt that produced the three market data research documents |
