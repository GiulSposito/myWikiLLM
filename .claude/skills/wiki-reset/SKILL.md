---
name: wiki-reset
description: Resets the wiki to a blank state. Deletes all ingested content (sources, entities, concepts, and all derived pages) and restores structural files to their initial templates. raw/ is never touched.
---

# Wiki Reset Skill

## Trigger

Use this skill when the user wants to wipe all ingested content from the wiki and
start fresh. This is a destructive, irreversible operation.

**Never run this skill without explicit user confirmation.**

---

## What is affected

### Directories deleted entirely

| Directory | Contents |
|-----------|----------|
| `wiki/sources/` | Source pages created by ingest |
| `wiki/entities/` | Entity pages |
| `wiki/concepts/` | Concept pages |
| `wiki/projects/` | Project pages |
| `wiki/patterns/` | Pattern pages |
| `wiki/decisions/` | Decision / ADR pages |
| `wiki/synthesis/` | Synthesis pages |
| `wiki/comparisons/` | Comparison pages |
| `wiki/questions/` | Open question pages |
| `wiki/data-dictionary/` | Data-dictionary domain pages |
| `outputs/reports/` | Wiki-lint reports |
| `outputs/briefings/` | Generated briefings |
| `outputs/presentations/` | Generated presentations |
| `maps/canvas/` | Canvas maps |
| `maps/excalidraw/` | Excalidraw diagrams |
| `maps/mermaid/` | Mermaid diagrams |
| `staging/` | Batch-ingest intermediate artifacts (`.gitkeep` preserved) |

### Files reset to blank templates

| File | Restored to |
|------|------------|
| `wiki/index.md` | Empty index with today's date |
| `wiki/log.md` | Empty log with today's date |
| `manifests/sources.yml` | `sources: []` |
| `manifests/aliases.yml` | Empty alias registry |
| `manifests/query-routing.yml` | `topics: {}` |

### Never touched (invariants)

- `raw/` — immutable audit layer
- `wiki/overview.md` — vault description, not ingested content
- `wiki/dashboard.md` — Dataview queries, not ingested content
- `manifests/taxonomy.yml` — validation source of truth
- `manifests/batch-ingest.yml` — pipeline configuration
- `.claude/` — skills, agents, commands
- `scripts/` — validation scripts

---

## Protocol

### Step 1: Inventory

Count files in each affected area. Run:

```bash
for dir in wiki/sources wiki/entities wiki/concepts wiki/projects wiki/patterns \
           wiki/decisions wiki/synthesis wiki/comparisons wiki/questions \
           wiki/data-dictionary outputs/reports outputs/briefings \
           outputs/presentations maps/canvas maps/excalidraw maps/mermaid; do
  count=$(find "$dir" -type f 2>/dev/null | wc -l | tr -d ' ')
  if [ "$count" -gt 0 ]; then echo "$dir: $count files"; fi
done

staging_count=$(find staging -mindepth 1 -not -name '.gitkeep' 2>/dev/null | wc -l | tr -d ' ')
echo "staging/: $staging_count items"
```

Compute the total file count. If total is 0, inform the user: "Wiki is already empty. Nothing to reset."

### Step 2: Present warning and require explicit confirmation

Display a prominent warning block with:

1. **Impact summary**: exact counts per directory from Step 1
2. **Files to be reset**: list the 5 structural files that will be restored to blank templates
3. **What will NOT be touched**: explicitly mention `raw/`, `overview.md`, `dashboard.md`, `taxonomy.yml`, `batch-ingest.yml`
4. **Confirmation instruction**: ask the user to type `confirmar reset` (or `confirm reset` in English) to proceed

Use `AskUserQuestion` to present the choice:
- Option A: "Confirmar reset — apagar tudo" (proceed)
- Option B: "Cancelar" (abort)

If the user cancels or does not explicitly confirm: print "Reset cancelled. No files were modified." and stop immediately.

### Step 3: Delete ingested content

Only after confirmed. Run in sequence:

```bash
# Delete wiki content directories
rm -rf wiki/sources wiki/entities wiki/concepts wiki/projects wiki/patterns \
       wiki/decisions wiki/synthesis wiki/comparisons wiki/questions \
       wiki/data-dictionary 2>/dev/null

# Delete generated outputs (preserve directory structure)
find outputs/reports outputs/briefings outputs/presentations \
     -type f -delete 2>/dev/null

# Delete generated maps (preserve directory structure)
find maps/canvas maps/excalidraw maps/mermaid \
     -type f -delete 2>/dev/null

# Clean staging artifacts (preserve .gitkeep)
find staging -mindepth 1 -not -name '.gitkeep' \
     \( -type f -o -type d \) -delete 2>/dev/null
```

### Step 4: Restore structural files

Rewrite the five structural files to their blank initial templates.

Use today's date (YYYY-MM-DD) in place of `<today>`.

#### `wiki/index.md`

```markdown
---
type: concept
status: active
confidence: high
created: <today>
updated: <today>
aliases:
  - Index
  - Wiki index
sources: []
tags:
  - meta
  - vault
auto_generated: true
last_full_rebuild: <today>
---

# Wiki Index

Knowledge compiled by Claude Code · LLM Wiki Vault

Navigate by type below. Run `python scripts/rebuild_index.py` to regenerate from frontmatter.

---

_No pages ingested yet._
```

#### `wiki/log.md`

```markdown
---
type: concept
status: active
confidence: high
created: <today>
updated: <today>
aliases:
  - Changelog
  - Ingest log
sources: []
tags:
  - meta
  - vault
---

# Wiki Log

Append-only changelog of all ingestion operations. New entries go at the top.

---

_No ingestions recorded yet._
```

#### `manifests/sources.yml`

```yaml
# Registry of ingested sources
# Format:
# - slug: source-slug
#   title: Source Title
#   type: pdf|article|slides|transcript|repo|web
#   ingested: YYYY-MM-DD
#   path: raw/... or url: https://...
#   pages_created: []
#   pages_updated: []

sources: []
```

#### `manifests/aliases.yml`

```yaml
# Global alias registry — prevents duplicate concept pages
# Format: canonical-slug: [alias1, alias2, ...]

# This file is managed by the Knowledge Compiler Agent.
# Add entries here when a concept has multiple names.
# Example:
# llm-wiki:
#   - karpathy-wiki
#   - ai-maintained-wiki
#   - knowledge-compiler-pattern

# No aliases registered yet.
```

#### `manifests/query-routing.yml`

```yaml
# manifests/query-routing.yml
# Maps topic keywords → canonical page slugs for that topic.
# Maintained during INGEST Step 12 (proposals only — user confirms before adding).
#
# Structure per topic:
#   <keyword>:
#     label: "Human-readable label for this topic cluster"
#     pages:        # concept/entity/pattern pages
#       - slug
#     synthesis:    # synthesis pages for this topic
#       - slug
#     decisions:    # decision/ADR pages for this topic
#       - slug

topics: {}
```

### Step 5: Final report

Print a summary:

```
Wiki reset complete.

Deleted:
  - wiki/sources/      : N pages
  - wiki/entities/     : N pages
  - wiki/concepts/     : N pages
  ... (only directories that had files)
  - staging/           : N artifacts

Reset to blank:
  - wiki/index.md
  - wiki/log.md
  - manifests/sources.yml
  - manifests/aliases.yml
  - manifests/query-routing.yml

Not touched:
  - raw/  (immutable audit layer — intact)
  - wiki/overview.md, wiki/dashboard.md
  - manifests/taxonomy.yml, manifests/batch-ingest.yml

The vault is ready for a fresh ingest cycle.
Next: /wiki-ingest <source> or /wiki-ingest-batch <directory>
```
