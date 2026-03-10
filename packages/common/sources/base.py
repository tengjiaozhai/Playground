from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class SourceHealth:
    source: str
    healthy: bool
    latency_ms: int
    message: str
    checked_at: datetime


@dataclass
class SourceRecord:
    source: str
    source_id: str
    publish_time: datetime
    content: str
    symbol_candidates: list[str]
    credibility_score: float
    url: str
    parser_version: str = "v2.0"
    crawl_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class SourceAdapter(ABC):
    source_name: str

    @abstractmethod
    def health_check(self) -> SourceHealth:
        raise NotImplementedError

    @abstractmethod
    def fetch(self, symbols: list[str]) -> list[SourceRecord]:
        raise NotImplementedError
