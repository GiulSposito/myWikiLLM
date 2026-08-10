# Plan: PDF Support for Ingest Skills

## Context

Currently, `wiki-ingest`, `wiki-ref`, and `wiki-ingest-batch` only handle Markdown/text sources. PDF files are invisible to the batch scanner (which only matches `.md`, `.txt`, `.vtt`, `.srt`) and unreadable by the LLM directly.

The reference script at `~/Projects/hapvida/acm/scripts/convert_pdf_to_md.py` uses `pymupdf4llm` to convert PDFs to Markdown, preserving tables, headings, and layout. It is adequate and will be adapted (not copied verbatim).

---

## Design Decisions

### 1. Where does the converted `.md` live?

**Decision: same directory as the PDF** (`raw/papers/foo.pdf` → `raw/papers/foo.md`).

- Co-location makes the relationship obvious.
- The `raw/` immutability rule forbids modifying/deleting existing files — creating a derived `.md` alongside a PDF is not a violation.
- The converted `.md` is deterministic and reproducible from the PDF.
- The batch scanner picks it up automatically with no code changes.

### 2. What does the source page reference?

**Decision: `raw_path` → converted `.md`; add `source_pdf` field for the original.**

- The `.md` is what was actually read and extracted from — it is the operative source.
- The sha256 is of the `.md` file (consistent with scanner behavior).
- `source_pdf` in frontmatter and `sources.yml` preserves the audit trail to the original PDF.
- Source page body includes a note: "Converted from PDF: `raw/.../foo.pdf`".

This avoids any scanner changes: dedup and change-detection work against the `.md` path/hash, as they do for all other sources.

### 3. When does conversion happen — per skill?

| Skill | Where | When |
|-------|-------|------|
| `wiki-ingest` | Step 1b (identify input type) | Detect `.pdf` extension → convert → proceed with `.md` |
| `wiki-ref` | Step 2 (obtain metadata) | Detect `.pdf` → convert → read resulting `.md` |
| `wiki-ingest-batch` | New Step 0.5 (PDF pre-processing) | Before scan: convert all PDFs in target directory |

### 4. Idempotency

The conversion script skips a PDF if an `.md` with the same stem already exists in the same directory (unless `--force` is passed). This makes re-runs safe and fast.

---

## Changes

### 1. New script: `scripts/convert_pdf_to_md.py`

Adapted from the reference script. Key changes:
- Add `--force` flag to overwrite existing `.md`.
- Add `--output-dir` / `-o` flag (default: same directory as PDF).
- Skip existing `.md` by default (idempotent).
- Add a dependency check with a clear error message if `pymupdf4llm` is not installed.
- Same conversion parameters as reference: `table_strategy="lines_strict"`, `ignore_code=False`.
- Print a summary of how many were converted, skipped, and failed.

### 2. Update `wiki-ingest/SKILL.md` — Step 1b

Add PDF detection clause to the existing "identify input type" step:

```
**PDF source**: If the source path ends in `.pdf`:
1. Convert it: `python3 scripts/convert_pdf_to_md.py <path>`
   - If conversion fails, stop and report the error to the user.
2. Proceed with the resulting `<stem>.md` for all extraction and reading steps.
3. In the source page frontmatter, add: `source_pdf: <original_pdf_path>`
4. In the source page body (Bibliographic Metadata), note: "Converted from PDF: `<original_pdf_path>`"
5. In `manifests/sources.yml`, add: `source_pdf: <original_pdf_path>`
```

### 3. Update `wiki-ref/SKILL.md` — Step 2

Add at the top of "Local file — large" and "Local file — short" branches:

```
**PDF pre-processing**: If the file is a `.pdf`, convert it first:
  python3 scripts/convert_pdf_to_md.py <path>
Then proceed with the resulting `.md` file. Record `source_pdf: <original_path>` in the stub and source page.
```

### 4. Update `wiki-ingest-batch/SKILL.md` — new Step 0.5

Insert between Step 0 (model config) and Step 1 (scan):

```
### Step 0.5: PDF pre-processing

Before scanning, check for PDFs in the target directory:

```bash
python3 scripts/convert_pdf_to_md.py <directory> -v
```

This converts all `.pdf` files that do not yet have a companion `.md` (idempotent).
The scanner (Step 1) will then discover the `.md` files as normal.

If any conversions fail, report the errors to the user and ask whether to continue
without the failed files or abort the batch.
```

---

## What is NOT changed

- `scripts/batch/scanner.py` — no changes. The scanner continues to work with `.md` files only. PDFs are invisible to it until converted.
- `raw/` files — never modified. The converted `.md` is a new file added alongside the PDF.
- Dedup logic — unchanged. Dedup keys off the `.md` path and sha256, same as any other source.

---

## Dependency

`pymupdf4llm` must be installed in the Python environment. The script emits a clear error if missing:
```
Error: pymupdf4llm is not installed. Run: pip install pymupdf4llm
```
