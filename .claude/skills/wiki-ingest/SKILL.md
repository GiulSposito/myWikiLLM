---
name: wiki-ingest
description: Ingests a source file or URL into the LLM Wiki vault. Creates/updates source, entity, concept, and related pages following the vault schema.
---

# Wiki Ingest Skill

## Trigger
Use this skill when the user wants to add knowledge from a document, article, paper, slide deck, transcript, repository, or URL into the wiki.

## Protocol

### Step 1: Dedup check
- Check `manifests/sources.yml` to confirm this source has not been ingested before
- If already ingested: warn the user and ask if they want to re-ingest (which updates, not duplicates)

### Step 1b: Identify input type
Before reading, classify the source:

- **Verbatim + summary pair**: Two files from the same session (one UUID-slug verbatim, one clean-name summary) → treat as a single source. Register both paths in frontmatter as `raw_files: [path1, path2]`. Use verbatim for claims/quotes, summary for structure.
- **Structured data catalog / repo snapshot**: Use type `data-dictionary`. Create `wiki/data-dictionary/<domain>/` with `index.md` hub + individual table pages.
- **Audio without full transcript**: Mark `confidence: low`. Note in Bibliographic Metadata that claims are inferred from structured summary.
- **Standard document**: Proceed normally.

### Step 2: Read the source
- **Delegate to `source-reader` subagent** for documents longer than ~3,000 words, or when the source contains dense technical content (schemas, transcripts, slide decks). The subagent returns a structured extraction without interpretation.
- For short, simple documents: read directly.
- Extract: title, author, date, type, URL/path, key claims, entities, concepts, quotes, contradictions, open questions.

### Step 3: Create source page
- Create `wiki/sources/<slug>.md` with full frontmatter
- For verbatim+summary pairs: use `raw_files: [path1, path2]` instead of `raw_file: path`
- slug = lowercase, hyphens, no special chars (e.g. "mckinsey-genai-2025")
- Fill all sections: bibliographic metadata, summary, key claims, entities, concepts, quotes, contradictions, open questions
- Set `confidence` based on source quality and corroboration

### Step 4: Process entities
- For each named entity (company, person, product, tool): check if `wiki/entities/<slug>.md` exists (including `manifests/aliases.yml`)
- If exists: add new facts from this source, append source to `sources:` list, update `updated:` date
- If not: **delegate to `entity-curator` subagent** to create using the entity template
- Add `[[entity-slug]]` wikilink in source page under "Relevant Entities"

### Step 5: Process concepts
- For each concept, framework, method, pattern: check if `wiki/concepts/<slug>.md` exists (including aliases)
- If semantically equivalent concept exists under different name: merge via alias — do NOT create duplicate
- If exists: add new claims under "Source-Backed Claims", update `sources:` list and `updated:` date
- If not: **delegate to `concept-curator` subagent** to create using the concept template
- Add `[[concept-slug]]` wikilink in source page under "Relevant Concepts"

### Step 6: Identify projects, patterns, decisions
If the source describes a specific project, recurring solution, or recorded decision: create or update the relevant page.

**Decision detection**: Scan for markers — "foi decidido", "optamos por", "ficou definido", "decided", "the decision was". For each decision found, add to proposals list (do NOT create automatically).

**Pattern detection**: Scan for recurring approaches that appear in other wiki sources. Add to proposals list.

### Step 7: Contradiction review
**Delegate to `contradiction-reviewer` subagent**, providing:
- The list of claims extracted from this source
- All concept and entity pages touched in Steps 4–6

The reviewer compares claims and flags conflicts. For each conflict:
1. Do NOT silently resolve or pick a winner
2. Set affected page(s) to `status: conflict`
3. Add "Contradictions" section entry on both source and affected page
4. Propose `wiki/questions/<slug>.md` if an open question page is warranted

Record the reviewer's output (number of claims verified, conflicts found) in the Step 12 report.

### Step 8: Add wikilinks throughout
Scan all newly created or updated pages. Ensure every mention of a known wiki page is wrapped in `[[slug]]`. Use `[[slug|Display Text]]` when slug differs from desired display text.

### Step 8b: Check status promotion candidates
Review all concept and entity pages touched in this ingest. For each page with `status: draft`, count entries in its `sources:` list. If count ≥ 2, flag as promotion candidate in the Step 12 report.

### Step 9: Update navigation
- Update `wiki/index.md` with new/updated pages (or run `python scripts/rebuild_index.py`)
- Append to `wiki/log.md`: date, source slug, pages created, pages updated, conflicts, open questions
- Register in `manifests/sources.yml`

### Step 10: Run validation
After writing all files, run:
```bash
python3 scripts/validate_frontmatter.py
python3 scripts/validate_links.py
```
Include any errors found in the Step 12 report.

### Step 11: Run wiki-lint (after batch ingests)
After ingesting 3 or more sources in a session, run `/wiki-lint` and save the report to `outputs/reports/wiki-lint-YYYY-MM-DD.md`.

### Step 12: Report
Return a structured summary:
```
Files created: N
Files updated: N
Conflicts flagged: [list]
Open questions raised: [list]
ADR proposals: [decisions detected, not yet created]
Pattern proposals: [recurring approaches detected]
Status promotion candidates: [pages with 2+ sources still in draft]
Validation errors: [if any]
```

### Step 12b: Post-ingest query ritual
After the report, answer these three closing questions from the current wiki state:

1. **Gap check**: Were any open questions in `wiki/questions/` partially or fully answered by this source? If yes, update the question page.
2. **Synthesis opportunity**: Is there a cross-source insight that could now be synthesized given the new source + existing wiki? If yes, propose synthesis page title and thesis.
3. **Concept-synthesis readiness**: Which concept pages now have 3+ sources and have not yet undergone a concept-synthesis pass? List them.
