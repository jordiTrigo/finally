from dataclasses import dataclass


@dataclass(frozen=True)
class SectorParams:
    mu: float     # annualized drift
    sigma: float  # annualized volatility


# Per-sector GBM params. Tech is noisier than financials; all drift slightly up
# so the market trends upward with noise rather than pure random-walking.
SECTOR_PARAMS: dict[str, SectorParams] = {
    "tech":       SectorParams(mu=0.10, sigma=0.35),
    "financials": SectorParams(mu=0.06, sigma=0.20),
    "media":      SectorParams(mu=0.08, sigma=0.30),
    "unknown":    SectorParams(mu=0.05, sigma=0.25),  # fallback for added tickers
}

# ticker -> (seed_price, sector)
SEED_PRICES: dict[str, tuple[float, str]] = {
    "AAPL":  (190.00, "tech"),
    "GOOGL": (175.00, "tech"),
    "MSFT":  (420.00, "tech"),
    "AMZN":  (185.00, "tech"),
    "TSLA":  (250.00, "tech"),
    "NVDA":  (130.00, "tech"),
    "META":  (560.00, "tech"),
    "JPM":   (210.00, "financials"),
    "V":     (275.00, "financials"),
    "NFLX":  (680.00, "media"),
}

DEFAULT_SEED_PRICE = 100.0  # for a ticker added later with no seed entry


def seed_for(ticker: str) -> tuple[float, str]:
    """Seed price and sector for a ticker, falling back for unknown symbols."""
    return SEED_PRICES.get(ticker, (DEFAULT_SEED_PRICE, "unknown"))
