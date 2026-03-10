from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone

from .market_data import fetch_market_series
from .models import BacktestFundMetric, BacktestRunResult
from .repository import StateRepository


def _weighted(signal) -> float:
    return signal.polarity * signal.intensity * signal.credibility * signal.relevance


def _max_drawdown(returns: list[float]) -> float:
    peak = 1.0
    equity = 1.0
    max_dd = 0.0
    for r in returns:
        equity *= (1.0 + r)
        peak = max(peak, equity)
        dd = (peak - equity) / peak
        max_dd = max(max_dd, dd)
    return round(max_dd, 4)


def _signal_daily_score(rows: list) -> dict[str, float]:
    bucket: dict[str, list[float]] = defaultdict(list)
    for s in rows:
        day = s.publish_time.date().strftime('%Y-%m-%d')
        bucket[day].append(_weighted(s))
    return {d: (sum(vs) / len(vs)) for d, vs in bucket.items()}


def run_backtest(repo: StateRepository, window_days: int = 365) -> BacktestRunResult:
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=window_days)
    signals = [s for s in repo.list_signals() if s.publish_time >= since]
    portfolio = repo.list_portfolio()

    by_symbol: dict[str, list] = defaultdict(list)
    for s in signals:
        for sym in s.symbol_candidates:
            by_symbol[sym].append(s)

    metrics: list[BacktestFundMetric] = []
    for p in portfolio:
        rows = sorted(by_symbol.get(p.fund_name, []) + by_symbol.get(p.fund_code, []), key=lambda x: x.publish_time)
        if len(rows) < 2:
            metrics.append(
                BacktestFundMetric(
                    fund_code=p.fund_code,
                    fund_name=p.fund_name,
                    samples=0,
                    hit_rate=0.0,
                    max_drawdown=0.0,
                    recommendation_stability=1.0,
                    signal_latency_hours=24.0,
                    label_source="proxy",
                )
            )
            continue

        daily_score = _signal_daily_score(rows)
        series = fetch_market_series(p.fund_code, days=window_days)
        nav_points = series.points

        preds: list[int] = []
        actuals: list[int] = []
        returns: list[float] = []
        latencies: list[float] = []

        for i in range(len(nav_points) - 1):
            d0 = nav_points[i].date
            d1 = nav_points[i + 1].date
            if d0 not in daily_score:
                continue
            pred = 1 if daily_score[d0] >= 0 else -1
            change = nav_points[i + 1].nav - nav_points[i].nav
            if change == 0:
                continue
            act = 1 if change > 0 else -1
            preds.append(pred)
            actuals.append(act)
            pct = abs(change / max(1e-8, nav_points[i].nav))
            pct = min(0.05, pct)
            returns.append(pct if pred == act else -pct)
            latencies.append(24.0)

        samples = len(preds)
        if samples == 0:
            metrics.append(
                BacktestFundMetric(
                    fund_code=p.fund_code,
                    fund_name=p.fund_name,
                    samples=0,
                    hit_rate=0.0,
                    max_drawdown=0.0,
                    recommendation_stability=1.0,
                    signal_latency_hours=24.0,
                    label_source=series.source,
                )
            )
            continue

        hit_rate = round(sum(1 for i in range(samples) if preds[i] == actuals[i]) / samples, 4)
        stability = 1.0
        if samples > 1:
            switches = sum(1 for i in range(1, samples) if preds[i] != preds[i - 1])
            stability = round(1.0 - (switches / (samples - 1)), 4)

        metrics.append(
            BacktestFundMetric(
                fund_code=p.fund_code,
                fund_name=p.fund_name,
                samples=samples,
                hit_rate=hit_rate,
                max_drawdown=_max_drawdown(returns),
                recommendation_stability=stability,
                signal_latency_hours=round(sum(latencies) / len(latencies), 2) if latencies else 0.0,
                label_source=series.source,
            )
        )

    result = BacktestRunResult(
        run_id=now.strftime("backtest-%Y%m%d-%H%M%S"),
        window_days=window_days,
        metrics=metrics,
        generated_at=now,
    )
    repo.save_backtest_run(result)
    return result
