from __future__ import annotations

import json
import os
from typing import Any


def _enabled() -> bool:
    return os.getenv("ENABLE_LLM_ASSIST", "false").lower() in {"1", "true", "yes"}


def _build_prompt(payload: dict[str, Any]) -> str:
    return (
        "你是基金舆情分析助手。请根据输入给出保守的辅助建议，输出严格 JSON，不要输出其他文本。\n"
        "输出字段: action, confidence_delta, explanation, risk_note\n"
        "action 只能是 buy/sell/watch；confidence_delta 在 -0.15 到 0.15 之间。\n"
        f"输入数据: {json.dumps(payload, ensure_ascii=False)}"
    )


def _safe_parse_json(text: str) -> dict[str, Any] | None:
    text = text.strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                return None
    return None


def assist_decision(payload: dict[str, Any]) -> dict[str, Any] | None:
    if not _enabled():
        return None

    api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    if not api_key:
        return None

    try:
        from langchain_openai import ChatOpenAI
    except Exception:
        return None

    model_name = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    max_tokens = int(os.getenv("LLM_MAX_TOKENS", "400"))

    llm = ChatOpenAI(
        model=model_name,
        api_key=api_key,
        base_url=base_url,
        temperature=0.2,
        max_tokens=max_tokens,
    )

    prompt = _build_prompt(payload)
    try:
        result = llm.invoke(prompt)
    except Exception:
        return None

    parsed = _safe_parse_json(getattr(result, "content", ""))
    if not parsed:
        return None

    action = str(parsed.get("action", "watch")).lower()
    if action not in {"buy", "sell", "watch"}:
        action = "watch"

    delta = float(parsed.get("confidence_delta", 0.0))
    delta = max(-0.15, min(0.15, delta))

    return {
        "action": action,
        "confidence_delta": delta,
        "explanation": str(parsed.get("explanation", ""))[:200],
        "risk_note": str(parsed.get("risk_note", ""))[:200],
    }
