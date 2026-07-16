---
type: concept
status: active
confidence: high
created: 2026-07-13
updated: 2026-07-13
aliases: [Dashboard]
sources: []
tags: [meta, dashboard]
---

# Wiki Dashboard

## Pages needing review

```dataview
TABLE type, confidence, updated
FROM "wiki"
WHERE status = "needs-review"
SORT updated DESC
```

## Low confidence pages

```dataview
TABLE type, status, updated
FROM "wiki"
WHERE confidence = "low"
SORT updated DESC
```

## Conflict pages

```dataview
TABLE type, updated
FROM "wiki"
WHERE status = "conflict"
SORT updated DESC
```

## Recent sources

```dataview
TABLE updated, confidence
FROM "wiki/sources"
SORT updated DESC
LIMIT 20
```

## All concepts

```dataview
TABLE status, confidence, updated
FROM "wiki/concepts"
SORT updated DESC
```

## All entities

```dataview
TABLE status, updated
FROM "wiki/entities"
SORT updated DESC
```
