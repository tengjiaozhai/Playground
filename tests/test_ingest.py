from datetime import datetime, timezone

from packages.common.ingest import deduplicate_signals
from packages.common.models import SentimentSignal


def test_deduplicate_signals_by_source_and_source_id() -> None:
    now = datetime.now(timezone.utc)
    rows = [
        SentimentSignal(
            source="news",
            source_id="a1",
            ts=now,
            publish_time=now,
            polarity=0.2,
            intensity=0.8,
            credibility=0.9,
            relevance=0.7,
            content="x",
            symbol_candidates=["f1"],
        ),
        SentimentSignal(
            source="news",
            source_id="a1",
            ts=now,
            publish_time=now,
            polarity=0.9,
            intensity=0.8,
            credibility=0.9,
            relevance=0.7,
            content="duplicate",
            symbol_candidates=["f1"],
        ),
    ]

    deduped = deduplicate_signals(rows)
    assert len(deduped) == 1
