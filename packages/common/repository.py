from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any

from .bootstrap import default_funds, default_portfolio
from .models import (
    BacktestRunResult,
    DailyReport,
    DecisionOutput,
    FeatureRecord,
    IngestStatus,
    PortfolioPosition,
    RawSourceRecord,
    SentimentSignal,
    SourceHealthStatus,
)


class StateRepository:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path or os.getenv("FUND_STATE_FILE", "data/state.json"))
        self._lock = Lock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._initialize_state()
        self._ensure_state_schema()

    def _initialize_state(self) -> None:
        state = {
            "fund_master": [f.model_dump(mode="json") for f in default_funds()],
            "portfolio": [p.model_dump(mode="json") for p in default_portfolio()],
            "signals": [],
            "raw_records": [],
            "feature_records": [],
            "recommendations": [],
            "reports": [],
            "ingest_runs": [],
            "source_health": [],
            "backtest_runs": [],
        }
        self._write(state)

    def _ensure_state_schema(self) -> None:
        with self._lock:
            state = self._read()
            changed = False
            defaults: dict[str, Any] = {
                "fund_master": [f.model_dump(mode="json") for f in default_funds()],
                "portfolio": [p.model_dump(mode="json") for p in default_portfolio()],
                "signals": [],
                "raw_records": [],
                "feature_records": [],
                "recommendations": [],
                "reports": [],
                "ingest_runs": [],
                "source_health": [],
                "backtest_runs": [],
            }
            for key, value in defaults.items():
                if key not in state:
                    state[key] = value
                    changed = True
            if changed:
                self._write(state)

    def _read(self) -> dict[str, Any]:
        with self.path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def _write(self, state: dict[str, Any]) -> None:
        with self.path.open("w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return self._read()

    def list_signals(self) -> list[SentimentSignal]:
        with self._lock:
            state = self._read()
            return [SentimentSignal.model_validate(s) for s in state["signals"]]

    def append_signals(self, signals: list[SentimentSignal]) -> None:
        with self._lock:
            state = self._read()
            state["signals"].extend([s.model_dump(mode="json") for s in signals])
            self._write(state)

    def append_raw_records(self, records: list[RawSourceRecord]) -> None:
        with self._lock:
            state = self._read()
            state["raw_records"].extend([r.model_dump(mode="json") for r in records])
            self._write(state)

    def append_feature_records(self, records: list[FeatureRecord]) -> None:
        with self._lock:
            state = self._read()
            state["feature_records"].extend([r.model_dump(mode="json") for r in records])
            self._write(state)

    def list_raw_records(self) -> list[RawSourceRecord]:
        with self._lock:
            state = self._read()
            return [RawSourceRecord.model_validate(r) for r in state.get("raw_records", [])]

    def list_feature_records(self) -> list[FeatureRecord]:
        with self._lock:
            state = self._read()
            return [FeatureRecord.model_validate(r) for r in state.get("feature_records", [])]

    def upsert_recommendations(self, recommendations: list[DecisionOutput]) -> None:
        with self._lock:
            state = self._read()
            state["recommendations"] = [r.model_dump(mode="json") for r in recommendations]
            self._write(state)

    def list_recommendations(self) -> list[DecisionOutput]:
        with self._lock:
            state = self._read()
            return [DecisionOutput.model_validate(r) for r in state["recommendations"]]

    def list_portfolio(self) -> list[PortfolioPosition]:
        with self._lock:
            state = self._read()
            return [PortfolioPosition.model_validate(p) for p in state["portfolio"]]

    def find_fund_names(self) -> list[str]:
        with self._lock:
            state = self._read()
            names: list[str] = []
            for f in state["fund_master"]:
                names.append(f["fund_name"])
                names.extend(f.get("aliases", []))
                if f.get("fund_code"):
                    names.append(f["fund_code"])
            return list(dict.fromkeys(names))

    def find_portfolio_by_code_or_name(self, code_or_name: str) -> list[PortfolioPosition]:
        with self._lock:
            state = self._read()
            result: list[PortfolioPosition] = []
            for row in state["portfolio"]:
                if code_or_name in {row.get("fund_code", ""), row.get("fund_name", "")}:
                    result.append(PortfolioPosition.model_validate(row))
            return result

    def save_report(self, report: DailyReport) -> None:
        with self._lock:
            state = self._read()
            rows = [r for r in state["reports"] if r.get("date") != report.date]
            rows.append(report.model_dump(mode="json"))
            state["reports"] = rows
            self._write(state)

    def save_ingest_status(self, status: IngestStatus) -> None:
        with self._lock:
            state = self._read()
            runs = state.get("ingest_runs", [])
            runs.append(status.model_dump(mode="json"))
            state["ingest_runs"] = runs[-20:]
            self._write(state)

    def latest_ingest_status(self) -> IngestStatus | None:
        with self._lock:
            state = self._read()
            runs = state.get("ingest_runs", [])
            if not runs:
                return None
            return IngestStatus.model_validate(runs[-1])

    def upsert_source_health(self, statuses: list[SourceHealthStatus]) -> None:
        with self._lock:
            state = self._read()
            state["source_health"] = [s.model_dump(mode="json") for s in statuses]
            self._write(state)

    def list_source_health(self) -> list[SourceHealthStatus]:
        with self._lock:
            state = self._read()
            return [SourceHealthStatus.model_validate(s) for s in state.get("source_health", [])]

    def save_backtest_run(self, run: BacktestRunResult) -> None:
        with self._lock:
            state = self._read()
            rows = state.get("backtest_runs", [])
            rows.append(run.model_dump(mode="json"))
            state["backtest_runs"] = rows[-20:]
            self._write(state)

    def latest_backtest_run(self) -> BacktestRunResult | None:
        with self._lock:
            state = self._read()
            rows = state.get("backtest_runs", [])
            if not rows:
                return None
            return BacktestRunResult.model_validate(rows[-1])

    def get_report(self, date: str) -> DailyReport | None:
        with self._lock:
            state = self._read()
            for row in state["reports"]:
                if row.get("date") == date:
                    return DailyReport.model_validate(row)
            return None

    def bind_fund_code(self, fund_name: str, fund_code: str) -> None:
        with self._lock:
            state = self._read()
            for row in state["fund_master"]:
                if row.get("fund_name") == fund_name:
                    row["fund_code"] = fund_code
                    row["pending_code_binding"] = False
            for row in state["portfolio"]:
                if row.get("fund_name") == fund_name:
                    row["fund_code"] = fund_code
                    row["pending_code_binding"] = False
                    row["updated_at"] = datetime.utcnow().isoformat()
            self._write(state)

    def upsert_fund(
        self,
        fund_name: str,
        fund_code: str = "",
        aliases: list[str] | None = None,
        amount: float | None = None,
        cost: float | None = None,
        old_fund_name: str | None = None,
    ) -> None:
        aliases = aliases or []
        with self._lock:
            state = self._read()
            now = datetime.utcnow().isoformat()
            target_name = old_fund_name or fund_name

            fund_found = False
            for row in state["fund_master"]:
                if row.get("fund_name") == target_name:
                    row["fund_name"] = fund_name
                    row["fund_code"] = fund_code
                    row["aliases"] = aliases
                    row["pending_code_binding"] = not bool(fund_code)
                    fund_found = True
                    break
            if not fund_found:
                state["fund_master"].append(
                    {
                        "fund_name": fund_name,
                        "fund_code": fund_code,
                        "aliases": aliases,
                        "pending_code_binding": not bool(fund_code),
                    }
                )

            pos_found = False
            for row in state["portfolio"]:
                if row.get("fund_name") == target_name:
                    row["fund_name"] = fund_name
                    row["fund_code"] = fund_code
                    if amount is not None:
                        row["amount"] = amount
                    if cost is not None:
                        row["cost"] = cost
                    row["pending_code_binding"] = not bool(fund_code)
                    row["updated_at"] = now
                    pos_found = True
                    break
            if not pos_found:
                state["portfolio"].append(
                    {
                        "fund_name": fund_name,
                        "fund_code": fund_code,
                        "amount": amount if amount is not None else 0.0,
                        "cost": cost if cost is not None else 0.0,
                        "updated_at": now,
                        "pending_code_binding": not bool(fund_code),
                    }
                )
            self._write(state)

    def update_position(self, fund_name: str, amount: float | None = None, cost: float | None = None) -> None:
        with self._lock:
            state = self._read()
            now = datetime.utcnow().isoformat()
            for row in state["portfolio"]:
                if row.get("fund_name") == fund_name:
                    if amount is not None:
                        row["amount"] = amount
                    if cost is not None:
                        row["cost"] = cost
                    row["updated_at"] = now
                    self._write(state)
                    return
            raise KeyError(f"fund not found: {fund_name}")

    def delete_fund(self, fund_name: str) -> None:
        with self._lock:
            state = self._read()
            state["fund_master"] = [r for r in state["fund_master"] if r.get("fund_name") != fund_name]
            state["portfolio"] = [r for r in state["portfolio"] if r.get("fund_name") != fund_name]
            state["recommendations"] = [r for r in state.get("recommendations", []) if r.get("fund_name") != fund_name]
            self._write(state)
