from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

from .base import SourceAdapter, SourceHealth, SourceRecord


class _MockAdapter(SourceAdapter):
    def __init__(self, source_name: str, domain: str, base_credibility: float) -> None:
        self.source_name = source_name
        self.domain = domain
        self.base_credibility = base_credibility

    def health_check(self) -> SourceHealth:
        return SourceHealth(
            source=self.source_name,
            healthy=True,
            latency_ms=80,
            message="mock-adapter-ok",
            checked_at=datetime.now(timezone.utc),
        )

    def fetch(self, symbols: list[str]) -> list[SourceRecord]:
        now = datetime.now(timezone.utc)
        records: list[SourceRecord] = []
        for idx, symbol in enumerate(symbols):
            seed = f"{self.source_name}:{symbol}:{now.date().isoformat()}"
            sid = hashlib.md5(seed.encode("utf-8")).hexdigest()[:16]
            records.append(
                SourceRecord(
                    source=self.source_name,
                    source_id=f"{self.source_name}-{sid}",
                    publish_time=now - timedelta(minutes=idx * 7),
                    content=f"{self.source_name} 对 {symbol} 的市场舆情摘要与观点。",
                    symbol_candidates=[symbol],
                    credibility_score=min(0.99, self.base_credibility + (idx % 3) * 0.03),
                    url=f"https://{self.domain}/mock/{sid}",
                    crawl_time=now,
                )
            )
        return records


class NewsAdapter(_MockAdapter):
    def __init__(self) -> None:
        super().__init__("news", "news.example.com", 0.78)


class BlogAdapter(_MockAdapter):
    def __init__(self) -> None:
        super().__init__("blog", "blog.example.com", 0.62)


class TiantianFundAdapter(_MockAdapter):
    def __init__(self) -> None:
        super().__init__("tiantianfund", "fund.eastmoney.com", 0.84)


class TonghuashunAIFundAdapter(_MockAdapter):
    def __init__(self) -> None:
        super().__init__("tonghuashun-aifund", "ai.iwencai.com", 0.82)


class EastmoneyAdapter(_MockAdapter):
    def __init__(self) -> None:
        super().__init__("eastmoney", "eastmoney.com", 0.86)


class SocialMediaAdapter(_MockAdapter):
    def __init__(self) -> None:
        super().__init__("social-media", "social.example.com", 0.55)


def build_mock_adapters() -> list[SourceAdapter]:
    return [
        NewsAdapter(),
        BlogAdapter(),
        TiantianFundAdapter(),
        TonghuashunAIFundAdapter(),
        EastmoneyAdapter(),
        SocialMediaAdapter(),
    ]
