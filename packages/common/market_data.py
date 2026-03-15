from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

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
    fund_name: str = ""
    source_url: str = ""
    fetched_at: str = ""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_json_maybe_jsonp(text: str) -> dict:
    text = text.strip()
    if text.startswith("{"):
        return json.loads(text)
    match = re.search(r"\((\{.*\})\)\s*;?$", text, re.DOTALL)
    if match:
        return json.loads(match.group(1))
    raise ValueError("invalid json/jsonp payload")


def _extract_js_var(text: str, var_name: str) -> str:
    # Supports: var fS_name = "...";
    m = re.search(rf"var\s+{re.escape(var_name)}\s*=\s*(.+?);", text, re.DOTALL)
    if not m:
        return ""
    return m.group(1).strip()


def _parse_pingzhongdata(fund_code: str, days: int) -> MarketSeries | None:
    ts = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    url = f"https://fund.eastmoney.com/pingzhongdata/{fund_code}.js?v={ts}"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        "Referer": f"https://fund.eastmoney.com/{fund_code}.html",
    }
    resp = requests.get(url, headers=headers, timeout=12)
    resp.raise_for_status()
    text = resp.text

    raw_name = _extract_js_var(text, "fS_name")
    raw_code = _extract_js_var(text, "fS_code")
    raw_trend = _extract_js_var(text, "Data_netWorthTrend")
    if not raw_trend:
        return None

    fund_name = ""
    if raw_name.startswith('"') and raw_name.endswith('"'):
        fund_name = json.loads(raw_name)
    code = ""
    if raw_code.startswith('"') and raw_code.endswith('"'):
        code = json.loads(raw_code)
    if code and code != fund_code:
        return None

    trend = json.loads(raw_trend)
    points: list[MarketPoint] = []
    for row in trend:
        ts_ms = row.get("x")
        nav = row.get("y")
        if ts_ms in (None, "") or nav in (None, ""):
            continue
        try:
            d = datetime.fromtimestamp(float(ts_ms) / 1000.0, tz=timezone.utc).strftime("%Y-%m-%d")
            n = float(nav)
        except Exception:
            continue
        points.append(MarketPoint(date=d, nav=n))

    points.sort(key=lambda p: p.date)
    if not points:
        return None
    if len(points) > days:
        points = points[-days:]

    return MarketSeries(
        fund_code=fund_code,
        source="eastmoney_pingzhongdata",
        points=points,
        fund_name=fund_name,
        source_url=url,
        fetched_at=_now_iso(),
    )


def _fetch_eastmoney_history(fund_code: str, days: int) -> MarketSeries | None:
    url = "https://api.fund.eastmoney.com/f10/lsjz"
    params = {
        "fundCode": fund_code,
        "pageIndex": 1,
        # Some funds return empty payloads when start/end dates are provided.
        # Request the newest page directly and trim locally for better freshness.
        "pageSize": max(120, min(200, days * 2)),
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

    data = payload.get("Data", {}) if isinstance(payload, dict) else {}
    rows = data.get("LSJZList", []) if isinstance(data, dict) else []
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
    if not points:
        return None
    if len(points) > days:
        points = points[-days:]

    return MarketSeries(
        fund_code=fund_code,
        source="eastmoney_lsjz",
        points=points,
        fund_name="",
        source_url=url,
        fetched_at=_now_iso(),
    )


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
        return MarketSeries(fund_code=code, source="proxy", points=build_proxy_series(days=days), fetched_at=_now_iso())
    if not code:
        return MarketSeries(fund_code="", source="proxy", points=build_proxy_series(days=days), fetched_at=_now_iso())

    # Try both Eastmoney sources and prefer the fresher latest trading day.
    pingzhongdata_series: MarketSeries | None = None
    try:
        pingzhongdata_series = _parse_pingzhongdata(code, days)
    except Exception:
        pass

    lsjz_series: MarketSeries | None = None
    try:
        lsjz_series = _fetch_eastmoney_history(code, days)
    except Exception:
        if mode == "live":
            return MarketSeries(fund_code=code, source="live_failed", points=[], fetched_at=_now_iso())

    if pingzhongdata_series and lsjz_series:
        ping_last = pingzhongdata_series.points[-1].date if pingzhongdata_series.points else ""
        lsjz_last = lsjz_series.points[-1].date if lsjz_series.points else ""
        if lsjz_last > ping_last:
            return lsjz_series
        return pingzhongdata_series

    if pingzhongdata_series:
        return pingzhongdata_series

    if lsjz_series:
        return lsjz_series

    if mode == "live":
        return MarketSeries(fund_code=code, source="live_failed", points=[], fetched_at=_now_iso())

    return MarketSeries(fund_code=code, source="proxy", points=build_proxy_series(days=days), fetched_at=_now_iso())
