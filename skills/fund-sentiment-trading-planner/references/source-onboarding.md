# Source Onboarding Spec

## Scope

- News
- Blogs
- Tiantian Fund
- Tonghuashun iFund
- Eastmoney
- Social media

## Unified record

```text
source_id
publish_time
content
symbol_candidates
credibility_score
```

## Rules

1. Assign a stable `source_id` per source-document pair.
2. Convert all timestamps to UTC in storage.
3. Keep the original source URL and crawl time for traceability.
4. Deduplicate by `(source, source_id)` first, then by normalized content hash.
5. Record parser version for replay and rollback.
