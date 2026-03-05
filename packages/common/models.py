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


class DecisionOutput(BaseModel):
    fund_code: str = ""
    fund_name: str
    action: Action
    confidence: float = Field(ge=0.0, le=1.0)
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


class DecisionRunResult(BaseModel):
    run_id: str
    recommendation_count: int
    blocked_count: int
