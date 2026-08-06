# LLM Wiki Vault — Query Optimization Strategy

## Problem

As a wiki vault grows, LLM query operations become token-expensive. The default QUERY protocol reads a flat `index.md` (no content abstracts) and then opens 5–15 full pages to determine relevance. A vault with 400+ pages and ~170 lines/page average means each query can easily consume 3,000–12,000 tokens just in orientation reads before producing an answer.

The root cause is **insufficient signal at the index layer**: the index tells Claude *what pages exist* but not *what they contain*, forcing full-page reads for triage.

---

## Strategy: Three Complementary Layers

The optimization is not a single mechanism but three layers that stack on each other. Each layer reduces token cost for a different query type. Implement them in phases, starting with the highest-ROI layer.

```
Layer 1 — Query Routing Manifest   fast cluster lookup by topic keyword
Layer 2 — Abstract-enriched Index  content signal without opening pages
Layer 3 — Domain Knowledge Maps    single-file orientation for broad queries
```

These layers do not replace the QUERY protocol — they add a pre-filtering step that reduces how many pages the protocol needs to load.

---

## Layer 1: Query Routing Manifest

### What it is

A YAML file at `manifests/query-routing.yml` that maps topic keywords to the canonical set of pages relevant to each topic. Claude reads this file *before* `index.md` during QUERY.

### Structure

```yaml
# manifests/query-routing.yml
# Maps topic keywords → canonical page slugs for that topic.
# Maintained manually; updated as part of every INGEST Step 12.
topics:

  sla:
    label: "SLA e prazos de autorização"
    pages:
      - sla-autorizacao
      - sla-dinamico
      - event-log-dependencia-central
    synthesis:
      - fluxo-autorizacao-ponta-a-ponta

  event-log:
    label: "Event Log como dependência central"
    pages:
      - event-log-como-prerequisito
      - event-log-dependencia-central
      - aut-como-fundacao-event-log
    decisions:
      - event-log-como-prioridade-maxima

  protocolo:
    label: "Protocolo assistencial e regulação"
    pages:
      - protocolo-assistencial
      - protocolo-assistencial-vs-regulacao
    synthesis:
      - protocolo-assistencial-e-autorizacao
```

### How QUERY uses it

```
Step 0 (new) — Read manifests/query-routing.yml.
  If the query matches one or more topic keywords:
    Load only the pages listed under those topics.
    Skip reading index.md entirely.
  If no topic matches:
    Fall back to the standard QUERY Step 1 (read index.md).
```

### How INGEST updates it

At Step 12 of every ingest, the compiler proposes additions to `query-routing.yml`:

- New concepts or entities detected → suggest new topic entry or addition to existing topic's `pages:` list
- Do not auto-update; list proposals in the Step 12 report for user confirmation

### Token reduction

| Query type | Before | After | Reduction |
|-----------|--------|-------|-----------|
| Specific term ("o que é SLA dinâmico") | ~3,000 | ~500 | −83% |
| Known topic area ("decisões sobre event log") | ~5,000 | ~800 | −84% |
| Unknown topic (no routing match) | ~3,000 | ~3,000 | 0% (fallback) |

---

## Layer 2: Abstract-Enriched Index

### What it is

A one- to two-sentence `abstract:` field in the frontmatter of every wiki page. The `rebuild_index.py` script includes the abstract in the generated `index.md` entry. Claude can now read the full index and know *what each page contains* without opening it.

### Frontmatter addition

Add `abstract:` as a required field in the frontmatter schema, immediately after `aliases:`:

```yaml
---
type: concept
status: active
confidence: high
created: 2026-01-15
updated: 2026-07-13
aliases: [SLA dinâmico]
abstract: "Mecanismo que ajusta automaticamente o prazo de SLA de uma autorização com base no tipo de procedimento, complexidade clínica e carga da fila."
sources: [hapvida-slas-autorizacao-jul2026]
tags: [sla, autorizacao, regulacao]
---
```

Rules for writing abstracts:
- 1–2 sentences maximum
- Factual, not meta ("This page describes...") — state the content directly
- Written in the same language as the page content
- Populated at creation time; updated if the page's core meaning changes

### Index entry format (after rebuild)

```markdown
- [[sla-dinamico]] — SLA dinâmico — Mecanismo que ajusta automaticamente o prazo de SLA com base no tipo de procedimento, complexidade clínica e carga da fila. — status: draft, confidence: medium
```

### Retroactive population

For existing pages without `abstract:`, populate via a batch review pass:
- Use `/wiki-review` or an agent loop to generate abstracts from page content
- Run `python scripts/rebuild_index.py` afterward to regenerate the index
- Pages without `abstract:` are valid but flagged as `needs-review` by the linter

### `rebuild_index.py` change

In the index entry generation loop, after extracting `title`, also extract `abstract` from frontmatter and append it to the entry line if present:

```python
abstract = frontmatter.get("abstract", "")
entry = f"- [[{slug}]] — {title}"
if abstract:
    entry += f" — {abstract}"
entry += f" — status: {status}, confidence: {confidence}"
```

### Token reduction

| Scenario | Before | After | Reduction |
|---------|--------|-------|-----------|
| Triage: find pages relevant to a topic | Open 8–12 pages | Read enriched index only | −75% |
| Disambiguation between 3 similar pages | Open all 3 | Abstract resolves it | −85% |

---

## Layer 3: Domain Knowledge Maps

### What it is

A `wiki/synthesis/knowledge-map-<domain>.md` file per major domain. Each map is a compiled, navigable overview of all significant facts, decisions, open questions, and cross-references within a domain — written as a dense reference document (~300–500 lines), not a narrative.

### When to use (QUERY integration)

```
Step 2b (new) — If the matched page cluster has > 5 pages in the same domain:
  Check if wiki/synthesis/knowledge-map-<domain>.md exists.
  If yes: load the knowledge map instead of the individual pages.
  If no: load individual pages as usual.
```

### Structure of a knowledge map

```markdown
---
type: synthesis
status: active
confidence: high
created: YYYY-MM-DD
updated: YYYY-MM-DD
abstract: "Mapa de conhecimento do domínio AUT: autorização de procedimentos médicos, motor de autorização, SLAs, event log, e interfaces com JAS e SAC."
sources: []
tags: [knowledge-map, aut, domain-overview]
---

# Knowledge Map: AUT (Autorização)

## Domain Scope
What this domain covers and its boundaries.

## Core Concepts
- [[concept-slug]] — one-line description of its role in the domain
- [[concept-slug-2]] — ...

## Key Decisions
- [[decision-slug]] — what was decided and why (one line)

## Active Synthesis Pages
- [[synthesis-slug]] — thesis in one line

## Open Questions
- [[question-slug]] — what is unresolved

## Domain Interfaces
- **→ JAS**: how AUT connects to JAS (one line)
- **→ SAC**: how AUT connects to SAC (one line)

## Data Assets
- [[data-dictionary/aut/index]] — tables and indicators

## Last Full Synthesis Pass
YYYY-MM-DD
```

### Maintenance

Knowledge maps are **not** updated during ingest — they are regenerated periodically via `/wiki-review` or explicitly when a synthesis pass is done. Each map includes a `Last Full Synthesis Pass` date so staleness is visible.

### Token reduction

| Query type | Before | After | Reduction |
|-----------|--------|-------|-----------|
| "Me dê uma visão geral do domínio AUT" | ~10,000 | ~2,500 | −75% |
| "Quais decisões foram tomadas em AUT?" | ~6,000 | ~1,500 | −75% |
| Cross-domain query (AUT + JAS) | ~15,000 | ~5,000 | −67% |

---

## Implementation Phases

### Phase 1 — Query Routing (highest ROI, lowest effort)

1. Create `manifests/query-routing.yml` covering all current topics in the vault
2. Update `CLAUDE.md` QUERY protocol: add Step 0 to read routing before index
3. Update `CLAUDE.md` INGEST Step 12: add routing update proposals to the report

**Effort:** ~2–3 hours  
**Impact:** immediate on all queries with recognizable topic terms

### Phase 2 — Abstract Enrichment (improves fallback quality)

1. Add `abstract:` to frontmatter schema in `CLAUDE.md`
2. Update `scripts/rebuild_index.py` to include abstract in index entries
3. Add linter check for missing `abstract:` field
4. Populate abstracts retroactively on all existing pages (batch pass)
5. Run `rebuild_index.py` to regenerate enriched `index.md`

**Effort:** ~4–6 hours (including retroactive population)  
**Impact:** improves quality of fallback path (when routing doesn't match)

### Phase 3 — Domain Knowledge Maps (for broad queries)

1. Update `CLAUDE.md` QUERY Step 2b to check for knowledge maps
2. Create knowledge maps for each major domain in priority order
3. Define update cadence: maps are regenerated explicitly, not on every ingest

**Effort:** ~3–4 hours per domain  
**Impact:** major reduction for orientation and cross-domain queries

---

## What NOT to implement

### RAG with vector embeddings

Breaks the Markdown-first paradigm. Adds infrastructure (embedding model, vector store), a re-indexing step on every ingest, and latency. Justified only if the vault exceeds ~2,000 pages and routing/abstracts no longer provide sufficient precision. At that scale, use a lightweight local option (ChromaDB + `sentence-transformers`) rather than a hosted service.

### Knowledge graph in YAML

A full node/edge YAML of 400+ pages (~4–5k lines) costs as many tokens to read as the index itself, without the content signal that abstracts provide. Not worth the maintenance burden.

---

## Combined Token Reduction Estimate

| Query scenario | Baseline tokens | Post-Phase 1+2 | Post-Phase 1+2+3 |
|---------------|----------------|----------------|------------------|
| Specific term query | ~3,000 | ~500 | ~500 |
| Domain orientation | ~10,000 | ~3,500 | ~2,000 |
| Cross-domain synthesis | ~15,000 | ~6,000 | ~4,000 |
| Ingest dedup check | ~2,000 | ~400 | ~400 |

---

## Files Changed Per Phase

### Phase 1
- `manifests/query-routing.yml` — new file
- `CLAUDE.md` — QUERY Step 0 (new), INGEST Step 12 (updated)

### Phase 2
- `CLAUDE.md` — frontmatter schema (add `abstract:`), linter check (new)
- `scripts/rebuild_index.py` — include abstract in entry format
- All `wiki/**/*.md` — add `abstract:` field to frontmatter (batch)

### Phase 3
- `CLAUDE.md` — QUERY Step 2b (new)
- `wiki/synthesis/knowledge-map-<domain>.md` — one per domain (new files)
