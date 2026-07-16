---
name: concept-synthesis
description: Combines knowledge from multiple wiki sources into a coherent, well-structured concept page. Use when a concept is covered by many sources and needs a synthesis pass.
---

# Concept Synthesis Skill

## Trigger
Use when the user asks to synthesize knowledge on a topic, or when a concept page has many sources and has grown fragmented.

## Protocol

### Step 1: Gather
- Read the target concept page (wiki/concepts/<slug>.md)
- Read all pages listed in its sources: field
- Read all pages that wikilink to it

### Step 2: Analyze
- Identify: consensus definition, competing definitions, key distinctions, use cases, trade-offs
- Identify contradictions and label them clearly
- Identify open questions not yet resolved

### Step 3: Write
- Rewrite the concept page with improved structure
- Preserve all source citations
- Keep contradictions visible (never flatten them)
- Use confidence: high only for claims with multiple corroborating sources
- Update status to active after synthesis

### Step 4: Update status
- After rewriting, set `status: active` in the frontmatter — concept-synthesis is the canonical review event
- Update `updated:` to today's date

### Step 5: Report
- List sources used
- List contradictions preserved
- List open questions still unresolved
- Suggest related pages to link
- Confirm: status changed from `draft` to `active`
- If any related concept pages also have 3+ sources and remain `draft`, list them as next candidates for concept-synthesis
