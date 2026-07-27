from app.market.models import PriceUpdate


class PriceCache:
    def __init__(self) -> None:
        self._latest: dict[str, PriceUpdate] = {}

    def update(self, price_update: PriceUpdate) -> None:
        self._latest[price_update.ticker] = price_update

    def get(self, ticker: str) -> PriceUpdate | None:
        return self._latest.get(ticker)

    def snapshot(self) -> list[PriceUpdate]:
        return list(self._latest.values())
