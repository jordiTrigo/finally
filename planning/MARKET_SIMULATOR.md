# Market Simulator Design

Design for the default, no-external-dependency market data source described in `PLAN.md` §6. Used whenever `MASSIVE_API_KEY` is not set — which is the common case for students running FinAlly without a Massive account.

## Goals

- Realistic-looking price action: smooth drift, occasional volatility, correlated moves across related tickers, occasional dramatic jumps.
- Deterministic given a seed, for testing.
- No external calls, no I/O — pure in-process computation, ticking every ~500ms per `PLAN.md` §6.
- Conforms to `MarketDataSource` from `MARKET_INTERFACE.md` — produces the same `PriceUpdate` shape as the Massive source.

## Price Model: Geometric Brownian Motion

Each ticker's price follows discrete-time GBM:

```
price_next = price_current * exp((mu - 0.5 * sigma**2) * dt + sigma * sqrt(dt) * Z)
```

- `mu` — annualized drift (expected return), per ticker
- `sigma` — annualized volatility, per ticker
- `dt` — time step as a fraction of a trading year. At a 500ms tick and ~252 trading days/6.5 trading hours each, `dt = 0.5 / (252 * 6.5 * 3600)`
- `Z` — a draw from the standard normal distribution, one per ticker per tick, correlated across tickers (see below)

GBM guarantees prices stay positive and produces the log-normal-ish, slightly-trending-with-noise behavior of a real short-term price series — it's the standard toy model for this and is cheap to compute per tick.

## Seed Prices and Per-Ticker Parameters

Starting prices approximate real-world levels so the demo looks plausible on first launch (`PLAN.md` §7 default watchlist):

| Ticker | Seed price | Sector |
|--------|-----------|--------|
| AAPL | 190.00 | Tech |
| GOOGL | 175.00 | Tech |
| MSFT | 420.00 | Tech |
| AMZN | 185.00 | Tech/Retail |
| TSLA | 250.00 | Auto/Tech |
| NVDA | 130.00 | Tech |
| META | 560.00 | Tech |
| JPM | 210.00 | Financials |
| V | 275.00 | Financials |
| NFLX | 680.00 | Media/Tech |

`mu` and `sigma` are assigned per sector rather than per ticker individually — e.g. tech tickers get a slightly higher `sigma` (~0.35 annualized) than financials (~0.20), and `mu` is a small positive drift (~0.05–0.10) for all, since a market that trends slowly upward with noise looks more like a real market than one that random-walks with zero drift. Exact values are tuning knobs, not load-bearing — the shape of the model matters more than the specific numbers.

## Correlated Moves

Real markets don't move ticker-by-ticker independently — sector peers and the broad market move together. Rather than a full covariance matrix (overkill for 10 tickers), each tick:

1. Draw one market-wide factor `Z_market ~ N(0, 1)`.
2. Draw one factor per sector `Z_sector ~ N(0, 1)`.
3. Draw one idiosyncratic factor per ticker `Z_ticker ~ N(0, 1)`.
4. Combine: `Z = w_market * Z_market + w_sector * Z_sector + w_idio * Z_ticker`, with weights summing so `Z` stays standard-normal-ish (e.g. `w_market=0.4, w_sector=0.3, w_idio=0.3` roughly, normalized so the combined variance is 1).

This gives tech names visibly co-moving on tech-heavy days, all ten tickers dipping together on a broad "market down" tick, while each still has its own noise — without simulating a full multi-asset correlation structure.

## Random Events

To avoid every tick looking like smooth noise, each tick has a small independent probability (e.g. ~0.1% per ticker per tick, roughly a few times per ticker per hour at 500ms ticks) of a one-off "event": an extra ±2–5% jump applied on top of the normal GBM step for that ticker only. This is what `PLAN.md` §6 calls "occasional random events for drama" — it's cosmetic, meant to occasionally give the watchlist a ticker flashing a big move, not a realistic jump-diffusion model.

## Update Cadence and Lifecycle

Matches the `MarketDataSource` protocol from `MARKET_INTERFACE.md`:

```python
class SimulatorMarketDataSource:
    def __init__(self, seed: int | None = None) -> None:
        self._rng = np.random.default_rng(seed)
        self._state: dict[str, TickerState] = {}

    async def run(self, cache: PriceCache, get_tickers: Callable[[], list[str]]) -> None:
        while True:
            z_market = self._rng.standard_normal()
            z_sector: dict[str, float] = {}
            for ticker in get_tickers():
                state = self._state.setdefault(ticker, self._init_state(ticker))
                sector = state.sector
                z_sector.setdefault(sector, self._rng.standard_normal())
                z = self._combine(z_market, z_sector[sector], self._rng.standard_normal())
                new_price = self._step(state, z)
                cache.update(PriceUpdate(
                    ticker=ticker,
                    price=new_price,
                    previous_price=state.price,
                    timestamp=datetime.now(UTC).isoformat(),
                    direction=_direction(new_price, state.price),
                ))
                state.price = new_price
            await asyncio.sleep(0.5)
```

- `_init_state(ticker)` looks up the seed price/sector table above; a ticker outside the default ten (added later via the watchlist) falls back to a generic seed price and "unknown" sector bucket with average `mu`/`sigma`.
- Seeded with `np.random.default_rng(seed)` — passing a fixed `seed` makes the whole sequence deterministic, which is what unit tests use; production runs with `seed=None` (OS entropy).
- One market-wide draw and one draw per sector per tick, then reused across every ticker in that sector, is what produces the correlation described above without an explicit covariance matrix.

## Code Structure

- `simulator.py` — `SimulatorMarketDataSource`, `TickerState`, the GBM step function, the correlation combination, and the event-injection check. Small module, no submodules needed for ten tickers and one model.
- `seed_prices.py` — the seed price/sector table above, as a plain dict. Kept separate from `simulator.py` so the tunable data (prices, sectors, `mu`/`sigma` per sector) is easy to find and adjust without touching the tick logic.

## Testing Implications

- With a fixed seed, `_step` and a full `run()` tick are fully deterministic — tests assert exact output values, not just "price changed within a range."
- Test that prices stay positive over a long simulated run (GBM guarantees this analytically, but worth a regression test given floating-point step accumulation).
- Test that two tickers in the same sector show non-zero correlation over many ticks (e.g. correlation coefficient of their returns is significantly above zero), and that the market-wide factor produces correlation across sectors too, just weaker.
- Test that a ticker added mid-run (simulating a watchlist addition) gets lazily initialized from the seed table and starts producing updates on the next tick, without restarting the source.
