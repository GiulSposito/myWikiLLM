---
name: wiki-query
description: Answers a question using the compiled LLM Wiki. Navigates the wiki graph through wikilinks and cites sources.
---

# Wiki Query Skill

## Trigger
Use when the user asks a question that can be answered from existing wiki knowledge.

## Protocol

### Step 1: Orient
- Read `wiki/index.md` to locate relevant pages
- Read `wiki/overview.md` for domain context

### Step 2: Read
- Read the most relevant pages fully
- Follow wikilinks to related pages when they add context (limit to 2 hops)
- Check `wiki/sources/` pages for evidence when claims need verification
- Prioritize pages with `confidence: high` and `status: active`

### Step 3: Synthesize
- Compose answer from wiki content only
- Cite every claim with its wiki page: `[[page-name]]`
- Rate answer confidence: high (multiple corroborating sources) / medium / low (single or uncertain source)

### Step 4: Flag gaps
- Explicitly state what the wiki does NOT cover on this question
- Suggest which `raw/` sources to ingest to fill the gap

### Step 5: Propose persistence

If the answer reveals reusable knowledge not yet in the wiki, propose one or more of:

**Synthesis page**: If the answer integrates 2+ sources into an interpretive argument that doesn't exist yet → propose `wiki/synthesis/<slug>.md` with thesis.

**Question page**: If the answer reveals an unresolved question → propose `wiki/questions/<slug>.md`.

**Decision page (ADR)**: If the answer contains or surfaces an explicit decision that was made (project or architectural) and no `wiki/decisions/<slug>.md` exists yet → propose creating an ADR. Decision markers: "foi decidido", "optamos por", "ficou definido", "the decision was".

**Pattern page**: If the answer describes a recurring approach that appears in multiple sources → propose `wiki/patterns/<slug>.md`.

**Concept-synthesis**: If the answer relied heavily on a concept page that has 3+ sources in its `sources:` list and `status: draft` → suggest running `/concept-synthesis <slug>` to consolidate it.

Do NOT create any of these automatically — propose and wait for user confirmation.
