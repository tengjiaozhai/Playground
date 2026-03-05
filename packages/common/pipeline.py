from __future__ import annotations

from datetime import date

from .decision import run_decision
from .ingest import run_ingest
from .reporting import generate_daily_report
from .repository import StateRepository


def run_full_pipeline(repo: StateRepository) -> dict[str, str | int]:
    ingest_result = run_ingest(repo)
    decision_result = run_decision(repo)
    report = generate_daily_report(repo, date.today().isoformat())
    return {
        "ingest_run_id": ingest_result.run_id,
        "created_signals": ingest_result.created_count,
        "decision_run_id": decision_result.run_id,
        "recommendations": decision_result.recommendation_count,
        "report_date": report.date,
    }
