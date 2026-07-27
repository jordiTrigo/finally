# FinAlly — AI Trading Workstation

A visually stunning AI-powered trading workstation that streams live market data, simulates portfolio trading, and integrates an LLM chat assistant that can analyze positions and execute trades via natural language.

Built entirely by coding agents as a capstone project for an agentic AI coding course. The full specification lives in [`planning/PROJECT_SUMMARY.md`](planning/PROJECT_SUMMARY.md).

## Features

- **Live price streaming** via SSE with green/red flash animations
- **Simulated portfolio** — $10k virtual cash, market orders, instant fills
- **Portfolio visualizations** — heatmap (treemap), P&L chart, positions table
- **AI chat assistant** — analyzes holdings, suggests and auto-executes trades
- **Watchlist management** — track tickers manually or via AI
- **Dark terminal aesthetic** — Bloomberg-inspired, data-dense layout

## Architecture

Single Docker container serving everything on port 8001:

- **Frontend**: Next.js (static export) with TypeScript and Tailwind CSS
- **Backend**: FastAPI (Python/uv) with SSE streaming
- **Database**: SQLite with lazy initialization
- **AI**: LiteLLM → OpenRouter (Cerebras inference) with structured outputs
- **Market data**: Built-in GBM simulator (default) or Massive API (optional)

## Status

The market data backend is built and tested: GBM simulator, optional Massive client, shared
price cache, and the SSE stream, wired into a FastAPI app. The database layer, portfolio and
chat APIs, frontend, and Docker packaging are not started yet.

To see the streaming stack working:

```bash
cd backend
uv run python demo/market_data_demo.py
```

See [`planning/PROJECT_SUMMARY.md`](planning/PROJECT_SUMMARY.md) for the full spec and current
build state.

## Environment Variables

| Variable | Required | Description |
| --- | --- | --- |
| `OPENROUTER_API_KEY` | Yes | OpenRouter API key for AI chat |
| `MASSIVE_API_KEY` | No | Massive (Polygon.io) key for real market data; omit to use simulator |
| `MASSIVE_POLL_INTERVAL_SECONDS` | No | Massive polling interval in seconds (default `15`) |
| `LLM_MOCK` | No | Set `true` for deterministic mock LLM responses (testing) |

Copy `.env.example` to `.env` and fill in your `OPENROUTER_API_KEY` to get started.

## Project Structure

```text
finally/
├── frontend/    # Next.js static export
├── backend/     # FastAPI uv project
├── planning/    # PROJECT_SUMMARY.md, plus archive/ of source documents
├── test/        # Playwright E2E tests
├── db/          # SQLite volume mount (runtime)
└── scripts/     # Start/stop helpers
```

## License

See [LICENSE](LICENSE).
