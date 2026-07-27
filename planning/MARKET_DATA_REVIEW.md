# Market Data Backend — Code Review

Review of the market data layer (`backend/app/market/`, `backend/tests/market/`) against
`MARKET_DATA_DESIGN.md`, `MARKET_INTERFACE.md`, `MARKET_SIMULATOR.md`, `MASSIVE_API.md`, and
`PLAN.md` §6.

Reviewed at commit `1595914`. Date: 2026-07-27.

## Verdict

The implementation is a faithful, clean translation of `MARKET_DATA_DESIGN.md` — module
layout, data model, cache, protocol, factory, and SSE endpoint match the spec essentially
verbatim, and the layer genuinely works end to end (verified against a live uvicorn server,
see "Verified working" below). Code quality is good: short modules, no defensive clutter, no
overengineering.

Two issues need fixing before this layer is built on:

1. **One test fails** — the simulator's correlation test. Root cause traced to a parameter
   scaling conflict in the spec itself, not a coding error (Finding 1).
2. **The Massive source dies permanently on a malformed snapshot** — a real robustness gap
   versus the design's stated error handling (Finding 2).

The rest are medium/low severity: a missing lockfile, a test-isolation leak that shadows the
real `massive` package, and some test-coverage gaps.

## How this review was run

```bash
cd backend
uv run pytest -q --durations=8      # full suite
```

Environment: Python 3.12, `uv` 0.7.15, 33 packages installed from `pyproject.toml`.
`massive` resolved to the real published package, version **2.8.0**.

Findings below were each verified by a targeted probe script rather than inferred from
reading; the measured numbers are quoted inline.

## Test results

```
1 failed, 33 passed in 3.62s
FAILED tests/market/test_simulator.py::test_same_sector_tickers_correlate_more_than_cross_sector
        assert np.float64(0.008307820772141419) > 0.3
```

No warnings. Slowest tests are the three timing-coupled simulator tests (1.20s, 0.60s,
0.60s), which together are ~2.4s of the 3.6s runtime.

## Findings

### 1. HIGH — Correlation test fails: event jumps swamp the correlated signal

`test_same_sector_tickers_correlate_more_than_cross_sector` measures same-sector correlation
at **0.0083**, against a threshold of 0.3.

**Root cause (proven, not guessed).** The correlation machinery in `_combine` is
mathematically correct. Re-running the identical measurement with `EVENT_PROB = 0`:

| Configuration | same-sector | cross-sector | per-tick return std |
|---|---|---|---|
| Events ON (as shipped) | 0.0083 | 0.0032 | 9.37e-04 |
| Events OFF (`EVENT_PROB=0`) | **0.7513** | **0.4673** | 1.02e-04 |
| Theoretical from weights | 0.7353 | 0.4706 | — |

With events disabled the measured correlations land within noise of the values implied by
`W_MARKET/W_SECTOR/W_IDIO` — `(0.4²+0.3²)/0.34 = 0.735` same-sector and `0.4²/0.34 = 0.471`
cross-sector. The factor model is right.

What breaks it is the scale mismatch between the two effects, both of which
`MARKET_SIMULATOR.md` specifies literally:

- `DT = 8.479e-08`, so a typical tick is `sigma*sqrt(DT)` = **0.0102%**.
- An event jump is **2–5%**, i.e. 200–500x a normal tick.
- At `EVENT_PROB = 0.001`, the event term contributes **~114x** the variance of the diffusion
  term (`1.18e-06` vs `1.04e-08`).

Event draws are independent per ticker, so this ~99%-of-variance idiosyncratic term drowns
the correlated diffusion component. Both spec requirements are individually implemented
correctly; they cannot both hold at these parameter values.

**Consequence beyond the failing test.** The GBM model is effectively cosmetic — the series
is really a jump process. Measured over 200 runs of one simulated trading hour (7200 ticks),
AAPL seeded at $190.00:

```
mean=189.78  median=189.06  min=146.56  max=240.60
pct change: std=9.6%  p5=-15.7%  p95=+15.3%
```

9.6% standard deviation per hour annualizes to roughly **390% volatility**, versus the
**35%** the tech sector params intend — about 11x too volatile. Over a demo session, prices
drift far from the carefully chosen realistic seed levels, which undercuts the reason those
seeds exist.

**Recommendation.** Two independent changes:

- *Fix the test to measure what it claims*: assert correlation on the diffusion component
  (run the measurement with events disabled). Correlation is a property of the factor model;
  testing it through a dominant independent jump term tests nothing useful.
- *Separately, decide the volatility budget* (a product call, not a test fix). To put events
  at ~25% of tick variance while keeping them visibly dramatic, a magnitude of ~0.3–0.8%
  with `EVENT_PROB ≈ 1e-4` gives roughly one jump per ticker per hour at ~50x a normal tick
  — still an obvious flash in the UI — and brings hourly movement to ~0.97%, which is exactly
  what 35% annualized vol implies. If ±2–5% jumps are considered essential to the demo, that
  is a legitimate choice, but the seed prices and sector `sigma` values then stop being
  meaningful and the docs should say so.

### 2. HIGH — A malformed Massive snapshot kills the price stream permanently

In `massive.py`, the `try/except` wraps only the `asyncio.to_thread` call; the parsing loop
sits outside it (`massive.py:46-57`). `MassiveMarketDataSource.run` has no exception handling
of its own.

Verified against the **real** `massive` 2.8.0 client — omitted fields deserialize to `None`:

```python
>>> TickerSnapshot.from_dict({'ticker': 'AAPL'})
last_trade: None | day: None | prev_day: None
```

So `snap.day.close` and `snap.prev_day.close` raise `AttributeError`. This is not
hypothetical: `MASSIVE_API.md` explicitly warns that snapshot data "resets daily around
3:30 AM ET and repopulates as exchanges report" and that "snapshots may be empty or reflect
the prior session."

Reproduced with one snapshot lacking `last_trade` and `day`:

```
task done after malformed snapshot? True
  escaped exception: AttributeError: 'NoneType' object has no attribute 'close'
  polls attempted: 1
  cache after: []
```

The background task dies after a single poll. Because nothing awaits that task in the
intended wiring (`MARKET_DATA_DESIGN.md` §12 creates it with `asyncio.create_task` and only
awaits it at shutdown), the exception is never surfaced — prices simply freeze forever while
the app appears healthy and the SSE stream keeps serving a stale (or empty) cache.

This directly contradicts design §10: "A failed poll (network error, HTTP 429 rate limit,
**bad response**) is logged and skipped."

**Recommendation.** Move the parse loop inside the `try`, and skip individual snapshots with
no usable price rather than letting one bad entry discard a whole good poll:

```python
for snap in snapshots:
    price = _price_from(snap)      # returns None if last_trade and day are both absent
    if price is None:
        continue
    ...
```

Add tests for: snapshot with all price fields `None`; snapshot with `prev_day` `None` and no
prior cache entry.

### 3. MEDIUM — `uv.lock` is not committed

`git status` shows `uv.lock` as untracked — it did not exist before this review generated it.

This contradicts two documented expectations:

- `PLAN.md` §11, Dockerfile stage 2: "`uv sync` (install Python dependencies **from
  lockfile**)".
- `MARKET_DATA_DESIGN.md` §3: `massive` stays a hard dependency "to keep the **lockfile** and
  image reproducible."

Without it, every Docker build re-resolves against whatever is on PyPI that day, so the image
is not reproducible and `numpy`/`fastapi`/`massive` can shift under the app silently.

**Recommendation.** Commit `uv.lock`.

### 4. MEDIUM — Tests permanently shadow the real `massive` package

`tests/market/test_massive.py:14-17` injects a stub module into `sys.modules` at import time,
guarded by `if "massive" not in sys.modules`. That guard always fires: nothing imports
`massive` before test collection, so **the stub always wins**, and it is never removed for the
rest of the session.

Verified — with the real 2.8.0 package installed, `massive` still resolves to the stub:

```
massive resolved to: STUB (no __file__)
```

Two consequences:

- Nothing in the suite ever imports the real client. If `RESTClient` were renamed, moved, or
  its `get_snapshot_all` signature changed, every test would still pass. That is precisely
  the integration risk worth catching, and the comment's premise ("the test environment may
  not have network access to install it") does not hold — `massive` is a hard dependency that
  installs from the lockfile like any other.
- It leaks across modules. `test_factory.py:26-31` branches on `"massive" in sys.modules`, so
  its behavior depends on whether `test_massive.py` was collected first — order-dependent
  tests that happen to pass today.

For the record, the real API surface does match the code:

```
get_snapshot_all(self, market_type, tickers=None, params=None, raw=False, ...)
TickerSnapshot fields: ['day', 'last_quote', 'last_trade', 'min', 'prev_day', 'ticker', ...]
LastTrade has price: True   Agg has close: True
```

**Recommendation.** Delete the `sys.modules` stub and the conditional in `test_factory.py`.
The fixtures already monkeypatch `massive_module.RESTClient`, which is the correct seam and
undoes itself. Letting the real package import is what makes these tests meaningful.

### 5. LOW — Wasted RNG draws from eager `setdefault`

`simulator.py:67`:

```python
z_sector.setdefault(state.sector, self._rng.standard_normal())
```

Python evaluates arguments eagerly, so a normal draw is taken for **every ticker** and
discarded whenever the sector key already exists (verified: 5 draws consumed for 5
same-sector tickers, 1 would be ideal).

Not a correctness bug — the first stored value is still shared across the sector, so
correlation is preserved. But it contradicts the design's "One market draw and one draw per
sector per tick", and it makes the RNG stream depend on watchlist size and ordering, which
weakens the determinism guarantee that seeded runs are supposed to provide.

**Recommendation.**

```python
if state.sector not in z_sector:
    z_sector[state.sector] = self._rng.standard_normal()
```

### 6. LOW — No FastAPI wiring; the layer is not runnable as shipped

`MARKET_DATA_DESIGN.md` §12 specifies `main.py` — the lifespan handler that creates
`PriceCache`, sets `app.state.price_cache`, and launches the source task. No `main.py` exists,
and nothing includes the exported `router`.

This is reasonable if it is being deferred until the DB layer provides
`get_watchlist_tickers`, and it is arguably outside "the market data layer". Flagging it only
so it is not assumed done: to test end to end I had to hand-wire the app myself. Worth an
explicit entry in the task list.

### 7. LOW — Test coverage gaps

- **`seed_for` fallback is untested.** `DEFAULT_SEED_PRICE` and the `"unknown"` sector are the
  path every user-added ticker takes, and no test covers it.
  `test_ticker_added_mid_run_is_lazily_initialized` adds MSFT, which is in the seed table, so
  the fallback branch never runs.
- **The `previous_price` chaining invariant is untested.** Nothing asserts that a tick's
  `previous_price` equals the prior tick's `price` for the same ticker. A regression here
  would silently corrupt every flash animation in the UI. (Behavior is currently correct —
  observed `189.972 -> prev=189.972` in the live run.)
- **`test_stream_prices_route_reads_cache_from_app_state` does not test its own name.** It
  asserts only `isinstance(response, EventSourceResponse)`; it never checks the response
  streams the cache taken from `app.state`. Either assert on the emitted payload or rename it.
- **No test mounts the router on a real app.** Note for whoever adds one: `httpx`
  `ASGITransport` buffers the entire response, so an infinite SSE generator hangs under it
  regardless of the app code (confirmed — a trivial infinite generator hangs identically).
  An end-to-end SSE test needs a live server (`uvicorn.Server` in-process works well).
- **Massive: no test for a watchlist ticker the API omits** from its response.

### 8. LOW — Timing-coupled simulator tests

Three tests sleep 0.6–1.2s against the real 500ms cadence, making up two thirds of the suite
runtime and risking flakiness on a loaded CI machine. `test_stream.py` already solves this by
monkeypatching `SSE_INTERVAL_SECONDS`; `simulator.py` exposes `TICK_INTERVAL_SECONDS` for
exactly the same purpose but no test uses it. Worth making consistent.

### 9. NIT — Redundant asyncio configuration

`pyproject.toml` sets `asyncio_mode = "auto"` while tests also carry explicit
`@pytest.mark.asyncio` markers. Harmless, but pick one.

### 10. NIT — `direction` names a function and a field

`models.py` exports a function `direction()` while `PriceUpdate` has a `direction` field,
yielding `direction=direction(new_price, state.price)` at call sites. Reads awkwardly;
`compute_direction()` would be clearer. Cosmetic only.

## Verified working

Confirmed by running a real `uvicorn` server with the router mounted and connecting a real
HTTP client (not `ASGITransport`):

```
source selected: SimulatorMarketDataSource
status: 200 | content-type: text/event-stream; charset=utf-8
  t=0.14s AAPL  price= 189.972 prev= 190.000 dir=down
  t=0.14s MSFT  price= 419.947 prev= 420.000 dir=down
  t=0.14s JPM   price= 210.001 prev= 210.000 dir=up
  t=0.64s AAPL  price= 189.998 prev= 189.972 dir=up
  ...
distinct tickers streamed: ['AAPL', 'JPM', 'MSFT']
keys per event: ['direction', 'previous_price', 'price', 'ticker', 'timestamp']
clean shutdown: OK
```

- Correct `text/event-stream` content type and SSE framing.
- Fixed ~500ms cadence (events at t=0.14, 0.64, 1.15).
- Payload is exactly the serialized `PriceUpdate` — the five fields `PLAN.md` §6 requires,
  with `ChangeDirection` serializing as a plain `"up"`/`"down"` string via `json.dumps`, no
  custom encoder, as designed.
- `previous_price` correctly chains from the prior tick; directions are consistent.
- Per-tick moves of ~2-3 cents on a $190 stock — the right magnitude for the UI's flash
  animation.
- Task cancellation shuts down cleanly.

## Design conformance

| Design element | Status |
|---|---|
| Module layout (§2) | Matches exactly, all 9 modules |
| `PriceUpdate` / `ChangeDirection` / `direction()` (§4) | Matches; frozen dataclass, str-Enum, JSON-clean |
| `PriceCache` (§5) | Matches verbatim |
| `MarketDataSource` protocol (§6) | Matches; `Protocol`, no `stop()` |
| Factory with deferred imports (§7) | Matches; simulator path never imports `massive` |
| Seed prices / sector params (§8) | Matches verbatim |
| Simulator GBM + correlation + events (§9) | Implemented as written; parameter conflict per Finding 1 |
| Massive poller (§10) | Matches, except error handling narrower than specified (Finding 2) |
| SSE endpoint (§11) | Matches; generator extracted for testability, a good change |
| FastAPI wiring (§12) | Not implemented (Finding 6) |
| Env vars (§13) | Both handled; default 15s confirmed by test |
| Testing plan (§14) | Mostly covered; gaps in Finding 7 |

Two small deviations from the design code, both improvements: `price_event_generator` is
extracted from the route handler so it can be tested directly, and the tick/stream intervals
are named constants rather than literals.

## Recommended next steps

In priority order:

1. Fix the correlation test to measure the diffusion component (Finding 1), and decide
   separately whether the event volatility budget is intended.
2. Move Massive's parse loop inside the `try` and skip unusable snapshots (Finding 2).
3. Commit `uv.lock` (Finding 3).
4. Remove the `sys.modules` stub from `test_massive.py` and the conditional in
   `test_factory.py` (Finding 4).
5. Fix the eager `setdefault` draw (Finding 5).
6. Close the test gaps in Finding 7, particularly `seed_for` fallback and the
   `previous_price` chaining invariant.
