# Plan: Multi-format Conversion to Markdown

## Context

The existing `scripts/convert_pdf_to_md.py` handles PDF → Markdown via `pymupdf4llm`. This plan extends the same capability to other document formats that naturally appear in knowledge-base workflows, using a unified script that can be called the same way by all three ingest skills.

---

## Format selection rationale

The repo's purpose is structured knowledge extraction from heterogeneous source material. Formats are included only if they plausibly carry structured knowledge (not binary data or media containers) and have a reliable conversion path already available in the environment.

| Format | Extension | Why include | Converter |
|--------|-----------|-------------|-----------|
| Word document | `.docx` | Most common office document format; reports, specs, meeting minutes | pandoc (installed) |
| OpenDocument text | `.odt` | LibreOffice / Google Docs export | pandoc (installed) |
| Rich Text | `.rtf` | Legacy Word, Apple Pages export | pandoc (installed) |
| EPUB | `.epub` | Books, long-form research, O'Reilly, etc. | pandoc (installed) |
| HTML (local) | `.html`, `.htm` | Web-clippings saved locally, scraped pages | pandoc (installed) |
| reStructuredText | `.rst` | Python docs, Sphinx documentation | pandoc (installed) |
| Org-mode | `.org` | Emacs knowledge bases, roam-style notes | pandoc (installed) |
| LaTeX | `.tex` | Academic papers (when PDF is unavailable) | pandoc (installed) |

**Excluded (and why):**
- `.pptx` / `.ppt` — python-pptx not installed; pandoc support is lossy (speaker notes lost, slide structure flattened). Worth adding separately if needed.
- `.xlsx` / `.xls` / `.csv` — tabular data, better handled by `data-dictionary` ingest type, not document conversion.
- `.docm`, `.odf` — edge cases; covered by pandoc's docx/odt readers already.
- Images (`.png`, `.jpg`) — require OCR, separate concern.

---

## Design decisions

### 1. One unified script instead of per-format scripts

**Decision: extend `scripts/convert_pdf_to_md.py` into a general `scripts/convert_to_md.py`.**

Reasons:
- The skill files reference one command — one entry point is simpler to maintain.
- PDF keeps its specialized path (`pymupdf4llm`) inside the same script; all other formats route through pandoc.
- CLI stays identical: `python3 scripts/convert_to_md.py <file_or_dir>` — only behavior changes based on extension.

The old `convert_pdf_to_md.py` becomes a thin wrapper that calls `convert_to_md.py` for backwards compatibility (one-line delegation), or is kept as-is and the skill files are updated to reference the new script.

**Chosen approach: rename/replace `convert_pdf_to_md.py` with `convert_to_md.py`; update skill files accordingly.**

### 2. Pandoc for everything except PDF

Pandoc is already installed (v2.16.2), handles all the target formats, and produces clean GFM Markdown. No additional Python dependencies needed.

Pandoc flags used:
- `--from <format> --to gfm` — GitHub-Flavored Markdown output
- `--wrap=none` — no line-wrapping (important for LLM consumption)
- `--extract-media=<dir>` — for EPUB/HTML with embedded images, extract to a subdirectory alongside the `.md` (images are referenced but not ingested)
- `--standalone` — not used (we want body content only, not a full HTML document)

### 3. `source_original` field (replaces `source_pdf`)

The source page frontmatter currently uses `source_pdf` for PDF sources. With multi-format support, rename this to `source_original` across the board. It is consistent and format-agnostic.

**Impact:** update the three skill files to use `source_original` instead of `source_pdf`. The PDF-specific field name was only added in the previous plan and has not been used in any real ingest yet.

### 4. Idempotency, `--force`, skip logic

Same as the existing PDF script:
- If `<stem>.md` already exists alongside the source file → skip (print SKIP).
- `--force` overwrites.
- `--output / -o` directs output to a different directory.

### 5. Dependency checks

- `pymupdf4llm`: checked lazily (only when a PDF is encountered).
- `pandoc`: checked once at startup if any non-PDF format is present. Clear error message with install hint.

---

## Changes

### 1. Replace `scripts/convert_pdf_to_md.py` → `scripts/convert_to_md.py`

New script structure:

```
convert_to_md.py
  main()
    parse args (same CLI as today)
    collect files: all supported extensions (not just .pdf)
    for each file:
      if .pdf → convert_pdf(path, output_dir, verbose)        # pymupdf4llm
      else    → convert_via_pandoc(path, output_dir, verbose) # pandoc subprocess
  convert_pdf(path, output_dir, verbose)   # extracted from current script, unchanged
  convert_via_pandoc(path, output_dir, verbose)
    map extension → pandoc --from value
    run: pandoc --from <fmt> --to gfm --wrap=none [-o <md_path>] [--extract-media=<dir>] <path>
    write output to <md_path>
  _check_pandoc()   # subprocess.run(["pandoc", "--version"], capture_output=True)
  _require_pymupdf4llm()   # unchanged
```

Supported extension → pandoc format map:
```python
PANDOC_FORMATS = {
    ".docx": "docx",
    ".odt":  "odt",
    ".rtf":  "rtf",
    ".epub": "epub",
    ".html": "html",
    ".htm":  "html",
    ".rst":  "rst",
    ".org":  "org",
    ".tex":  "latex",
}
```

The old `convert_pdf_to_md.py` is **deleted** (or kept as a one-line deprecation shim if backwards compatibility matters — to be decided at implementation time; since the file has no external callers yet, deletion is cleaner).

### 2. Update skill files (3 files)

In each skill file, replace:
- `python3 scripts/convert_pdf_to_md.py` → `python3 scripts/convert_to_md.py`
- `source_pdf:` field references → `source_original:`

Files to update:
- `.claude/skills/wiki-ingest/SKILL.md` (Step 1b)
- `.claude/skills/wiki-ref/SKILL.md` (Step 2)
- `.claude/skills/wiki-ingest-batch/SKILL.md` (Step 0.5)

In each, also expand the format description from "PDF" to the full list, e.g.:

> **Rich document source** (`.pdf`, `.docx`, `.odt`, `.rtf`, `.epub`, `.html`, `.rst`, `.org`, `.tex`):

### 3. Update `scripts/batch/scanner.py` — NO CHANGE

The scanner only processes the resulting `.md` files. No change needed.

---

## What is NOT changed

- Dedup logic, sha256, slug generation — all operate on the `.md` output, unchanged.
- `raw/` immutability — the script only creates new files, never modifies existing ones.
- `manifests/sources.yml` format — only the field name changes (`source_pdf` → `source_original`).

---

## Open question (not blocking)

`.pptx` (PowerPoint) is a common knowledge source. Pandoc reads pptx but output is lossy (no speaker notes, slide metadata lost). A dedicated `pptx_to_md.py` using `python-pptx` could produce a richer result (one section per slide, speaker notes appended). Deferred to a separate plan.
