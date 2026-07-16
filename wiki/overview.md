---
type: concept
status: active
confidence: high
created: 2026-07-13
updated: 2026-07-13
aliases: [About this vault, Vault overview]
sources: []
tags: [meta, vault]
---

# LLM Wiki Vault

## What this vault is

This vault follows the Karpathy LLM Wiki pattern: instead of traditional RAG (where raw documents are retrieved and fed to a model at query time), raw sources are compiled into a structured, interlinked Markdown wiki. A Knowledge Compiler Agent reads source material and synthesizes it into wiki pages — concepts, entities, patterns, decisions, and more.

The result is a living knowledge base that grows incrementally with each ingestion. Knowledge compounds over time: new sources refine, extend, or challenge existing pages rather than being siloed as standalone documents. The wiki becomes the primary knowledge artifact, not the raw files.

## How it works

The ingestion cycle is:

```
raw/  →  ingest  →  wiki/  →  query
```

1. **raw/** — Drop source files here (PDFs, articles, transcripts, slides, web clippings, repos).
2. **ingest** — Run `/wiki-ingest` to trigger the Knowledge Compiler Agent pipeline. Source-Reader, Concept-Curator, and Entity-Curator agents process the material and write or update wiki pages.
3. **wiki/** — Structured Markdown pages organized by type (sources, concepts, entities, projects, patterns, decisions, synthesis, comparisons, questions).
4. **query** — Run `/wiki-query` to ask questions. The agent searches the wiki and synthesizes an answer with citations.

## Key principles

- **Knowledge compounds** — New ingestions update existing pages; they do not create duplicate entries. Every new fact integrates into the existing graph.
- **Do not overwrite silently** — When a new source conflicts with existing content, pages are flagged `status: conflict` and a note is added explaining the discrepancy. Conflicts are surfaced, not hidden.
- **Separate source from interpretation** — Source pages (`wiki/sources/`) record what a document says. Concept and synthesis pages record what it means. The distinction is maintained explicitly.
- **Always cite** — Every claim in a wiki page must trace back to a source page via a wiki link. Unsourced assertions are marked or avoided.

## Domains covered

_No domains ingested yet. This section will be populated as sources are added._

## How to use

Main commands available via Claude Code slash commands:

- `/wiki-ingest` — Ingest a new source file or URL into the wiki.
- `/wiki-query` — Query the wiki with a natural language question.
- `/wiki-lint` — Run linting checks on wiki pages (frontmatter, links, orphans).
- `/wiki-map` — Generate a map of content, showing relationships between pages.

## Related

- [[index]]
- [[log]]
- [[dashboard]]
