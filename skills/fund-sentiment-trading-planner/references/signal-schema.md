# Signal and Decision Schema

## SentimentSignal

```text
source
ts
polarity [-1, 1]
intensity [0, 1]
credibility [0, 1]
relevance [0, 1]
content
symbol_candidates[]
```

## DecisionOutput

```text
action: buy|sell|watch
confidence: [0, 1]
target_position: string range
stop_profit: percent string
stop_loss: percent string
reasons[]
counter_evidence[]
evidence_sources[]
conflict_summary
```

## Mandatory constraints

1. If `pending_code_binding=true`, force `action=watch`.
2. Include at least one reason and one evidence source.
3. Always emit a conflict summary.
