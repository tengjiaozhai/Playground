import os

from fastapi.testclient import TestClient

from apps.api.main import app

os.environ["INGEST_ADAPTER_MODE"] = "mock"
os.environ["MARKET_DATA_MODE"] = "proxy"


def test_pipeline_end_to_end() -> None:
    client = TestClient(app)

    r = client.post('/pipeline/run')
    assert r.status_code == 200
    body = r.json()
    assert body['created_signals'] > 0

    r = client.get('/portfolio/recommendations')
    assert r.status_code == 200
    recs = r.json()
    assert len(recs) >= 2
    required = {'fund_name', 'action', 'confidence', 'evidence_sources', 'conflict_summary'}
    assert required.issubset(set(recs[0].keys()))


def test_ingest_status_and_source_health() -> None:
    client = TestClient(app)

    start = client.get('/ingest/status')
    assert start.status_code == 200

    run = client.post('/ingest/run')
    assert run.status_code == 200
    run_body = run.json()
    assert run_body['raw_count'] > 0
    assert run_body['feature_count'] > 0
    assert len(run_body['by_source']) >= 6
    assert run_body['mode'] in {'mock', 'live', 'hybrid'}

    status = client.get('/ingest/status')
    assert status.status_code == 200
    status_body = status.json()
    assert status_body['status'] == 'success'
    assert status_body['feature_count'] >= status_body['created_count']
    assert status_body['mode'] in {'mock', 'live', 'hybrid'}

    health = client.get('/sources/health')
    assert health.status_code == 200
    health_rows = health.json()
    assert len(health_rows) >= 6
    assert all('source' in row and 'healthy' in row for row in health_rows)


def test_backtest_endpoints() -> None:
    client = TestClient(app)
    client.post('/pipeline/run')

    run = client.post('/backtest/run', params={'window_days': 365})
    assert run.status_code == 200
    body = run.json()
    assert body['window_days'] == 365
    assert isinstance(body['metrics'], list)

    metrics = client.get('/backtest/metrics')
    assert metrics.status_code == 200
    metrics_body = metrics.json()
    assert 'metrics' in metrics_body


def test_signal_daily_and_market_history() -> None:
    client = TestClient(app)
    client.post('/pipeline/run')

    daily = client.get('/funds/华宝石油天然气/signal-daily', params={'days': 30})
    assert daily.status_code == 200
    assert isinstance(daily.json(), list)

    market = client.get('/funds/华宝石油天然气/market-history', params={'days': 60})
    assert market.status_code == 200
    body = market.json()
    assert 'source' in body
    assert 'points' in body
