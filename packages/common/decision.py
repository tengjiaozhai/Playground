from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone

from .llm_assist import assist_decision
from .models import DecisionOutput, DecisionRunResult, SentimentSignal
from .repository import StateRepository


SOURCE_WEIGHT = {
    "news": 1.0,
    "blog": 0.8,
    "tiantianfund": 1.15,
    "tonghuashun-aifund": 1.12,
    "eastmoney": 1.18,
    "social-media": 0.72,
}


def _weighted_score(row: SentimentSignal) -> float:
    w = SOURCE_WEIGHT.get(row.source, 1.0)
    return row.polarity * row.intensity * row.credibility * row.relevance * w


def _action_from_score(score: float, confidence: float) -> str:
    if confidence < 0.55:
        return "watch"
    if score > 0.08:
        return "buy"
    if score < -0.08:
        return "sell"
    return "watch"


def _probabilities(score: float) -> tuple[float, float]:
    # map score (-1..1 approx) to up/down probabilities
    bounded = max(-1.0, min(1.0, score * 4))
    up = 0.5 + (bounded * 0.25)
    up = max(0.01, min(0.99, up))
    down = max(0.01, min(0.99, 1.0 - up))
    return round(up, 4), round(down, 4)


def _volatility_strength(score_values: list[float]) -> float:
    if not score_values:
        return 0.0
    avg = sum(abs(v) for v in score_values) / len(score_values)
    return round(max(0.0, min(1.0, avg * 6)), 4)


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
        up_prob, down_prob = _probabilities(score)
        volatility = _volatility_strength(score_values)

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
        llm_used = False
        llm_provider = ""
        llm_model = ""
        llm_stage = ""
        llm_explanation = ""
        llm_risk_note = ""

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

            llm_payload = {
                "fund_name": position.fund_name,
                "fund_code": position.fund_code,
                "base_action": action,
                "confidence": round(confidence, 4),
                "up_probability": up_prob,
                "down_probability": down_prob,
                "volatility_strength": volatility,
                "signal_count": len(related),
                "sources": sources,
                "top_positive": [f"{s.source}:{s.polarity:.2f}" for s in sorted(related, key=lambda x: x.polarity, reverse=True)[:3]],
                "top_negative": [f"{s.source}:{s.polarity:.2f}" for s in sorted(related, key=lambda x: x.polarity)[:3]],
            }
            llm_result = assist_decision(llm_payload)
            if llm_result:
                llm_used = True
                llm_provider = str(llm_result.get("provider", "DeepSeek"))
                llm_model = str(llm_result.get("model", ""))
                llm_stage = str(llm_result.get("stage", "decision_review"))
                # Keep base action unless model confidence is sufficiently strong.
                if confidence >= 0.6:
                    action = llm_result.get("action", action)
                    target_position = _target_position(action)
                confidence = max(0.0, min(0.99, confidence + float(llm_result.get("confidence_delta", 0.0))))
                if llm_result.get("explanation"):
                    llm_explanation = str(llm_result["explanation"])
                    reasons.append(f"llm_explanation={llm_result['explanation']}")
                if llm_result.get("risk_note"):
                    llm_risk_note = str(llm_result["risk_note"])
                    reasons.append(f"llm_risk_note={llm_result['risk_note']}")

        outputs.append(
            DecisionOutput(
                fund_code=position.fund_code,
                fund_name=position.fund_name,
                action=action,
                confidence=round(confidence, 4),
                up_probability=up_prob,
                down_probability=down_prob,
                volatility_strength=volatility,
                target_position=target_position,
                stop_profit=stop_profit,
                stop_loss=stop_loss,
                reasons=reasons,
                counter_evidence=counter_evidence,
                evidence_sources=sources,
                conflict_summary=conflict_summary,
                llm_used=llm_used,
                llm_provider=llm_provider,
                llm_model=llm_model,
                llm_stage=llm_stage,
                llm_explanation=llm_explanation,
                llm_risk_note=llm_risk_note,
                generated_at=now,
            )
        )

    repo.upsert_recommendations(outputs)
    return DecisionRunResult(
        run_id=run_id,
        recommendation_count=len(outputs),
        blocked_count=blocked_count,
    )
