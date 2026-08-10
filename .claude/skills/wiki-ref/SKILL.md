---
name: wiki-ref
description: Indexes an external reference (URL or large document) as a lightweight source card in the wiki. Does NOT extract claims, create entity/concept pages, or run contradiction review — only creates a bibliographic stub and source page.
---

# Wiki Reference Skill

## Trigger
Use this skill when the user wants to register a reference to an external source (documentation, technical manual, large report, external repo, etc.) without importing its full content into the wiki.

**When to use `/wiki-ref` instead of `/wiki-ingest`:**
- The source is a large technical manual, official docs, or reference repository where extracting every claim would bloat the wiki
- The user wants to "point to" a source so it can be linked from concept/entity pages later
- The source covers many topics loosely — it's more useful as a pointer than as an ingest

**When to use `/wiki-ingest` instead:**
- The source is a focused paper, article, transcript, or talk where the claims directly inform wiki knowledge
- The user wants entity and concept pages created or updated from the source

---

## Protocol

### Step 1: Dedup check
- Check `manifests/sources.yml` for an existing entry matching the URL or file path.
- If already registered: inform the user and stop (or ask if they want to update the stub).
- If a `sha256:` is present on the existing entry, compare hashes; warn if the source has changed.

### Step 2: Obtain source metadata
Classify the input:

**URL source:**
- Use WebFetch to retrieve the page. Read the title, description meta tag, and top-level heading structure (H1–H3) to infer scope.
- Do NOT download the full document. Retrieve only enough for a 3–5 paragraph summary.
- Record title, author/publisher, date (if visible), and canonical URL.

**Local file — rich document** (`.pdf`, `.docx`, `.odt`, `.rtf`, `.epub`, `.html`, `.htm`, `.rst`, `.org`, `.tex`):
- Convert to Markdown first:
  ```bash
  python3 scripts/convert_to_md.py <path> -v
  ```
  - Idempotent: skips conversion if the companion `.md` already exists. Use `--force` only if the source was updated.
  - If conversion fails, stop and report the error to the user.
- Continue with the resulting `<stem>.md` for all subsequent steps (reading, TOC extraction, sha256, slug).
- Record `source_original: <original_file_path>` in the stub (Step 3) and source page frontmatter (Step 4).
- In the stub body and source page, add a note: "Converted from `<format>`: `<original_file_path>`"

**Local file — large (≥ 800 lines or unknown length):**
- Read the first 150 lines to check for a Table of Contents or document header.
- If a TOC exists, read it fully to extract topic structure.
- Do NOT read the entire document. Summary is based on TOC + header.
- Compute SHA256:
  ```bash
  python3 -c "import hashlib; print(hashlib.sha256(open('<path>','rb').read()).hexdigest())"
  ```

**Local file — short (< 800 lines):**
- Read the complete file.
- Still apply the reference protocol: do NOT create entity/concept pages.
- Compute SHA256 as above.

### Step 3: Create stub in `raw/external/<slug>.md`
This is the immutable audit trail for the reference. Once created, do NOT modify it.

Slug rules: lowercase, hyphens, no special chars, accents stripped. For URL sources, derive from the domain + page title (e.g., `langchain-docs-rag-overview`). Use:
```bash
python3 -c "from scripts.batch.normalizer import slugify; print(slugify('Title Here'))"
```

Stub format:
```markdown
# <Title> — External Reference Stub

- **URL / Path**: <url or relative path from vault root>
- **Accessed**: YYYY-MM-DD
- **Type**: url | pdf | manual | repo | doc
- **Summary**: <2–3 sentences describing what the source covers and who it is for>
```

### Step 4: Create source page in `wiki/sources/<slug>.md`
Use the **source (reference mode)** template from `.claude/skills/wiki-ingest/references/page-templates.md`.

Additional frontmatter fields:
```yaml
ingest_depth: reference
external_url: "<url if applicable>"
```

Fill all sections:
- **Summary**: 2–4 paragraphs on scope, purpose, and audience
- **Key Topics**: bullet list of themes (not verifiable claims)
- **Mentioned Concepts**: wikilinks to existing pages only; plain text for unknown concepts
- **Mentioned Entities**: wikilinks to existing pages only; plain text for unknown entities
- **Access Notes**: URL, relevant sections, prerequisites for reading

### Step 5: Identify wiki links (WITHOUT creating pages)
Scan the extracted topics for concepts and entities that may already have wiki pages.

For each mention:
- **Existing wiki page**: wrap in `[[slug]]` in the source page
- **No wiki page yet**: list in plain text under the section, mark as "link candidate" in the Step 7 report
- Do NOT create any new concept or entity pages — that is the job of `/wiki-ingest`

### Step 6: Update navigation
- `wiki/index.md`: add entry under Sources with `[reference]` marker
- `wiki/log.md`: append entry:
  ```markdown
  ## YYYY-MM-DD — Reference: <Source Title>
  - Source: [[slug]] `[reference mode]`
  - Raw stub: `raw/external/<slug>.md`
  - No pages created or updated (reference-only ingest)
  ```
- `manifests/sources.yml`: register with exactly this format:
  ```yaml
  - slug: <slug>
    title: <title>
    type: url | pdf | manual | repo | doc
    ingested: YYYY-MM-DD
    raw_path: raw/external/<slug>.md
    sha256: <64-char hex>   # hash of raw stub file (for URL sources); hash of local file (for file sources)
    external_url: <url if applicable>
    ingest_depth: reference
    pages_created: [wiki/sources/<slug>]
    pages_updated: []
  ```

### Step 7: Report
```
Mode: reference (lightweight)
Source page: wiki/sources/<slug>.md
Raw stub: raw/external/<slug>.md
Mentioned concepts (linked to existing wiki pages): [list or "none"]
Mentioned entities (linked to existing wiki pages): [list or "none"]
Link candidates (mentioned but no wiki page exists yet):
  - <name> — consider /wiki-ingest or /wiki-ref if dedicated docs exist
```

No validation run is needed after a reference ingest (no concept/entity mutations to validate).
