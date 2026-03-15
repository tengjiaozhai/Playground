import os
from datetime import datetime, timezone

import pytest

from packages.common import backtest
from packages.common.backtest import BacktestLiveDataError, run_backtest
from packages.common.market_data import MarketPoint, MarketSeries
from packages.common.models import SentimentSignal
from packages.common.repository import StateRepository


def test_backtest_live_mode_requires_live_labels(monkeypatch, tmp_path) -> None:
    os.environ['MARKET_DATA_MODE'] = 'live'
    repo = StateRepository(path=tmp_path / 'state.json')

    now = datetime.now(timezone.utc)
    rows = [
        SentimentSignal(
            source='news',
            source_id=f's{i}',
            ts=now,
            publish_time=now,
            polarity=0.1,
            intensity=0.8,
            credibility=0.9,
            relevance=0.8,
            content='x',
            symbol_candidates=['华宝石油天然气'],
        )
        for i in range(3)
    ]
    repo.append_signals(rows)

    def fake_fetch(_code: str, days: int = 365):
        return MarketSeries(fund_code='007844', source='live_failed', points=[MarketPoint(date='2026-03-01', nav=1.0)])

    monkeypatch.setattr(backtest, 'fetch_market_series', fake_fetch)

    with pytest.raises(BacktestLiveDataError) as exc:
        run_backtest(repo, window_days=365)

    assert exc.value.errors
    assert exc.value.errors[0]['reason'].startswith('label_source=')
