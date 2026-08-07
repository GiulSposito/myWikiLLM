# Page Templates — LLM Wiki Vault

Reference file for page creation during ingest. Contains all templates, the full type/status/confidence taxonomy, and frontmatter examples.

Consulted by `wiki-ingest` Step 3 when creating a new page. Not loaded automatically — only when explicitly referenced.

---

## Frontmatter Schema

### Required Fields (all pages)

```yaml
---
type: <type>          # see Type Taxonomy below
status: <status>      # see Status Values below
confidence: <level>   # low | medium | high
created: YYYY-MM-DD
updated: YYYY-MM-DD
aliases: []           # alternative names for this page
abstract: ""          # 1–2 factual sentences (required for concept/entity/synthesis/source/pattern/decision)
sources: []           # list of source slugs that support this page
tags: []              # domain and topic tags
---
```

**Rules for `abstract:`**
- 1–2 sentences maximum. Factual, not meta — never write "This page describes..."
- Required for: `concept`, `entity`, `synthesis`, `source`, `pattern`, `decision`
- Optional for: `question`, `comparison`, `data-dictionary`

### Minimal valid frontmatter

```yaml
---
type: concept
status: draft
confidence: low
created: 2026-01-15
updated: 2026-01-15
aliases: []
abstract: ""
sources: []
tags: []
---
```

### Fully populated example

```yaml
---
type: concept
status: active
confidence: high
created: 2026-01-10
updated: 2026-07-13
aliases: [RAG, Retrieval Augmented Generation]
abstract: "Técnica que combina recuperação de documentos relevantes com geração de texto para reduzir alucinações em LLMs."
sources: [lewis-2020-rag-paper, gao-2023-rag-survey]
tags: [nlp, retrieval, architecture, llm]
---
```

---

## Type Taxonomy

| Type | Where | Purpose |
|------|-------|---------|
| `source` | `wiki/sources/` | Bibliographic record of an ingested document |
| `entity` | `wiki/entities/` | A named thing: company, person, product, tool |
| `concept` | `wiki/concepts/` | A definition, mechanism, or framework |
| `project` | `wiki/projects/` | An ongoing or historical project |
| `pattern` | `wiki/patterns/` | A recurring solution to a recurring problem |
| `decision` | `wiki/decisions/` | A recorded design or architectural decision |
| `synthesis` | `wiki/synthesis/` | An interpretive argument across multiple sources |
| `comparison` | `wiki/comparisons/` | Structured comparison between two or more things |
| `question` | `wiki/questions/` | An open question, unknown, or hypothesis |
| `data-dictionary` | `wiki/data-dictionary/<domain>/` | Structured catalog of data assets — tables, fields, schemas |

## Status Values

| Status | Meaning |
|--------|---------|
| `draft` | Freshly created, not yet reviewed |
| `active` | Reviewed and current |
| `needs-review` | Outdated or flagged for update |
| `deprecated` | No longer relevant, kept for history |
| `conflict` | Contains a contradiction that has not been resolved |

## Confidence Levels

| Confidence | Meaning |
|-----------|---------|
| `low` | Single source, weak evidence, or high uncertainty |
| `medium` | Multiple sources or moderate evidence |
| `high` | Well-corroborated across independent sources |

## Status Promotion Criteria

| Transition | Trigger |
|-----------|---------|
| `draft → active` | Page has 2+ corroborating sources in `sources:` list AND has been reviewed at least once |
| `active → needs-review` | `updated` is more than 60 days old, OR a new source introduces conflicting information |
| `draft → conflict` | A claim in the page directly contradicts a claim in a different source — set immediately |
| `conflict → active` | Contradiction resolved (both positions documented, resolution rationale written) |
| `active → deprecated` | Page no longer relevant — keep for history, add note explaining why |

---

## Template: source

File path: `wiki/sources/<slug>.md`

```markdown
---
type: source
status: draft
confidence: medium
created: YYYY-MM-DD
updated: YYYY-MM-DD
aliases: []
abstract: ""
sources: []
tags: []
---

# <Title of the Source>

## Bibliographic Metadata

- **Author(s)**: 
- **Date**: 
- **Type**: article | paper | book | talk | transcript | repo | web-clipping
- **URL / DOI**: 
- **Raw file**: `raw/<subfolder>/<filename>`
- **Ingested**: YYYY-MM-DD

## Summary

One to three paragraphs capturing the main argument or purpose of the source.

## Key Claims

1. 
2. 
3. 

## Important Quotes

> "Exact quote." (p. X or timestamp)

## Relevant Entities

- [[entity-slug]] — brief reason for relevance

## Relevant Concepts

- [[concept-slug]] — brief reason for relevance

## Contradictions

Claims in this source that conflict with existing wiki knowledge. If none found, write "None identified."

- Conflicts with [[concept-slug]]: <describe conflict>

## Pages Updated

- [[page-slug]] — what was added/changed

## Open Questions

- 
```

---

## Template: concept

File path: `wiki/concepts/<slug>.md`

```markdown
---
type: concept
status: draft
confidence: medium
created: YYYY-MM-DD
updated: YYYY-MM-DD
aliases: []
abstract: ""
sources: []
tags: []
---

# <Concept Name>

## Definition

A precise, source-backed definition. Cite at least one source.

## Why It Matters

Why this concept is significant in its domain.

## How It Works

Mechanism, process, or structure.

## Related Concepts

- [[concept-slug]] — relationship description

## Related Entities

- [[entity-slug]] — how this entity relates to the concept

## Examples

1. **Example name**: Description. Source: [[source-slug]]

## Source-Backed Claims

- Claim text. ([[source-slug]])

## Contradictions / Competing Views

- [[source-slug]] argues X, while [[source-slug-2]] argues Y.

## Open Questions

-
```

---

## Template: entity

File path: `wiki/entities/<slug>.md`

```markdown
---
type: entity
status: draft
confidence: medium
created: YYYY-MM-DD
updated: YYYY-MM-DD
aliases: []
abstract: ""
sources: []
tags: []
---

# <Entity Name>

## Description

A factual description of this entity.

## Type

`company` | `person` | `product` | `tool` | `organization` | `standard`

## Key Facts

- **Founded / Created**: 
- **Origin / Affiliation**: 
- **Current status**: 
- **Notable for**: 

## Related Concepts

- [[concept-slug]] — relationship description

## Related Projects

- [[project-slug]] — relationship description

## Related Entities

- [[entity-slug]] — relationship description

## Sources

- [[source-slug]] — what this source says about the entity

## Open Questions

-
```

---

## Template: decision

File path: `wiki/decisions/<slug>.md`

```markdown
---
type: decision
status: draft
confidence: medium
created: YYYY-MM-DD
updated: YYYY-MM-DD
aliases: []
abstract: ""
sources: []
tags: []
---

# <Decision Title>

## Context

What situation or problem prompted this decision? What constraints were in play?

## Decision

The decision that was made, stated clearly and specifically.

## Rationale

Why this decision was made over the alternatives.

## Alternatives Considered

| Alternative | Why rejected |
|-------------|-------------|
|             |             |

## Consequences

**Positive:**
- 

**Negative / Trade-offs:**
- 

## Related Pages

- [[page-slug]]

## Source Evidence

- [[source-slug]] — relevant evidence or precedent
```

---

## Template: synthesis

File path: `wiki/synthesis/<slug>.md`

```markdown
---
type: synthesis
status: draft
confidence: low
created: YYYY-MM-DD
updated: YYYY-MM-DD
aliases: []
abstract: ""
sources: []
tags: []
---

# <Synthesis Title>

## Thesis

The central interpretive claim of this synthesis.

## Supporting Arguments

1. **Argument**: Description. ([[source-slug]])
2. **Argument**: Description. ([[source-slug-2]])

## Counterarguments

- Counterargument: Description. ([[source-slug]])

## Sources

- [[source-slug]]

## Confidence

Explain why the confidence level was set as it was.

## Open Questions

-
```

---

## Template: pattern

File path: `wiki/patterns/<slug>.md`

```markdown
---
type: pattern
status: draft
confidence: medium
created: YYYY-MM-DD
updated: YYYY-MM-DD
aliases: []
abstract: ""
sources: []
tags: []
---

# <Pattern Name>

## Problem

The recurring problem this pattern addresses.

## Solution

The solution approach. Specific enough to be actionable.

## When to Use

Conditions under which this pattern applies.

## When NOT to Use

Conditions that make this pattern inappropriate.

## Trade-offs

| Benefit | Cost |
|---------|------|
|         |      |

## Examples

1. **Example**: Description. Source: [[source-slug]]

## Related Patterns

- [[pattern-slug]] — how they relate

## Sources

- [[source-slug]]
```

---

## Template: knowledge-map

File path: `wiki/synthesis/knowledge-map-<domain>.md`

A pre-compiled dense reference for a major domain. Used by the QUERY protocol when a cluster has more than 5 pages in the same domain. Regenerated periodically via `/wiki-review` or an explicit synthesis pass — not updated during ingest.

```markdown
---
type: synthesis
status: active
confidence: high
created: YYYY-MM-DD
updated: YYYY-MM-DD
aliases: []
abstract: "Mapa de conhecimento do domínio <DOMAIN>: <one-sentence scope description>."
sources: []
tags: [knowledge-map, <domain>, domain-overview]
---

# Knowledge Map: <DOMAIN>

## Domain Scope

What this domain covers and its boundaries.

## Core Concepts

- [[concept-slug]] — one-line role in the domain

## Key Decisions

- [[decision-slug]] — what was decided and why (one line)

## Active Synthesis Pages

- [[synthesis-slug]] — thesis in one line

## Open Questions

- [[question-slug]] — what is unresolved

## Domain Interfaces

- **→ <other-domain>**: how this domain connects (one line)

## Data Assets

- [[data-dictionary/<domain>/index]] — tables and indicators

## Last Full Synthesis Pass

YYYY-MM-DD
```

---

## Log Entry Format

```markdown
## YYYY-MM-DD — Ingest: <Source Title>

- Source: [[source-slug]]
- New pages: [[page-1]], [[page-2]]
- Updated pages: [[page-3]], [[page-4]]
- Conflicts detected: [[concept-slug]] (see status: conflict)
- Open questions: [[question-slug]]
```
