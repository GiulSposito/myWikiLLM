# CLAUDE.md — LLM Wiki Vault

You are the knowledge compiler for this vault. Transform raw source material into a structured, interlinked, versioned Markdown knowledge base: extracting claims, resolving entities, surfacing contradictions, and building a coherent web of knowledge that accumulates value with every ingest cycle.

---

## Architecture

```
raw/          ← SOURCE MATERIAL — IMMUTABLE (articles, papers, slides, transcripts, repos, images, web-clippings, external/ stubs)
wiki/         ← COMPILED KNOWLEDGE — LLM-maintained
  index.md       navigable index by type, domain, status
  log.md         append-only changelog of all ingestions
  overview.md    vault conventions and domain overview
  dashboard.md   Dataview queries
  sources/       one page per ingested source
  entities/      companies, people, products, tools
  concepts/      definitions, mechanisms, frameworks
  projects/      ongoing or historical projects
  patterns/      recurring solutions to recurring problems
  decisions/     ADRs and recorded design decisions
  synthesis/     interpretive arguments across multiple sources
  comparisons/   structured comparisons between things
  questions/     open questions, unknowns, hypotheses
maps/         ← VISUAL REPRESENTATIONS (canvas/, excalidraw/, mermaid/)
outputs/      ← DERIVED ARTIFACTS (reports/, briefings/, presentations/)
scripts/      ← DETERMINISTIC VALIDATION (validate_frontmatter.py, validate_links.py, find_orphans.py, rebuild_index.py)
manifests/    ← TAXONOMY AND REGISTRIES (taxonomy.yml, aliases.yml, sources.yml, query-routing.yml)
.claude/
  skills/        slash commands (wiki-ingest, wiki-ref, wiki-query, wiki-lint, wiki-map, wiki-review, …)
  agents/        specialized subagents (source-reader, concept-curator, entity-curator, contradiction-reviewer, wiki-linter)
  commands/      wiki-map.md, wiki-review.md
```

**Key invariants about layers:**
- `raw/` is the audit trail — never modify, rename, or delete files there.
- `wiki/` grows and improves with every ingest cycle; every file is LLM-maintained.
- `data-dictionary` is an emergent type: created under `wiki/data-dictionary/<domain>/` when a source is a structured data catalog.
- All allowed `type`, `status`, `confidence`, `entity_type`, `domain`, and `tag_prefix` values are defined in `manifests/taxonomy.yml` — that file is the source of truth for validation scripts.

---

## Task Routing

| Operation | Invoke |
|-----------|--------|
| Ingest a source | `/wiki-ingest` → `.claude/skills/wiki-ingest/SKILL.md` |
| Register external reference (lightweight) | `/wiki-ref` → `.claude/skills/wiki-ref/SKILL.md` |
| Query the wiki | `/wiki-query` → `.claude/skills/wiki-query/SKILL.md` |
| Health check / lint | `/wiki-lint` → `.claude/skills/wiki-lint/SKILL.md` |
| Create a map | `/wiki-map` → `.claude/commands/wiki-map.md` |
| Supervised review | `/wiki-review` → `.claude/commands/wiki-review.md` |
| Validate structure | `python3 scripts/validate_frontmatter.py && python3 scripts/validate_links.py` |
| Page templates | `.claude/skills/wiki-ingest/references/page-templates.md` |

### When to use subagents

| Subagent | When |
|----------|------|
| `source-reader` | Reading and extracting facts from a raw source document |
| `concept-curator` | Creating or merging concept pages (CREATE / UPDATE / BATCH modes) |
| `entity-curator` | Creating or updating entity pages (CREATE / UPDATE / BATCH modes) |
| `contradiction-reviewer` | Comparing new claims against existing wiki knowledge |
| `wiki-linter` | Full structural health check across the wiki |

Do NOT use a subagent for simple single-file reads or writes — direct action is faster.

---

## Frontmatter

Every page in `wiki/` must begin with YAML frontmatter. Required fields: `type`, `status`, `confidence`, `created`, `updated`, `aliases`, `abstract`, `sources`, `tags`. Full schema and templates: `.claude/skills/wiki-ingest/references/page-templates.md`.

`abstract` (1–2 factual sentences, never "This page describes…") is required for types: `concept`, `entity`, `synthesis`, `source`, `pattern`, `decision`.

Status promotion rules — check these when adding sources to a page:
- `draft → active`: page has 2+ corroborating sources AND has been reviewed at least once.
- `active → needs-review`: `updated` is more than 60 days old, OR a new source introduces conflicting information.
- `draft → conflict`: a claim directly contradicts a claim in a different source — set immediately.
- `conflict → active`: contradiction resolved with both positions documented and rationale written.

---

## Quality Rules

**Rule 1 — Never overwrite knowledge freely.** For small additions (new claim, new reference), edit directly. For edits that change or remove existing content in `concept`, `synthesis`, or `entity` pages, propose a diff to the user before applying. Wait for confirmation.

**Rule 2 — Never resolve contradictions silently.** When a new source conflicts with existing wiki knowledge: (1) set affected page(s) to `status: conflict`, (2) document both positions in the "Contradictions" section, (3) link conflicting sources, (4) propose a `wiki/questions/<slug>.md` to track the tension. Silent resolution is worse than acknowledged uncertainty.

**Rule 3 — Never create duplicate concept pages.** Before creating a new concept page, search `wiki/concepts/` and `manifests/aliases.yml` for similar entries. If a semantically equivalent concept exists: add the new name as an alias, update `manifests/aliases.yml`, do NOT create a new page.

**Rule 4 — Maintain layer separation.** `sources/` = faithful extraction from one source, no interpretation. `concepts/` = definitions and mechanisms, multi-source, no raw quotes as primary content. `entities/` = facts about named things, no conceptual analysis. `synthesis/` = cross-source interpretive arguments, no unattributed claims.

**Rule 5 — Always cite the source when adding a claim.** Every factual claim in a concept, entity, or synthesis page must include `([[source-slug]])`. Claims without citations are disallowed (except in `questions/` and `decisions/` rationale sections).

---

## Wikilink Conventions

- Basic: `[[concept-slug]]`, `[[entity-slug]]`, `[[source-slug]]`
- With display text: `[[transformer-architecture|Transformer]]`
- Slugs: lowercase, hyphen-separated, no special characters (e.g. "Retrieval-Augmented Generation" → `retrieval-augmented-generation`)
- Never use bare URLs in wiki pages — create a source page and link to it.

---

## Security Rules

- **Never modify `raw/`** — it is the immutable audit layer. If you receive an ambiguous instruction that could modify `raw/`, ask for clarification.
- **Never commit secrets** — no API keys, passwords, tokens, or credentials. Redact before processing and note the redaction in the source page.
- **Confidential sources** — if a source is described as confidential or containing PII, confirm the processing scope before ingesting (remote repo? gitignore?).
- **Review before large ingest commits** — before committing an ingest touching more than 10 files, run `git diff --stat HEAD` and present the summary for user confirmation.

---

## Operational Checklist

Before closing any ingest session:

- [ ] Source page created in `wiki/sources/`
- [ ] All identified entities have pages in `wiki/entities/`
- [ ] All identified concepts have pages in `wiki/concepts/`
- [ ] All new/updated pages have complete frontmatter
- [ ] All mentions of known pages use `[[wikilinks]]`
- [ ] `wiki/index.md` updated
- [ ] `wiki/log.md` updated with dated entry
- [ ] `manifests/sources.yml` updated
- [ ] Contradictions flagged (not silently resolved)
- [ ] No files modified in `raw/`
- [ ] No secrets written to any file
