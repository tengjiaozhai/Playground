from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone

from .models import DecisionOutput, DecisionRunResult, SentimentSignal
from .repository import StateRepository


def _weighted_score(row: SentimentSignal) -> float:
    return row.polarity * row.intensity * row.credibility * row.relevance


def _action_from_score(score: float, confidence: float) -> str:
    if confidence < 0.55:
        return "watch"
    if score > 0.08:
        return "buy"
    if score < -0.08:
        return "sell"
    return "watch"


def _target_position(action: str) -> str:
    if action == "buy":
        return "40%-60%"
    if action == "sell":
        return "0%-20%"
    return "20%-40%"


def _stops(score: float) -> tuple[str, str]:
    magnitude = min(1.0, abs(score) * 8)
    stop_profit = 0.08 + magnitude * 0.07
    stop_loss = 0.03 + magnitude * 0.05
    return f"{stop_profit:.1%}", f"{stop_loss:.1%}"


def run_decision(repo: StateRepository) -> DecisionRunResult:
    now = datetime.now(timezone.utc)
    run_id = now.strftime("decision-%Y%m%d-%H%M%S")
    signals = repo.list_signals()
    portfolio = repo.list_portfolio()

    buckets: dict[str, list[SentimentSignal]] = defaultdict(list)
    for signal in signals:
        for symbol in signal.symbol_candidates:
            buckets[symbol].append(signal)

    outputs: list[DecisionOutput] = []
    blocked_count = 0
    for position in portfolio:
        related = buckets.get(position.fund_name, []) + buckets.get(position.fund_code, [])
        if not related:
            related = []

        score_values = [_weighted_score(s) for s in related]
        score = sum(score_values) / len(score_values) if score_values else 0.0
        confidence = min(0.99, 0.45 + min(0.45, len(related) * 0.01) + min(0.09, abs(score) * 2))

        pos_count = len([v for v in score_values if v > 0])
        neg_count = len([v for v in score_values if v < 0])
        conflict_summary = f"positive={pos_count}, negative={neg_count}, total={len(score_values)}"

        reasons = [
            f"aggregated_score={score:.4f}",
            f"confidence={confidence:.2f}",
            f"risk_mode=balanced",
        ]
        counter_evidence = [
            f"{s.source}:{s.polarity:.2f}" for s in sorted(related, key=lambda x: x.polarity)[:3]
        ]
        sources = sorted({s.source for s in related})

        if position.pending_code_binding:
            action = "watch"
            target_position = "hold"
            stop_profit = "n/a"
            stop_loss = "n/a"
            blocked_count += 1
            reasons.insert(0, "pending_code_binding=true, trading action blocked")
        else:
            action = _action_from_score(score, confidence)
            target_position = _target_position(action)
            stop_profit, stop_loss = _stops(score)

        outputs.append(
            DecisionOutput(
                fund_code=position.fund_code,
                fund_name=position.fund_name,
                action=action,
                confidence=round(confidence, 4),
                target_position=target_position,
                stop_profit=stop_profit,
                stop_loss=stop_loss,
                reasons=reasons,
                counter_evidence=counter_evidence,
                evidence_sources=sources,
                conflict_summary=conflict_summary,
                generated_at=now,
            )
        )

    repo.upsert_recommendations(outputs)
    return DecisionRunResult(
        run_id=run_id,
        recommendation_count=len(outputs),
        blocked_count=blocked_count,
    )
