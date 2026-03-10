from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Action = Literal["buy", "sell", "watch"]


class FundIdentity(BaseModel):
    fund_code: str = ""
    fund_name: str
    aliases: list[str] = Field(default_factory=list)
    pending_code_binding: bool = True


class PortfolioPosition(BaseModel):
    fund_code: str = ""
    fund_name: str
    amount: float = 0.0
    cost: float = 0.0
    updated_at: datetime
    pending_code_binding: bool = True


class SentimentSignal(BaseModel):
    source: str
    source_id: str
    ts: datetime
    publish_time: datetime
    polarity: float = Field(ge=-1.0, le=1.0)
    intensity: float = Field(ge=0.0, le=1.0)
    credibility: float = Field(ge=0.0, le=1.0)
    relevance: float = Field(ge=0.0, le=1.0)
    content: str
    symbol_candidates: list[str] = Field(default_factory=list)


class RawSourceRecord(BaseModel):
    source: str
    source_id: str
    publish_time: datetime
    content: str
    symbol_candidates: list[str] = Field(default_factory=list)
    credibility_score: float = Field(ge=0.0, le=1.0)
    url: str = ""
    parser_version: str = "v2.0"
    crawl_time: datetime
    content_hash: str


class FeatureRecord(BaseModel):
    source: str
    source_id: str
    ts: datetime
    polarity: float = Field(ge=-1.0, le=1.0)
    intensity: float = Field(ge=0.0, le=1.0)
    heat: float = Field(ge=0.0, le=1.0)
    spread_speed: float = Field(ge=0.0, le=1.0)
    credibility: float = Field(ge=0.0, le=1.0)
    relevance: float = Field(ge=0.0, le=1.0)
    conflict: float = Field(ge=0.0, le=1.0)
    symbol_candidates: list[str] = Field(default_factory=list)


class DecisionOutput(BaseModel):
    fund_code: str = ""
    fund_name: str
    action: Action
    confidence: float = Field(ge=0.0, le=1.0)
    up_probability: float = Field(ge=0.0, le=1.0, default=0.5)
    down_probability: float = Field(ge=0.0, le=1.0, default=0.5)
    volatility_strength: float = Field(ge=0.0, le=1.0, default=0.0)
    target_position: str
    stop_profit: str
    stop_loss: str
    reasons: list[str]
    counter_evidence: list[str]
    evidence_sources: list[str]
    conflict_summary: str
    generated_at: datetime


class DailyReport(BaseModel):
    date: str
    markdown: str
    html: str
    generated_at: datetime


class IngestRunResult(BaseModel):
    run_id: str
    created_count: int
    total_signals: int
    raw_count: int = 0
    feature_count: int = 0
    by_source: dict[str, int] = Field(default_factory=dict)
    mode: str = "hybrid"
    source_errors: dict[str, str] = Field(default_factory=dict)


class SourceHealthStatus(BaseModel):
    source: str
    healthy: bool
    latency_ms: int
    message: str
    checked_at: datetime


class IngestStatus(BaseModel):
    run_id: str
    started_at: datetime
    finished_at: datetime
    status: str
    created_count: int
    raw_count: int
    feature_count: int
    total_signals: int
    by_source: dict[str, int] = Field(default_factory=dict)
    mode: str = "hybrid"
    source_errors: dict[str, str] = Field(default_factory=dict)


class DecisionRunResult(BaseModel):
    run_id: str
    recommendation_count: int
    blocked_count: int


class BacktestFundMetric(BaseModel):
    fund_code: str = ""
    fund_name: str
    samples: int
    hit_rate: float = Field(ge=0.0, le=1.0)
    max_drawdown: float = Field(ge=0.0)
    recommendation_stability: float = Field(ge=0.0, le=1.0)
    signal_latency_hours: float = Field(ge=0.0)
    label_source: str = "proxy"


class BacktestRunResult(BaseModel):
    run_id: str
    window_days: int
    metrics: list[BacktestFundMetric]
    generated_at: datetime
