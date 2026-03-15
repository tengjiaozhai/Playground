from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any


@lru_cache(maxsize=1)
def _read_local_env() -> dict[str, str]:
    repo_root = Path(__file__).resolve().parents[2]
    candidates = [Path.cwd() / ".env", repo_root / ".env"]
    for path in candidates:
        if not path.exists():
            continue
        data: dict[str, str] = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[7:].strip()
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            data[key.strip()] = value.strip().strip("'\"")
        return data
    return {}


def _env(name: str, default: str = "") -> str:
    value = os.getenv(name, "").strip()
    if value:
        return value
    return _read_local_env().get(name, default)


def _enabled() -> bool:
    return _env("ENABLE_LLM_ASSIST", "false").lower() in {"1", "true", "yes"}


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


def get_llm_status() -> dict[str, Any]:
    enabled = _enabled()
    api_key = _env("DEEPSEEK_API_KEY", "")
    model_name = _env("DEEPSEEK_MODEL", "deepseek-chat")
    base_url = _env("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

    try:
        from langchain_openai import ChatOpenAI  # noqa: F401

        langchain_ready = True
    except Exception:
        langchain_ready = False

    ready = enabled and bool(api_key) and langchain_ready
    if not enabled:
        reason = "当前未开启大模型辅助推理"
    elif not api_key:
        reason = "已打开大模型开关，但还没有可用的 DeepSeek API Key"
    elif not langchain_ready:
        reason = "langchain-openai 依赖不可用，暂时无法调用大模型"
    else:
        reason = "DeepSeek 会在决策阶段参与复核"

    return {
        "enabled": enabled,
        "ready": ready,
        "provider": "DeepSeek",
        "model": model_name,
        "base_url": base_url,
        "stage": "decision_review",
        "reason": reason,
    }


def assist_decision(payload: dict[str, Any]) -> dict[str, Any] | None:
    status = get_llm_status()
    if not status["ready"]:
        return None

    try:
        from langchain_openai import ChatOpenAI
    except Exception:
        return None

    api_key = _env("DEEPSEEK_API_KEY", "")
    model_name = status["model"]
    base_url = status["base_url"]
    max_tokens = int(_env("LLM_MAX_TOKENS", "400"))

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
        "provider": status["provider"],
        "model": model_name,
        "stage": status["stage"],
    }
