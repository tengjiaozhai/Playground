---
name: fund-sentiment-trading-planner
description: Plan, design, and iterate a multi-source fund sentiment analysis and decision-support system. Use when building or evolving workflows that ingest news/blog/fund-site/social signals, map fund name+code dual identity, produce buy/sell/watch recommendations with stop-profit and stop-loss, maintain portfolio state, generate daily reports, and manage roadmap versions through 计划版本.md.
---

# Fund Sentiment Trading Planner

Use this skill to keep implementation decisions consistent across roadmap versions.

## Follow this workflow

1. Read `docs/计划版本.md` and identify current version scope.
2. Confirm constraints before coding:
- Keep dual-key identity for each fund: `fund_name` and `fund_code`.
- Block trade actions when `pending_code_binding=true`.
- Include evidence source list, generation timestamp, and conflict summary in each recommendation.
3. Keep API compatibility with the frozen first version:
- `POST /ingest/run`
- `GET /funds/{code_or_name}/signals`
- `POST /decision/run`
- `GET /portfolio/recommendations`
- `GET /reports/daily?date=YYYY-MM-DD`
4. Apply risk mode defaults from balanced policy unless explicitly overridden.
5. Update `docs/计划版本.md` after each version increment using the fixed sections.
6. Append a new entry to `docs/实现说明.md` immediately after each completed implementation.
7. In each summary entry, include changed files, runnable commands, features delivered, test status, and follow-up items.

## Load references only when needed

- Source onboarding and normalization: `references/source-onboarding.md`
- Signal and decision rules: `references/signal-schema.md`
- Backtest and acceptance metrics: `references/backtest-eval.md`
- Report writing templates: `references/recommendation-template.md`
- Implementation summary protocol: `references/implementation-summary.md`

## Script entrypoints

Use these scripts when repetitive transformations are needed:

- `scripts/normalize_sources.py`
- `scripts/score_signal.py`
- `scripts/generate_daily_report.py`

Each script currently defines CLI contracts and extension points. Fill implementations per roadmap stage instead of ad-hoc notebook logic.

## Guardrails

1. Keep this project as research and decision support only.
2. Keep source compliance explicit: rate limit, attribution, and terms checks.
3. Prefer deterministic, testable rules for V1-V2; defer model-heavy logic to V3+.
4. Never finish a feature turn without updating `docs/实现说明.md`.
