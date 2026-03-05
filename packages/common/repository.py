from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any

from .bootstrap import default_funds, default_portfolio
from .models import DailyReport, DecisionOutput, PortfolioPosition, SentimentSignal


class StateRepository:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path or os.getenv("FUND_STATE_FILE", "data/state.json"))
        self._lock = Lock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._initialize_state()

    def _initialize_state(self) -> None:
        state = {
            "fund_master": [f.model_dump(mode="json") for f in default_funds()],
            "portfolio": [p.model_dump(mode="json") for p in default_portfolio()],
            "signals": [],
            "recommendations": [],
            "reports": [],
        }
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
