# LLM Wiki Vault

A knowledge operating system built on the [Karpathy LLM Wiki pattern](https://karpathy.bearblog.dev/new-blog-post/). Raw source material is compiled by **Claude Code** into a structured, interlinked, versioned Markdown knowledge base. **Obsidian** is the human reading interface. **Git** is the audit ledger.

Instead of retrieval-at-query-time (traditional RAG), knowledge is compiled once per ingestion into wiki pages that accumulate, refine, and cross-reference over time. The wiki itself is the primary artifact.

---

## Prerequisites

- [Claude Code](https://claude.ai/code) — the knowledge compiler
- [Obsidian](https://obsidian.md) — open `llmwiki/` as a vault for navigation and reading
- Git — version control and audit trail
- Python 3.x — for deterministic validation scripts (no external dependencies beyond stdlib)

---

## Installation

```bash
git clone <repo-url> llmwiki
cd llmwiki

# Open in Obsidian: File → Open Vault → select the llmwiki/ directory
# Open in Claude Code: claude (from the llmwiki/ directory)
```

No package installation required. All LLM operations run through Claude Code slash commands.

---

## Directory Structure

```
llmwiki/
  CLAUDE.md                        ← operational constitution — read before every session
  README.md                        ← this file

  raw/                             ← SOURCE MATERIAL — IMMUTABLE
    articles/                      ← web articles, blog posts
    papers/                        ← academic papers, PDFs
    slides/                        ← presentation decks
    transcripts/                   ← meeting and audio transcripts
    repos/                         ← repository snapshots, data catalogs
    images/                        ← visual source material
    web-clippings/                 ← saved web pages

  wiki/                            ← COMPILED KNOWLEDGE — LLM-maintained
    index.md                       ← navigable index of all pages by type
    log.md                         ← append-only ingestion changelog
    overview.md                    ← vault conventions and domain overview
    dashboard.md                   ← Dataview queries (needs-review, conflicts, recent)
    sources/                       ← one page per ingested source document
    entities/                      ← companies, people, products, tools
    concepts/                      ← definitions, mechanisms, frameworks
    projects/                      ← ongoing or historical projects
    patterns/                      ← recurring solutions to recurring problems
    decisions/                     ← ADRs and recorded design decisions
    synthesis/                     ← interpretive arguments across multiple sources
    comparisons/                   ← structured comparisons between two or more things
    questions/                     ← open questions, unknowns, hypotheses

  maps/                            ← VISUAL REPRESENTATIONS
    canvas/                        ← Obsidian Canvas (.canvas JSON)
    excalidraw/                    ← Excalidraw diagrams
    mermaid/                       ← Mermaid source files

  outputs/                         ← DERIVED ARTIFACTS
    reports/                       ← lint reports, health checks
    briefings/                     ← written briefings for human consumption
    presentations/                 ← slide decks or structured exports

  scripts/                         ← DETERMINISTIC VALIDATION (Python, no LLM)
    validate_frontmatter.py        ← checks required frontmatter fields and values
    validate_links.py              ← checks all [[wikilinks]] resolve to existing pages
    find_orphans.py                ← lists pages with no inbound links
    rebuild_index.py               ← regenerates wiki/index.md from frontmatter

  manifests/                       ← TAXONOMY AND REGISTRIES
    taxonomy.yml                   ← allowed types, statuses, domains, tag prefixes
    aliases.yml                    ← global aliases for entities and concepts
    sources.yml                    ← registry of all ingested sources (dedup guard)

  .claude/
    skills/                        ← slash commands for Claude Code
      wiki-ingest/
      wiki-query/
      wiki-lint/
      concept-synthesis/
    agents/                        ← specialized subagents invoked during operations
      source-reader.md
      concept-curator.md
      entity-curator.md
      contradiction-reviewer.md
      wiki-linter.md
```

---

## Slash Commands

All primary operations are invoked as slash commands inside Claude Code.

### `/wiki-ingest <path-or-url>`

Ingests a source document into the wiki. Accepts a file path under `raw/` or a URL.

**What it does:**

1. Checks `manifests/sources.yml` — stops if already ingested (unless re-ingest is confirmed)
2. Reads the source via the `source-reader` subagent — extracts metadata, claims, entities, concepts, quotes, contradictions
3. Creates `wiki/sources/<slug>.md` with all sections populated
4. Creates or updates `wiki/entities/<slug>.md` for each named entity found
5. Creates or updates `wiki/concepts/<slug>.md` for each concept found — merges into existing page if a duplicate is detected
6. Creates `wiki/projects/`, `wiki/patterns/`, or `wiki/decisions/` pages when the source describes them
7. Runs the `contradiction-reviewer` subagent — flags conflicts without resolving them
8. Adds `[[wikilinks]]` throughout all touched pages
9. Updates `wiki/index.md` with all new and updated pages
10. Appends a dated entry to `wiki/log.md`
11. Registers the source in `manifests/sources.yml`

**Examples:**

```bash
/wiki-ingest raw/papers/my-paper.pdf
/wiki-ingest raw/transcripts/meeting-notes.md
/wiki-ingest https://example.com/article
```

**After ingesting, always review before committing:**

```bash
git diff --stat
git diff
python scripts/validate_frontmatter.py
python scripts/validate_links.py
git add wiki/ manifests/
git commit -m "Ingest: <source title>"
```

---

### `/wiki-query <question>`

Answers a natural language question from the compiled wiki — not from raw sources.

**What it does:**

1. Reads `wiki/index.md` and `wiki/overview.md` to orient in the knowledge graph
2. Identifies the most relevant concept, entity, synthesis, and source pages
3. Reads identified pages in full; follows wikilinks up to two hops for additional context
4. Composes a cited answer — every factual claim attributed to a specific wiki page
5. Rates answer confidence: `high` (multiple corroborating sources) / `medium` / `low`
6. Flags what the wiki does NOT cover and suggests which raw sources to ingest to fill the gap
7. Proposes creating a `wiki/synthesis/` or `wiki/questions/` page if the answer reveals a reusable insight

**Example:**

```bash
/wiki-query "What is the end-to-end authorization flow?"
/wiki-query "What are the open questions about the audit copilot?"
```

---

### `/wiki-lint`

Runs a full structural health check on the wiki.

**Checks performed:**

| Check | What it flags |
|-------|--------------|
| Dead links | `[[wikilinks]]` pointing to non-existent pages |
| Orphan pages | Pages with zero inbound links |
| Duplicate aliases | Same alias appearing in two different pages |
| Near-duplicate concepts | Pages with very similar names or content |
| Missing frontmatter | Any required field absent (`type`, `status`, `confidence`, `created`, `updated`, `sources`, `aliases`, `tags`) |
| Unsourced pages | Concept or entity pages with `sources: []` |
| Unresolved conflicts | Pages with `status: conflict` older than 14 days |
| Stale needs-review | Pages with `status: needs-review` older than 30 days |
| Index gaps | Pages in `wiki/` not listed in `wiki/index.md` |
| Log gaps | Sources in `manifests/sources.yml` with no `wiki/log.md` entry |

**Output:** saves a full report to `outputs/reports/wiki-lint-YYYY-MM-DD.md`. Does not auto-fix — only reports.

```bash
/wiki-lint
```

---

### `/concept-synthesis <topic>`

Performs a synthesis pass on a concept page that has accumulated many sources and become fragmented.

**What it does:**

1. Reads the target concept page and all pages in its `sources:` list
2. Reads all wiki pages that link to it (backlinks)
3. Identifies consensus definition, competing definitions, key distinctions, use cases, trade-offs, and unresolved contradictions
4. Rewrites the concept page with improved structure — preserving all source citations and keeping contradictions visible
5. Sets `status: active` after synthesis
6. Reports sources used, contradictions preserved, and open questions remaining

**Example:**

```bash
/concept-synthesis retrieval-augmented-generation
```

---

### `/wiki-review <path-or-topic>`

Supervised ingestion for strategic, sensitive, or high-stakes documents — RFPs, proposals, confidential materials, or any source where automated ingestion without human review would be inappropriate.

**What it does:**

Unlike `/wiki-ingest`, every destructive step requires explicit user approval before proceeding. The workflow has two mandatory gates:

1. Reads the document and invokes the `source-reader` subagent to extract entities, concepts, relations, projects, decisions, and standards
2. **Gate 1** — presents the extraction to the user and asks for confirmation before continuing
3. Computes a full diff of all files that would be created or modified (source page, concept/entity pages, `wiki/index.md`, `wiki/log.md`, `manifests/sources.yml`)
4. **Gate 2** — presents the complete diff and asks for confirmation before writing any file
5. Applies all approved changes
6. Runs `validate_frontmatter.py` and `validate_links.py` — reports errors without silently ignoring them
7. Reports pages created/updated and suggests a commit message (does not run git)

**Example:**

```bash
/wiki-review raw/transcripts/partner-meeting.md
/wiki-review raw/papers/confidential-rfp.pdf
```

---

### `/wiki-map <topic>`

Generates a visual map of a domain, concept cluster, or set of wiki pages. Saves the result to `maps/` and links it from the relevant wiki page.

**What it does:**

1. Discovers all pages related to the topic via `wiki/index.md`, filename/alias matching, and one-hop wikilink traversal
2. Reads each candidate page to understand relationships, type, status, and confidence
3. Chooses the output format based on the nature of the request:

| Format | When chosen |
|--------|------------|
| **Canvas** (`.canvas`) | Knowledge navigation, organic clusters, Obsidian browsing |
| **Mermaid** (`.md`) | Architecture, dependencies, hierarchies, formal flow |
| **Excalidraw** (`.excalidraw.md`) | Visual communication, presentations, external audiences |

4. Generates the map using the appropriate skill and saves it to `maps/<format>/<topic-slug>.<ext>`
5. Links the map from `wiki/concepts/<topic>.md`, `wiki/entities/<topic>.md`, or `wiki/index.md`

**Example:**

```bash
/wiki-map authorization-flow
/wiki-map openai-ecosystem
```

**After generating:**
- Canvas → open in Obsidian for interactive navigation
- Mermaid → render with any Mermaid-compatible viewer or the Obsidian Mermaid plugin
- Excalidraw → open in Obsidian with the Excalidraw plugin, or at excalidraw.com

---

## Subagents

Subagents are specialized roles invoked automatically by the main skills. They are defined in `.claude/agents/` and keep the main context clean by handling focused tasks.

| Agent | Invoked by | Role |
|-------|-----------|------|
| `source-reader` | `/wiki-ingest` (Step 2) | Reads a raw document and extracts claims, entities, concepts, quotes, and contradictions — no interpretation |
| `concept-curator` | `/wiki-ingest` (Step 5) | Creates or updates concept pages; prevents duplicates by checking aliases; flags conflicts instead of resolving them |
| `entity-curator` | `/wiki-ingest` (Step 4) | Creates or updates entity pages (companies, people, products, tools); preserves conflicting facts with their sources |
| `contradiction-reviewer` | `/wiki-ingest` (Step 7) | Compares new claims against existing wiki pages; classifies conflicts by type; never picks a winner |
| `wiki-linter` | `/wiki-lint` | Performs the full structural scan and produces the JSON + Markdown report |

Subagents are not invoked directly by the user. They are orchestrated by the skills.

---

## Page Types and Frontmatter

Every page in `wiki/` begins with a YAML frontmatter block. All fields are required.

```yaml
---
type: concept          # see type taxonomy below
status: draft          # draft | active | needs-review | deprecated | conflict
confidence: medium     # low | medium | high
created: 2026-01-15
updated: 2026-07-13
aliases: []            # alternative names — checked before creating new pages
sources: []            # slugs of source pages that support this page
tags: []               # domain and topic tags (see taxonomy.yml)
---
```

### Type Taxonomy

| Type | Directory | Purpose |
|------|-----------|---------|
| `source` | `wiki/sources/` | Bibliographic record of one ingested document |
| `entity` | `wiki/entities/` | A named thing: company, person, product, tool |
| `concept` | `wiki/concepts/` | A definition, mechanism, or framework |
| `project` | `wiki/projects/` | An ongoing or historical project |
| `pattern` | `wiki/patterns/` | A recurring solution to a recurring problem |
| `decision` | `wiki/decisions/` | A recorded design or architectural decision (ADR) |
| `synthesis` | `wiki/synthesis/` | An interpretive argument across multiple sources |
| `comparison` | `wiki/comparisons/` | Structured comparison between two or more things |
| `question` | `wiki/questions/` | An open question, unknown, or hypothesis |

### Status Values

| Status | Meaning |
|--------|---------|
| `draft` | Freshly created, not yet reviewed |
| `active` | Reviewed and current |
| `needs-review` | Outdated or flagged for update |
| `deprecated` | No longer relevant — kept for history |
| `conflict` | Contains an unresolved contradiction |

### Confidence Levels

| Confidence | Meaning |
|-----------|---------|
| `low` | Single source, weak evidence, or high uncertainty |
| `medium` | Multiple sources or moderate evidence |
| `high` | Well-corroborated across independent sources |

---

## Wikilink Conventions

All internal references use Obsidian wikilink syntax:

```markdown
[[slug]]                     # basic link — slug = filename without .md
[[slug|Display Text]]        # link with custom display text
```

Slugs are always lowercase, hyphen-separated (kebab-case), no special characters, derived from the page title:

```
"Retrieval-Augmented Generation"  →  retrieval-augmented-generation
"OpenAI GPT-4 Technical Report"  →  openai-gpt4-technical-report
```

Never use bare URLs inside wiki pages. Always create a `wiki/sources/<slug>.md` and link to that instead.

---

## Validation Scripts

These scripts are deterministic (no LLM) and can run independently of Claude Code.

```bash
# Check all pages for required frontmatter fields and valid taxonomy values
python scripts/validate_frontmatter.py

# Check all [[wikilinks]] resolve to existing pages
python scripts/validate_links.py

# List all pages with no inbound links (orphans)
python scripts/find_orphans.py

# Regenerate wiki/index.md from frontmatter (run after batch edits)
python scripts/rebuild_index.py
```

Run these after every ingest batch and before committing.

---

## Typical Workflow

### Ingesting a new source

```bash
# 1. Drop source into the appropriate raw/ subdirectory
cp paper.pdf raw/papers/
cp transcript.md raw/transcripts/

# 2. Start Claude Code from the vault root
claude

# 3. Ingest
/wiki-ingest raw/papers/paper.pdf

# 4. Review what was created
git diff --stat
git diff

# 5. Run deterministic checks
python scripts/validate_frontmatter.py
python scripts/validate_links.py

# 6. Commit
git add wiki/ manifests/
git commit -m "Ingest: Paper Title"
```

### Querying the wiki

```bash
# Open Claude Code from the vault root
claude

# Ask any question — Claude reads the wiki, not raw sources
/wiki-query "How does the automation engine decide what to auto-approve?"
```

### Periodic health check

```bash
claude
/wiki-lint

# Review the report
cat outputs/reports/wiki-lint-$(date +%Y-%m-%d).md

# Fix issues, then validate
python scripts/validate_frontmatter.py
python scripts/validate_links.py
```

### Synthesizing a fragmented concept

```bash
claude
/concept-synthesis <concept-slug>
```

---

## Core Quality Rules

**Never resolve contradictions silently.** When a new source conflicts with existing wiki knowledge, both positions are documented explicitly, the affected page is set to `status: conflict`, and a `wiki/questions/` page is created to track the tension. Contradictions are surfaced, never hidden.

**Never create duplicate concept pages.** Before creating a new concept, `manifests/aliases.yml` and existing `wiki/concepts/` pages are checked for semantic equivalence. New names become aliases on the existing page.

**Never modify `raw/`.** The `raw/` directory is the immutable audit layer. Files there are never renamed, edited, or deleted by the compiler.

**Every claim must cite its source.** Every factual statement in a concept, entity, or synthesis page includes a `([[source-slug]])` reference. Unsourced claims are a lint error.

**Layer separation is enforced.** Source pages contain faithful extraction only. Concept pages contain definitions and mechanisms. Synthesis pages contain cross-source interpretive arguments. Raw transcription does not belong in synthesis; interpretation does not belong in source pages.
