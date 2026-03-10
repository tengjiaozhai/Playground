from __future__ import annotations

from .base import SourceAdapter, SourceHealth, SourceRecord
from .live_adapters import build_live_adapters
from .mock_adapters import build_mock_adapters


class HybridAdapter(SourceAdapter):
    def __init__(self, live: SourceAdapter, mock: SourceAdapter) -> None:
        self.live = live
        self.mock = mock
        self.source_name = live.source_name

    def health_check(self) -> SourceHealth:
        live_h = self.live.health_check()
        if live_h.healthy:
            return live_h
        mock_h = self.mock.health_check()
        return SourceHealth(
            source=self.source_name,
            healthy=mock_h.healthy,
            latency_ms=live_h.latency_ms,
            message=f"live_failed({live_h.message}), fallback={mock_h.message}",
            checked_at=live_h.checked_at,
        )

    def fetch(self, symbols: list[str]) -> list[SourceRecord]:
        records = self.live.fetch(symbols)
        if records:
            return records
        return self.mock.fetch(symbols)


def build_all_adapters(mode: str = "hybrid") -> list[SourceAdapter]:
    mode = (mode or "hybrid").strip().lower()
    mock = build_mock_adapters()
    if mode == "mock":
        return mock

    live = build_live_adapters()
    if mode == "live":
        return live

    # hybrid: one-to-one fallback by source ordering
    by_source = {a.source_name: a for a in mock}
    out: list[SourceAdapter] = []
    for ladp in live:
        madp = by_source.get(ladp.source_name)
        out.append(HybridAdapter(ladp, madp) if madp else ladp)
    return out


__all__ = [
    "SourceAdapter",
    "SourceHealth",
    "SourceRecord",
    "HybridAdapter",
    "build_all_adapters",
]
