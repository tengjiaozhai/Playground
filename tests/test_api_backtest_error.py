from fastapi.testclient import TestClient

import apps.api.main as api_main
from packages.common.backtest import BacktestLiveDataError


def test_backtest_run_returns_502_with_errors(monkeypatch) -> None:
    client = TestClient(api_main.app)

    def fake_run_backtest(_repo, window_days: int = 365):
        raise BacktestLiveDataError([
            {"fund_name": "华宝石油天然气", "fund_code": "007844", "reason": "label_source=live_failed"}
        ])

    monkeypatch.setattr(api_main, 'run_backtest', fake_run_backtest)

    r = client.post('/backtest/run', params={'window_days': 365})
    assert r.status_code == 502
    detail = r.json().get('detail', {})
    assert 'message' in detail
    assert detail.get('errors')
