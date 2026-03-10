import os

from packages.common.llm_assist import assist_decision


def test_assist_decision_disabled() -> None:
    os.environ['ENABLE_LLM_ASSIST'] = 'false'
    result = assist_decision({'fund_name': 'x'})
    assert result is None


def test_assist_decision_enabled_but_no_key() -> None:
    os.environ['ENABLE_LLM_ASSIST'] = 'true'
    os.environ['DEEPSEEK_API_KEY'] = ''
    result = assist_decision({'fund_name': 'x'})
    assert result is None
