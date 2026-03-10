from __future__ import annotations

import hashlib
import os
import re
from collections import Counter
from datetime import datetime, timezone

from .models import (
    FeatureRecord,
    IngestRunResult,
    IngestStatus,
    RawSourceRecord,
    SentimentSignal,
    SourceHealthStatus,
)
from .repository import StateRepository
from .sources import build_all_adapters


def _score(seed: str, offset: int = 0) -> float:
    digest = hashlib.sha256(f"{seed}:{offset}".encode("utf-8")).hexdigest()
    return int(digest[:8], 16) / 0xFFFFFFFF


def _signed(seed: str, offset: int = 0) -> float:
    return (_score(seed, offset) * 2.0) - 1.0


def _normalize_text(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)
    return text


def _content_hash(text: str) -> str:
    return hashlib.sha256(_normalize_text(text).encode("utf-8")).hexdigest()


def deduplicate_raw_records(records: list[RawSourceRecord]) -> list[RawSourceRecord]:
    seen_id: set[tuple[str, str]] = set()
    seen_content: set[str] = set()
    out: list[RawSourceRecord] = []

    for row in records:
        key = (row.source, row.source_id)
        if key in seen_id:
            continue
        if row.content_hash in seen_content:
            continue
        seen_id.add(key)
        seen_content.add(row.content_hash)
        out.append(row)
    return out


def _to_feature(row: RawSourceRecord, ts: datetime) -> FeatureRecord:
    seed = f"{row.source}:{row.source_id}:{row.publish_time.isoformat()}"
    polarity = round(_signed(seed, 1), 4)
    intensity = round(0.2 + _score(seed, 2) * 0.8, 4)
    heat = round(0.3 + _score(seed, 3) * 0.7, 4)
    spread_speed = round(0.2 + _score(seed, 4) * 0.8, 4)
    relevance = round(0.4 + _score(seed, 5) * 0.6, 4)
    conflict = round(abs(polarity) * (1 - row.credibility_score), 4)
    return FeatureRecord(
        source=row.source,
        source_id=row.source_id,
        ts=ts,
        polarity=polarity,
        intensity=intensity,
        heat=heat,
        spread_speed=spread_speed,
        credibility=round(row.credibility_score, 4),
        relevance=relevance,
        conflict=conflict,
        symbol_candidates=row.symbol_candidates,
    )


def _to_signal(row: RawSourceRecord, feat: FeatureRecord) -> SentimentSignal:
    return SentimentSignal(
        source=row.source,
        source_id=row.source_id,
        ts=feat.ts,
        publish_time=row.publish_time,
        polarity=feat.polarity,
        intensity=feat.intensity,
        credibility=feat.credibility,
        relevance=feat.relevance,
        content=row.content,
        symbol_candidates=row.symbol_candidates,
    )


def run_ingest(repo: StateRepository) -> IngestRunResult:
    started_at = datetime.now(timezone.utc)
    run_id = started_at.strftime("ingest-%Y%m%d-%H%M%S")
    symbols = repo.find_fund_names()
    mode = os.getenv("INGEST_ADAPTER_MODE", "hybrid")

    raw_records: list[RawSourceRecord] = []
    health_rows: list[SourceHealthStatus] = []
    source_errors: dict[str, str] = {}

    for adapter in build_all_adapters(mode=mode):
        health = adapter.health_check()
        health_rows.append(
            SourceHealthStatus(
                source=health.source,
                healthy=health.healthy,
                latency_ms=health.latency_ms,
                message=health.message,
                checked_at=health.checked_at,
            )
        )
        if not health.healthy:
            source_errors[health.source] = health.message
            continue

        for row in adapter.fetch(symbols):
            raw_records.append(
                RawSourceRecord(
                    source=row.source,
                    source_id=row.source_id,
                    publish_time=row.publish_time,
                    content=row.content,
                    symbol_candidates=row.symbol_candidates,
                    credibility_score=row.credibility_score,
                    url=row.url,
                    parser_version=row.parser_version,
                    crawl_time=row.crawl_time,
                    content_hash=_content_hash(row.content),
                )
            )

    unique_raw = deduplicate_raw_records(raw_records)
    ts = datetime.now(timezone.utc)
    features = [_to_feature(r, ts) for r in unique_raw]
    signals = [_to_signal(r, f) for r, f in zip(unique_raw, features)]

    by_source = dict(Counter([r.source for r in unique_raw]))

    repo.append_raw_records(unique_raw)
    repo.append_feature_records(features)
    repo.append_signals(signals)
    repo.upsert_source_health(health_rows)

    finished_at = datetime.now(timezone.utc)
    total_signals = len(repo.list_signals())
    status = IngestStatus(
        run_id=run_id,
        started_at=started_at,
        finished_at=finished_at,
        status="success",
        created_count=len(signals),
        raw_count=len(unique_raw),
        feature_count=len(features),
        total_signals=total_signals,
        by_source=by_source,
        mode=mode,
        source_errors=source_errors,
    )
    repo.save_ingest_status(status)

    return IngestRunResult(
        run_id=run_id,
        created_count=len(signals),
        total_signals=total_signals,
        raw_count=len(unique_raw),
        feature_count=len(features),
        by_source=by_source,
        mode=mode,
        source_errors=source_errors,
    )
