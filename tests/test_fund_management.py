from fastapi.testclient import TestClient

from apps.api.main import app


def test_fund_add_update_delete_flow() -> None:
    client = TestClient(app)

    add = client.post(
        '/funds/upsert',
        json={
            'fund_name': '测试基金A',
            'fund_code': '000001',
            'aliases': ['测试A'],
            'amount': 1200,
            'cost': 3000,
        },
    )
    assert add.status_code == 200

    master = client.get('/funds/master')
    assert master.status_code == 200
    names = [x['fund_name'] for x in master.json()]
    assert '测试基金A' in names

    update = client.patch('/funds/position', json={'fund_name': '测试基金A', 'amount': 1500, 'cost': 3600})
    assert update.status_code == 200

    pos = client.get('/portfolio/positions')
    rows = [x for x in pos.json() if x['fund_name'] == '测试基金A']
    assert rows and rows[0]['amount'] == 1500

    delete = client.delete('/funds', params={'fund_name': '测试基金A'})
    assert delete.status_code == 200

    master2 = client.get('/funds/master')
    names2 = [x['fund_name'] for x in master2.json()]
    assert '测试基金A' not in names2
