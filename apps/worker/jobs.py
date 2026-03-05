from __future__ import annotations

from packages.common.pipeline import run_full_pipeline
from packages.common.repository import StateRepository


def run_daily_jobs() -> dict[str, str | int]:
    repo = StateRepository()
    return run_full_pipeline(repo)
