from packages.common import llm_assist


def test_assist_decision_disabled(monkeypatch) -> None:
    monkeypatch.setenv('ENABLE_LLM_ASSIST', 'false')
    monkeypatch.setattr(llm_assist, '_read_local_env', lambda: {})
    result = llm_assist.assist_decision({'fund_name': 'x'})
    assert result is None


def test_assist_decision_enabled_but_no_key(monkeypatch) -> None:
    monkeypatch.setenv('ENABLE_LLM_ASSIST', 'true')
    monkeypatch.setenv('DEEPSEEK_API_KEY', '')
    monkeypatch.setattr(llm_assist, '_read_local_env', lambda: {})
    result = llm_assist.assist_decision({'fund_name': 'x'})
    assert result is None


def test_get_llm_status_exposes_reason(monkeypatch) -> None:
    monkeypatch.setenv('ENABLE_LLM_ASSIST', 'true')
    monkeypatch.setenv('DEEPSEEK_API_KEY', '')
    monkeypatch.setattr(llm_assist, '_read_local_env', lambda: {})
    status = llm_assist.get_llm_status()
    assert status['enabled'] is True
    assert status['ready'] is False
    assert 'API Key' in status['reason']
