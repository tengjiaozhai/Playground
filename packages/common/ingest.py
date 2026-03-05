from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from .models import IngestRunResult, SentimentSignal
from .repository import StateRepository

SOURCES = [
    "news",
    "blog",
    "tiantianfund",
    "tonghuashun-aifund",
    "eastmoney",
    "social-media",
]


def deduplicate_signals(signals: list[SentimentSignal]) -> list[SentimentSignal]:
    seen: set[tuple[str, str]] = set()
    output: list[SentimentSignal] = []
    for row in signals:
        key = (row.source, row.source_id)
        if key in seen:
            continue
        seen.add(key)
        output.append(row)
    return output


def _score(seed: str, offset: int = 0) -> float:
    digest = hashlib.sha256(f"{seed}:{offset}".encode("utf-8")).hexdigest()
    return int(digest[:8], 16) / 0xFFFFFFFF


def _signed(seed: str, offset: int = 0) -> float:
    return (_score(seed, offset) * 2.0) - 1.0


def run_ingest(repo: StateRepository) -> IngestRunResult:
    now = datetime.now(timezone.utc)
    run_id = now.strftime("ingest-%Y%m%d-%H%M%S")
    fund_terms = repo.find_fund_names()

    created: list[SentimentSignal] = []
    for source in SOURCES:
        for term in fund_terms:
            seed = f"{source}:{term}:{now.date().isoformat()}"
            created.append(
                SentimentSignal(
                    source=source,
                    source_id=f"{source}-{hashlib.md5(seed.encode('utf-8')).hexdigest()[:12]}",
                    ts=now,
                    publish_time=now,
                    polarity=round(_signed(seed, 1), 4),
                    intensity=round(_score(seed, 2), 4),
                    credibility=round(0.5 + (_score(seed, 3) * 0.5), 4),
                    relevance=round(0.4 + (_score(seed, 4) * 0.6), 4),
                    content=f"{source} signal mentions {term}",
                    symbol_candidates=[term],
                )
            )

    unique_created = deduplicate_signals(created)
    repo.append_signals(unique_created)
    total = len(repo.list_signals())
    return IngestRunResult(run_id=run_id, created_count=len(unique_created), total_signals=total)
