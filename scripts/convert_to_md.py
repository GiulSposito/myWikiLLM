#!/usr/bin/env python3
"""
Converte documentos para Markdown preservando estrutura e formatação.

Formatos suportados:
  .pdf              → pymupdf4llm  (títulos, tabelas, colunas)
  .docx .odt .rtf   → pandoc       (Word, LibreOffice, Rich Text)
  .epub             → pandoc       (livros, long-form)
  .html .htm        → pandoc       (web-clippings salvos localmente)
  .rst .org .tex    → pandoc       (docs técnicos, Sphinx, LaTeX, Org-mode)

Uso:
  python3 scripts/convert_to_md.py raw/papers/foo.pdf
  python3 scripts/convert_to_md.py raw/docs/report.docx
  python3 scripts/convert_to_md.py raw/papers/           # toda a pasta
  python3 scripts/convert_to_md.py raw/ --force -v
"""

import subprocess
import sys
import argparse
from pathlib import Path

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

SUPPORTED_EXTENSIONS = {".pdf"} | set(PANDOC_FORMATS)


# ---------------------------------------------------------------------------
# Dependency checks
# ---------------------------------------------------------------------------

def _require_pymupdf4llm():
    try:
        import pymupdf4llm  # noqa: F401
    except ImportError:
        print(
            "Error: pymupdf4llm is not installed.\n"
            "Run: pip install pymupdf4llm",
            file=sys.stderr,
        )
        sys.exit(1)


def _check_pandoc():
    result = subprocess.run(
        ["pandoc", "--version"],
        capture_output=True,
    )
    if result.returncode != 0:
        print(
            "Error: pandoc is not installed or not found in PATH.\n"
            "Install: https://pandoc.org/installing.html",
            file=sys.stderr,
        )
        sys.exit(1)


# ---------------------------------------------------------------------------
# Converters
# ---------------------------------------------------------------------------

def convert_pdf(pdf_path: Path, output_dir: Path, verbose: bool = False) -> Path:
    import pymupdf4llm

    md_path = output_dir / (pdf_path.stem + ".md")
    if verbose:
        print(f"  Converting (PDF): {pdf_path}")

    md_text = pymupdf4llm.to_markdown(
        str(pdf_path),
        show_progress=verbose,
        table_strategy="lines_strict",
        ignore_code=False,
    )

    md_path.write_text(md_text, encoding="utf-8")

    if verbose:
        kb = md_path.stat().st_size / 1024
        print(f"  -> Saved: {md_path} ({kb:.1f} KB)")

    return md_path


def convert_via_pandoc(src_path: Path, output_dir: Path, verbose: bool = False) -> Path:
    ext = src_path.suffix.lower()
    fmt = PANDOC_FORMATS[ext]
    md_path = output_dir / (src_path.stem + ".md")

    if verbose:
        print(f"  Converting ({fmt}): {src_path}")

    cmd = [
        "pandoc",
        "--from", fmt,
        "--to", "gfm",
        "--wrap=none",
        "--output", str(md_path),
    ]

    # For EPUB and HTML, extract embedded media alongside the .md
    if fmt in ("epub", "html"):
        media_dir = output_dir / (src_path.stem + "_media")
        cmd += ["--extract-media", str(media_dir)]

    cmd.append(str(src_path))

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "pandoc exited with non-zero status")

    if verbose:
        kb = md_path.stat().st_size / 1024
        print(f"  -> Saved: {md_path} ({kb:.1f} KB)")

    return md_path


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Convert documents to Markdown preserving structure.",
    )
    parser.add_argument(
        "input",
        nargs="?",
        default=".",
        help=(
            "File or directory to convert. "
            f"Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))} "
            "(default: current directory)"
        ),
    )
    parser.add_argument(
        "-o", "--output",
        default=None,
        help="Output directory (default: same directory as each source file)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing .md files (default: skip)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Show detailed progress",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: '{input_path}' not found.", file=sys.stderr)
        sys.exit(1)

    # Collect files
    if input_path.is_file():
        if input_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            print(
                f"Error: unsupported format '{input_path.suffix}'. "
                f"Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}",
                file=sys.stderr,
            )
            sys.exit(1)
        files = [input_path]
    else:
        files = sorted(
            p for p in input_path.rglob("*")
            if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
        )

    if not files:
        print("No supported files found.", file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(files)} file(s).")

    # Lazy dependency checks
    has_pdf = any(f.suffix.lower() == ".pdf" for f in files)
    has_other = any(f.suffix.lower() != ".pdf" for f in files)
    if has_pdf:
        _require_pymupdf4llm()
    if has_other:
        _check_pandoc()

    converted, skipped, failed = 0, 0, 0
    for src_path in files:
        output_dir = Path(args.output) if args.output else src_path.parent
        output_dir.mkdir(parents=True, exist_ok=True)
        md_path = output_dir / (src_path.stem + ".md")

        if md_path.exists() and not args.force:
            if args.verbose:
                print(f"  SKIP {src_path.name} (already converted, use --force to overwrite)")
            else:
                print(f"  SKIP {src_path.name}")
            skipped += 1
            continue

        try:
            if src_path.suffix.lower() == ".pdf":
                convert_pdf(src_path, output_dir, verbose=args.verbose or len(files) == 1)
            else:
                convert_via_pandoc(src_path, output_dir, verbose=args.verbose or len(files) == 1)

            if not args.verbose:
                print(f"  OK   {src_path.name} -> {md_path.name}")
            converted += 1
        except Exception as exc:
            print(f"  ERR  {src_path.name}: {exc}", file=sys.stderr)
            failed += 1

    print(f"\nDone: {converted} converted, {skipped} skipped, {failed} failed.")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
