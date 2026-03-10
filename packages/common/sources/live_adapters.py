from __future__ import annotations

import hashlib
import re
import time
from datetime import datetime, timedelta, timezone

from .base import SourceAdapter, SourceHealth, SourceRecord
from .http_client import FetchResult, fetch_with_retry


def _extract_title(html: str) -> str:
    match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    if not match:
        return ""
    title = re.sub(r"\s+", " ", match.group(1)).strip()
    return title[:120]


def _extract_meta_description(html: str) -> str:
    match = re.search(
        r'<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']',
        html,
        re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return ""
    return re.sub(r"\s+", " ", match.group(1)).strip()[:200]


def _extract_plain_text(html: str) -> str:
    text = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.IGNORECASE)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:1200]


def _keyword_context(text: str, keyword: str, width: int = 70) -> str:
    idx = text.find(keyword)
    if idx < 0:
        return text[:width * 2]
    left = max(0, idx - width)
    right = min(len(text), idx + len(keyword) + width)
    return text[left:right]


class _LiveHttpAdapter(SourceAdapter):
    def __init__(
        self,
        source_name: str,
        url: str,
        credibility: float,
        parser_tag: str,
        min_interval_sec: float = 0.6,
        failure_threshold: int = 2,
        cooldown_sec: int = 45,
    ) -> None:
        self.source_name = source_name
        self.url = url
        self.credibility = credibility
        self.parser_tag = parser_tag
        self.min_interval_sec = min_interval_sec
        self.failure_threshold = failure_threshold
        self.cooldown_sec = cooldown_sec

        self._last_request_at = 0.0
        self._failure_count = 0
        self._circuit_open_until = 0.0
        self._last_error = ""

    def _throttle(self) -> None:
        now = time.monotonic()
        wait = self.min_interval_sec - (now - self._last_request_at)
        if wait > 0:
            time.sleep(wait)

    def _request(self, timeout: int, retries: int) -> FetchResult:
        now = time.monotonic()
        if now < self._circuit_open_until:
            remaining = int(self._circuit_open_until - now)
            return FetchResult(
                ok=False,
                text="",
                latency_ms=0,
                error_type="circuit_open",
                message=f"circuit_open_{remaining}s",
            )

        self._throttle()
        result = fetch_with_retry(self.url, timeout=timeout, retries=retries)
        self._last_request_at = time.monotonic()

        if result.ok:
            self._failure_count = 0
            self._last_error = ""
            return result

        self._failure_count += 1
        self._last_error = f"{result.error_type}:{result.message}"
        if self._failure_count >= self.failure_threshold:
            self._circuit_open_until = time.monotonic() + self.cooldown_sec
        return result

    def _build_content(self, html: str, symbol: str) -> str:
        title = _extract_title(html)
        desc = _extract_meta_description(html)
        text = _extract_plain_text(html)
        context = _keyword_context(text, symbol)
        if self.source_name == "tiantianfund":
            return f"天天基金|{title}|{symbol}|{context[:180]}"
        if self.source_name == "tonghuashun-aifund":
            return f"同花顺爱基金|{title}|{symbol}|{context[:180]}"
        if self.source_name == "eastmoney":
            return f"东方财富|{title}|{symbol}|{context[:180]}"
        if self.source_name == "social-media":
            return f"社交媒体|{title}|{symbol}|{context[:180]}"
        if self.source_name == "blog":
            return f"博客社区|{title}|{symbol}|{desc or context[:180]}"
        return f"财经新闻|{title}|{symbol}|{desc or context[:180]}"

    def health_check(self) -> SourceHealth:
        result = self._request(timeout=8, retries=1)
        if result.ok:
            return SourceHealth(
                source=self.source_name,
                healthy=True,
                latency_ms=result.latency_ms,
                message=f"live-ok:{self.parser_tag}",
                checked_at=datetime.now(timezone.utc),
            )
        return SourceHealth(
            source=self.source_name,
            healthy=False,
            latency_ms=result.latency_ms,
            message=f"{result.error_type}:{result.message}",
            checked_at=datetime.now(timezone.utc),
        )

    def fetch(self, symbols: list[str]) -> list[SourceRecord]:
        result = self._request(timeout=12, retries=2)
        if not result.ok:
            return []

        now = datetime.now(timezone.utc)
        records: list[SourceRecord] = []
        for idx, symbol in enumerate(symbols):
            content = self._build_content(result.text, symbol)
            seed = f"{self.source_name}:{symbol}:{content[:160]}:{now.date().isoformat()}"
            sid = hashlib.md5(seed.encode("utf-8")).hexdigest()[:16]
            records.append(
                SourceRecord(
                    source=self.source_name,
                    source_id=f"{self.source_name}-{sid}",
                    publish_time=now - timedelta(minutes=idx * 5),
                    content=content,
                    symbol_candidates=[symbol],
                    credibility_score=self.credibility,
                    url=self.url,
                    parser_version=f"v2.2-{self.parser_tag}",
                    crawl_time=now,
                )
            )
        return records


class NewsLiveAdapter(_LiveHttpAdapter):
    def __init__(self) -> None:
        super().__init__("news", "https://www.eastmoney.com/", 0.82, parser_tag="news")


class BlogLiveAdapter(_LiveHttpAdapter):
    def __init__(self) -> None:
        super().__init__("blog", "https://xueqiu.com/", 0.66, parser_tag="blog")


class TiantianFundLiveAdapter(_LiveHttpAdapter):
    def __init__(self) -> None:
        super().__init__("tiantianfund", "https://fund.eastmoney.com/", 0.86, parser_tag="ttfund")


class TonghuashunAIFundLiveAdapter(_LiveHttpAdapter):
    def __init__(self) -> None:
        super().__init__("tonghuashun-aifund", "https://fund.10jqka.com.cn/", 0.84, parser_tag="ths")


class EastmoneyLiveAdapter(_LiveHttpAdapter):
    def __init__(self) -> None:
        super().__init__("eastmoney", "https://www.eastmoney.com/", 0.87, parser_tag="eastmoney")


class SocialMediaLiveAdapter(_LiveHttpAdapter):
    def __init__(self) -> None:
        super().__init__("social-media", "https://weibo.com/", 0.57, parser_tag="weibo")


def build_live_adapters() -> list[SourceAdapter]:
    return [
        NewsLiveAdapter(),
        BlogLiveAdapter(),
        TiantianFundLiveAdapter(),
        TonghuashunAIFundLiveAdapter(),
        EastmoneyLiveAdapter(),
        SocialMediaLiveAdapter(),
    ]
