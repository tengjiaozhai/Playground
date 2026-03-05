from packages.common.decision import run_decision
from packages.common.repository import StateRepository


def test_pending_code_binding_blocks_trade(tmp_path) -> None:
    repo = StateRepository(path=tmp_path / "state.json")
    result = run_decision(repo)

    assert result.blocked_count >= 1
    recs = repo.list_recommendations()
    assert recs
    assert all(r.action == "watch" for r in recs)
