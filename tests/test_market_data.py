from packages.common import market_data
from packages.common.market_data import MarketPoint, MarketSeries


def test_fetch_market_series_prefers_fresher_source(monkeypatch) -> None:
    def fake_ping(_fund_code: str, days: int):
        return MarketSeries(
            fund_code="005052",
            source="eastmoney_pingzhongdata",
            points=[
                MarketPoint(date="2026-03-11", nav=1.2814),
            ],
        )

    def fake_lsjz(_fund_code: str, days: int):
        return MarketSeries(
            fund_code="005052",
            source="eastmoney_lsjz",
            points=[
                MarketPoint(date="2026-03-12", nav=1.2811),
            ],
        )

    monkeypatch.setattr(market_data, "_parse_pingzhongdata", fake_ping)
    monkeypatch.setattr(market_data, "_fetch_eastmoney_history", fake_lsjz)

    series = market_data.fetch_market_series("005052", days=10)
    assert series.source == "eastmoney_lsjz"
    assert series.points[-1].date == "2026-03-12"


def test_fetch_market_series_allows_short_windows_without_proxy(monkeypatch) -> None:
    def fake_ping(_fund_code: str, days: int):
        return MarketSeries(
            fund_code="005052",
            source="eastmoney_pingzhongdata",
            points=[
                MarketPoint(date="2026-03-11", nav=1.2814),
                MarketPoint(date="2026-03-12", nav=1.2811),
            ],
        )

    def fake_lsjz(_fund_code: str, days: int):
        return None

    monkeypatch.setattr(market_data, "_parse_pingzhongdata", fake_ping)
    monkeypatch.setattr(market_data, "_fetch_eastmoney_history", fake_lsjz)

    series = market_data.fetch_market_series("005052", days=2)
    assert series.source == "eastmoney_pingzhongdata"
    assert len(series.points) == 2
