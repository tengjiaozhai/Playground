from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta

import requests


@dataclass
class MarketPoint:
    date: str
    nav: float


@dataclass
class MarketSeries:
    fund_code: str
    source: str
    points: list[MarketPoint]


def _parse_json_maybe_jsonp(text: str) -> dict:
    text = text.strip()
    if text.startswith("{"):
        return json.loads(text)
    match = re.search(r"\((\{.*\})\)\s*;?$", text, re.DOTALL)
    if match:
        return json.loads(match.group(1))
    raise ValueError("invalid json/jsonp payload")


def _fetch_eastmoney_history(fund_code: str, days: int) -> list[MarketPoint]:
    end = datetime.utcnow().date()
    start = end - timedelta(days=max(30, days * 2))
    url = "https://api.fund.eastmoney.com/f10/lsjz"
    params = {
        "fundCode": fund_code,
        "pageIndex": 1,
        "pageSize": max(120, min(2000, days * 2)),
        "startDate": start.strftime("%Y-%m-%d"),
        "endDate": end.strftime("%Y-%m-%d"),
    }
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        "Referer": "https://fund.eastmoney.com/",
    }
    resp = requests.get(url, params=params, headers=headers, timeout=12)
    resp.raise_for_status()
    payload = _parse_json_maybe_jsonp(resp.text)
    rows = payload.get("Data", {}).get("LSJZList", [])
    points: list[MarketPoint] = []
    for r in rows:
        d = str(r.get("FSRQ", ""))[:10]
        nav_raw = r.get("DWJZ")
        if not d or nav_raw in (None, ""):
            continue
        try:
            nav = float(nav_raw)
        except Exception:
            continue
        points.append(MarketPoint(date=d, nav=nav))
    points.sort(key=lambda x: x.date)
    if len(points) > days:
        points = points[-days:]
    return points


def build_proxy_series(days: int = 365, seed_nav: float = 1.0) -> list[MarketPoint]:
    now = datetime.utcnow().date()
    points: list[MarketPoint] = []
    nav = seed_nav
    for i in range(days):
        d = now - timedelta(days=days - i)
        drift = ((i % 11) - 5) * 0.0009
        nav = max(0.2, nav * (1.0 + drift))
        points.append(MarketPoint(date=d.strftime("%Y-%m-%d"), nav=round(nav, 4)))
    return points


def fetch_market_series(fund_code: str, days: int = 365) -> MarketSeries:
    code = (fund_code or "").strip()
    mode = os.getenv("MARKET_DATA_MODE", "auto").lower()
    if mode == "proxy":
        return MarketSeries(fund_code=code, source="proxy", points=build_proxy_series(days=days))
    if not code:
        return MarketSeries(fund_code="", source="proxy", points=build_proxy_series(days=days))
    try:
        points = _fetch_eastmoney_history(code, days)
        if len(points) >= 20:
            return MarketSeries(fund_code=code, source="eastmoney_live", points=points)
    except Exception:
        if mode == "live":
            return MarketSeries(fund_code=code, source="live_failed", points=[])
    return MarketSeries(fund_code=code, source="proxy", points=build_proxy_series(days=days))
