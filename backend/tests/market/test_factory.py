import sys
import types
from unittest.mock import MagicMock

from app.market.factory import create_market_data_source
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
    if "massive" not in sys.modules:
        stub = types.ModuleType("massive")
        stub.RESTClient = MagicMock()
        monkeypatch.setitem(sys.modules, "massive", stub)
    else:
        monkeypatch.setattr(sys.modules["massive"], "RESTClient", MagicMock())

    monkeypatch.setenv("MASSIVE_API_KEY", "test-key")

    from app.market.massive import MassiveMarketDataSource

    source = create_market_data_source()

    assert isinstance(source, MassiveMarketDataSource)
