from datetime import datetime, timezone

from packages.common.ingest import deduplicate_raw_records
from packages.common.models import RawSourceRecord


def test_deduplicate_raw_records_by_id_and_content() -> None:
    now = datetime.now(timezone.utc)
    rows = [
        RawSourceRecord(
            source="news",
            source_id="a1",
            publish_time=now,
            content="same content",
            symbol_candidates=["f1"],
            credibility_score=0.8,
            url="https://x",
            parser_version="v2",
            crawl_time=now,
            content_hash="h1",
        ),
        RawSourceRecord(
            source="news",
            source_id="a1",
            publish_time=now,
            content="different content",
            symbol_candidates=["f1"],
            credibility_score=0.8,
            url="https://y",
            parser_version="v2",
            crawl_time=now,
            content_hash="h2",
        ),
        RawSourceRecord(
            source="blog",
            source_id="b1",
            publish_time=now,
            content="same content",
            symbol_candidates=["f1"],
            credibility_score=0.7,
            url="https://z",
            parser_version="v2",
            crawl_time=now,
            content_hash="h1",
        ),
    ]

    deduped = deduplicate_raw_records(rows)
    assert len(deduped) == 1
    assert deduped[0].source_id == "a1"
