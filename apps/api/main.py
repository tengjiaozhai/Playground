from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from packages.common.backtest import BacktestLiveDataError, run_backtest
from packages.common.decision import run_decision
from packages.common.ingest import run_ingest
from packages.common.llm_assist import get_llm_status
from packages.common.market_data import fetch_market_series
from packages.common.pipeline import run_full_pipeline
from packages.common.reporting import generate_daily_report
from packages.common.repository import StateRepository

app = FastAPI(title="Fund Sentiment Trading API", version="0.1.0")
repo = StateRepository()


class FundUpsertRequest(BaseModel):
    fund_name: str
    fund_code: str = ""
    aliases: list[str] = Field(default_factory=list)
    amount: float = 0.0
    cost: float = 0.0
    old_fund_name: str | None = None


class PositionUpdateRequest(BaseModel):
    fund_name: str
    amount: float | None = None
    cost: float | None = None


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/ingest/run")
def ingest_run() -> dict[str, Any]:
    result = run_ingest(repo)
    return result.model_dump(mode="json")


@app.get("/ingest/status")
def ingest_status() -> dict[str, Any]:
    status = repo.latest_ingest_status()
    if status is None:
        return {"status": "not_started"}
    return status.model_dump(mode="json")


@app.get("/sources/health")
def sources_health() -> list[dict[str, Any]]:
    return [s.model_dump(mode="json") for s in repo.list_source_health()]


@app.get("/system/llm-status")
def system_llm_status() -> dict[str, Any]:
    return get_llm_status()


@app.get("/funds/{code_or_name}/signals")
def fund_signals(code_or_name: str) -> list[dict[str, Any]]:
    signals = repo.list_signals()
    filtered = [
        s.model_dump(mode="json")
        for s in signals
        if code_or_name in s.symbol_candidates or code_or_name in s.content
    ]
    return filtered


@app.get("/funds/{code_or_name}/signal-daily")
def fund_signal_daily(code_or_name: str, days: int = 90) -> list[dict[str, Any]]:
    signals = repo.list_signals()
    bucket: dict[str, dict[str, float]] = {}
    for s in signals:
        if not (code_or_name in s.symbol_candidates or code_or_name in s.content):
            continue
        day = s.publish_time.date().strftime("%Y-%m-%d")
        row = bucket.setdefault(day, {"count": 0, "score": 0.0})
        row["count"] += 1
        row["score"] += s.polarity * s.intensity * s.credibility * s.relevance
    rows = []
    for d in sorted(bucket.keys())[-days:]:
        count = bucket[d]["count"]
        rows.append({"date": d, "count": count, "avg_score": round(bucket[d]["score"] / max(1, count), 6)})
    return rows


@app.get("/funds/{code_or_name}/market-history")
def fund_market_history(code_or_name: str, days: int = 365) -> dict[str, Any]:
    code = code_or_name
    snapshot = repo.snapshot()
    for row in snapshot.get("fund_master", []):
        if code_or_name in {row.get("fund_name", ""), row.get("fund_code", "")}:
            code = row.get("fund_code") or code_or_name
            break
    series = fetch_market_series(code, days=days)
    return {
        "fund_code": series.fund_code,
        "fund_name": series.fund_name,
        "source": series.source,
        "source_url": series.source_url,
        "fetched_at": series.fetched_at,
        "points": [{"date": p.date, "nav": p.nav} for p in series.points],
    }


@app.post("/decision/run")
def decision_run() -> dict[str, Any]:
    result = run_decision(repo)
    return result.model_dump(mode="json")


@app.get("/portfolio/recommendations")
def portfolio_recommendations() -> list[dict[str, Any]]:
    return [r.model_dump(mode="json") for r in repo.list_recommendations()]


@app.get("/portfolio/positions")
def portfolio_positions() -> list[dict[str, Any]]:
    return [p.model_dump(mode="json") for p in repo.list_portfolio()]


@app.get("/funds/master")
def funds_master() -> list[dict[str, Any]]:
    return repo.snapshot().get("fund_master", [])


@app.get("/reports/daily")
def daily_report(date_value: str = Query(default_factory=lambda: date.today().isoformat(), alias="date")) -> dict[str, Any]:
    report = repo.get_report(date_value)
    if report is None:
        report = generate_daily_report(repo, date_value)
    return report.model_dump(mode="json")


@app.post("/portfolio/bind-code")
def bind_fund_code(fund_name: str, fund_code: str) -> dict[str, str]:
    if not fund_name or not fund_code:
        raise HTTPException(status_code=400, detail="fund_name and fund_code are required")
    repo.bind_fund_code(fund_name=fund_name, fund_code=fund_code)
    return {"status": "ok"}


@app.post("/funds/upsert")
def upsert_fund(payload: FundUpsertRequest) -> dict[str, str]:
    if not payload.fund_name.strip():
        raise HTTPException(status_code=400, detail="fund_name is required")
    repo.upsert_fund(
        fund_name=payload.fund_name.strip(),
        fund_code=payload.fund_code.strip(),
        aliases=[a.strip() for a in payload.aliases if a.strip()],
        amount=payload.amount,
        cost=payload.cost,
        old_fund_name=payload.old_fund_name.strip() if payload.old_fund_name else None,
    )
    return {"status": "ok"}


@app.patch("/funds/position")
def update_fund_position(payload: PositionUpdateRequest) -> dict[str, str]:
    try:
        repo.update_position(fund_name=payload.fund_name, amount=payload.amount, cost=payload.cost)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"status": "ok"}


@app.delete("/funds")
def delete_fund(fund_name: str) -> dict[str, str]:
    if not fund_name.strip():
        raise HTTPException(status_code=400, detail="fund_name is required")
    repo.delete_fund(fund_name=fund_name.strip())
    return {"status": "ok"}


@app.post("/pipeline/run")
def pipeline_run() -> dict[str, str | int]:
    return run_full_pipeline(repo)


@app.post("/backtest/run")
def backtest_run(window_days: int = 365) -> dict[str, Any]:
    try:
        result = run_backtest(repo, window_days=window_days)
    except BacktestLiveDataError as exc:
        raise HTTPException(
            status_code=502,
            detail={
                "message": "MARKET_DATA_MODE=live 时要求真实净值标签，当前部分基金抓取失败",
                "errors": exc.errors,
            },
        ) from exc
    return result.model_dump(mode="json")


@app.get("/backtest/metrics")
def backtest_metrics() -> dict[str, Any]:
    latest = repo.latest_backtest_run()
    if latest is None:
        return {"status": "not_started", "metrics": []}
    return latest.model_dump(mode="json")
