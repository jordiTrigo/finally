import os

from app.market.source import MarketDataSource


def create_market_data_source() -> MarketDataSource:
    if os.environ.get("MASSIVE_API_KEY"):
        from app.market.massive import MassiveMarketDataSource
        return MassiveMarketDataSource()
    from app.market.simulator import SimulatorMarketDataSource
    return SimulatorMarketDataSource()
