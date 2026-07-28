# FinAlly Team Contract

Six engineers build the rest of FinAlly. `planning/PROJECT_SUMMARY.md` is the specification;
this document is the coordination layer. It says who owns what, which interfaces are frozen,
and how work flows between people.

Read this before touching code. If you need something that crosses a boundary below, ask its
owner rather than reaching across it.

## 1. The Team

| Engineer | Owns | Agent |
| --- | --- | --- |
| Database Engineer | `backend/app/db/`, `backend/tests/db/` | `database-engineer` |
| Backend API Engineer | `backend/app/api/` (except chat), `backend/app/main.py`, `backend/tests/api/` | `backend-api-engineer` |
| LLM Engineer | `backend/app/llm/`, `backend/app/api/chat.py`, `backend/tests/llm/` | `llm-engineer` |
| Frontend Engineer | `frontend/` | `frontend-engineer` |
| DevOps Engineer | `Dockerfile`, `docker-compose.yml`, `.dockerignore`, `scripts/`, `.env.example` | `devops-engineer` |
| Integration Tester | `test/`, `planning/E2E_REPORT.md` | `integration-tester` |

Nobody edits another engineer's files. The market data layer (`backend/app/market/`) is
finished and closed - it is nobody's to change.

## 2. Build Order

```
Wave 1   Database Engineer          Frontend Engineer
            (schema, repos)            (whole UI, mocked API)
              |
Wave 2   Backend API Engineer
            (portfolio, watchlist, health, snapshots)
              |
Wave 3   LLM Engineer
            (chat, structured outputs, auto-execution)
              |
Wave 4   DevOps Engineer
            (image, scripts, one-command run)
              |
Wave 5   Integration Tester
            (E2E, then fixes routed back to owners)
```

The Frontend Engineer starts in wave 1 because the API contract in section 4 is frozen up
front - the UI is written against the contract, not against a running server.

## 3. Database Interface (frozen)

The Database Engineer implements this; everyone else calls it and writes no SQL.

```python
from app.db import (
    init_db,                  # idempotent: create schema + seed if missing
    get_connection,           # sqlite3 connection to FINALLY_DB_PATH

    get_profile,              # -> {"id", "cash_balance", "created_at"}
    get_cash_balance,         # -> float
    set_cash_balance,         # (amount: float) -> None

    get_watchlist,            # -> list[str], insertion order
    add_to_watchlist,         # (ticker: str) -> bool, False if already present
    remove_from_watchlist,    # (ticker: str) -> bool, False if absent

    get_positions,            # -> list[{"ticker", "quantity", "avg_cost", "updated_at"}]
    get_position,             # (ticker: str) -> position dict or None

    execute_trade,            # (ticker, side, quantity, price) -> TradeResult
    get_trades,               # (limit: int | None) -> list of trade dicts, newest first

    record_snapshot,          # (total_value: float) -> None
    get_snapshots,            # -> list[{"total_value", "recorded_at"}], oldest first

    get_chat_messages,        # (limit: int | None) -> list of message dicts, oldest first
    add_chat_message,         # (role, content, actions: dict | None) -> message dict
)
```

Every function takes a trailing `user_id: str = "default"`.

`execute_trade` is the single source of truth for trade math - cash checks, average cost,
close-out of a position that reaches zero. It returns a result carrying success, the resulting
cash balance, and an error message when validation fails. It raises nothing on a rejected
trade; callers inspect the result. The API layer and the LLM layer both call this one function.

Money is REAL, quantities are REAL (fractional shares), timestamps are ISO-8601 UTC strings.
Path comes from `FINALLY_DB_PATH`, defaulting to `db/finally.db` at the project root.

## 4. API Contract (frozen)

The frontend codes against this before the backend exists. Shapes are fixed; adding fields is
allowed, renaming or removing is not.

```
GET  /api/health              -> {"status": "ok"}

GET  /api/portfolio           -> {"cash_balance": float,
                                  "positions": [{"ticker", "quantity", "avg_cost",
                                                 "current_price", "market_value",
                                                 "unrealized_pnl", "pnl_percent"}],
                                  "positions_value": float,
                                  "total_value": float,
                                  "total_unrealized_pnl": float}

POST /api/portfolio/trade     {"ticker": str, "side": "buy"|"sell", "quantity": float}
                              -> 200 {"ticker", "side", "quantity", "price",
                                      "executed_at", "cash_balance"}
                              -> 400 {"detail": "Insufficient cash: need $X, have $Y"}

GET  /api/portfolio/history   -> {"snapshots": [{"total_value", "recorded_at"}]}

GET  /api/watchlist           -> {"tickers": [{"ticker", "price", "previous_price",
                                               "direction"}]}
POST /api/watchlist           {"ticker": str} -> 201 {"ticker"} | 409 already present
DELETE /api/watchlist/{ticker} -> 204 | 404 not present

GET  /api/chat                -> {"messages": [{"id", "role", "content", "actions",
                                                "created_at"}]}
POST /api/chat                {"message": str}
                              -> {"message": str,
                                  "actions": [{"type": "trade"|"watchlist",
                                               "status": "executed"|"failed",
                                               "detail": str}]}

GET  /api/stream/prices       SSE, already built. Each event:
                              {"ticker", "price", "previous_price", "timestamp", "direction"}
                              direction is "up" | "down" | "flat"
```

Tickers are uppercase everywhere. A price is `null` when the cache has not seen the ticker yet -
the UI must render that state rather than assume a number.

## 5. Shared Conventions

- Python is managed with `uv`. Always `uv run ...`, never bare `python3`; `uv add ...`, never
  `pip install`.
- Prices are read from the shared `PriceCache` on `app.state.price_cache`. No layer polls a
  market source directly.
- Short modules, short functions, clear names. Docstrings over inline comments. No defensive
  programming, no speculative abstraction, no emojis anywhere in code, logs, or output.
- Every engineer writes their own unit tests. `uv run pytest` from `backend/` and `npm test`
  from `frontend/` must pass before anyone reports done.
- Root cause before fix. Reproduce, prove, then change code.

## 6. Reporting Issues

The Integration Tester finds bugs; the owning engineer fixes them. Findings go in
`planning/E2E_REPORT.md`, one entry each:

```
### <short title>
Owner:    Database | Backend API | LLM | Frontend | DevOps
Steps:    what was done
Expected: what should have happened
Actual:   what happened, with evidence
Verdict:  product bug | flaky test
```

Nobody fixes a bug outside their own files. If a fix needs a change on both sides of a
boundary, both owners make their own half.
