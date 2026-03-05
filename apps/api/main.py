from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import FastAPI, HTTPException, Query

from packages.common.decision import run_decision
from packages.common.ingest import run_ingest
from packages.common.pipeline import run_full_pipeline
from packages.common.reporting import generate_daily_report
from packages.common.repository import StateRepository

app = FastAPI(title="Fund Sentiment Trading API", version="0.1.0")
repo = StateRepository()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/ingest/run")
def ingest_run() -> dict[str, Any]:
    result = run_ingest(repo)
    return result.model_dump(mode="json")


@app.get("/funds/{code_or_name}/signals")
def fund_signals(code_or_name: str) -> list[dict[str, Any]]:
    signals = repo.list_signals()
    filtered = [
        s.model_dump(mode="json")
        for s in signals
        if code_or_name in s.symbol_candidates or code_or_name in s.content
    ]
    return filtered


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


@app.post("/pipeline/run")
def pipeline_run() -> dict[str, str | int]:
    return run_full_pipeline(repo)
