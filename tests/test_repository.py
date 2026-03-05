from packages.common.repository import StateRepository


def test_bind_fund_code_updates_portfolio_and_master(tmp_path) -> None:
    repo = StateRepository(path=tmp_path / "state.json")
    repo.bind_fund_code("华宝石油天然气", "162411")
    rows = repo.find_portfolio_by_code_or_name("162411")
    assert len(rows) == 1
    assert rows[0].pending_code_binding is False
