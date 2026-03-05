from fastapi.testclient import TestClient

from apps.api.main import app


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
