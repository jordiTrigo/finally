from unittest.mock import MagicMock

import app.market.massive as massive_module
from app.market.factory import create_market_data_source
from app.market.massive import MassiveMarketDataSource
from app.market.simulator import SimulatorMarketDataSource


def test_returns_simulator_when_massive_api_key_unset(monkeypatch):
    monkeypatch.delenv("MASSIVE_API_KEY", raising=False)

    source = create_market_data_source()

    assert isinstance(source, SimulatorMarketDataSource)


def test_returns_simulator_when_massive_api_key_is_empty_string(monkeypatch):
    monkeypatch.setenv("MASSIVE_API_KEY", "")

    source = create_market_data_source()

    assert isinstance(source, SimulatorMarketDataSource)


def test_returns_massive_source_when_api_key_set(monkeypatch):
    # Stub only the client construction; the real `massive` package still imports.
    monkeypatch.setattr(massive_module, "RESTClient", MagicMock())
    monkeypatch.setenv("MASSIVE_API_KEY", "test-key")

    source = create_market_data_source()

    assert isinstance(source, MassiveMarketDataSource)
