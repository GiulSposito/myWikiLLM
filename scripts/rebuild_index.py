"""
rebuild_index.py
Regenera wiki/index.md a partir do frontmatter de todas as páginas, organizado por type.

Para o tipo data-dictionary, lista apenas os arquivos index.md de cada domínio
como pontos de entrada (não todas as tabelas individuais).
"""

import sys
from datetime import date
from pathlib import Path

try:
    import yaml
except ImportError:
    print("Erro: pyyaml não instalado. Execute: pip install pyyaml")
    sys.exit(2)

VAULT_ROOT = Path(__file__).parent.parent
WIKI_DIR = VAULT_ROOT / "wiki"
INDEX_PATH = WIKI_DIR / "index.md"

# Páginas de navegação — excluídas do índice
EXCLUDED_STEMS = {"index", "log", "overview", "dashboard"}

# Ordem preferida para as seções de type
TYPE_ORDER = [
    "source",
    "entity",
    "concept",
    "project",
    "pattern",
    "decision",
    "synthesis",
    "comparison",
    "question",
    "data-dictionary",
]

# Frontmatter para o index.md gerado
INDEX_FRONTMATTER = """\
---
type: concept
status: active
confidence: high
created: 2026-07-13
updated: {today}
aliases:
  - Index
  - Wiki index
sources: []
tags:
  - meta
  - vault
auto_generated: true
last_full_rebuild: {today}
---
"""


def parse_frontmatter(path: Path) -> dict | None:
    """Extrai e retorna o frontmatter YAML, ou None se ausente/inválido."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"[AVISO] Não foi possível ler {path}: {exc}")
        return None

    if not text.startswith("---"):
        return None
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None
    try:
        data = yaml.safe_load(parts[1])
    except yaml.YAMLError:
        return None
    return data if isinstance(data, dict) else None


def make_link(path: Path, wiki_dir: Path) -> str:
    """Gera o wikilink correto para uma página.
    Para data-dictionary: usa o path relativo ao wiki_dir para preservar a hierarquia.
    Para outros tipos: usa apenas o stem.
    """
    data = parse_frontmatter(path)
    if data and data.get("type") == "data-dictionary":
        rel = path.relative_to(wiki_dir).with_suffix("")
        return str(rel).replace("\\", "/")
    return path.stem


def format_entry(slug: str, data: dict) -> str:
    """Formata uma linha de entrada para o índice."""
    status = data.get("status", "?")
    confidence = data.get("confidence", "?")

    aliases = data.get("aliases") or []
    alias_str = ""
    if aliases:
        first_alias = str(aliases[0])
        alias_str = f" — {first_alias}"

    return f"- [[{slug}]]{alias_str} — status: {status}, confidence: {confidence}"


def is_data_dict_index(path: Path, wiki_dir: Path) -> bool:
    """Retorna True se o arquivo é um index.md de domínio dentro de data-dictionary/."""
    try:
        rel = path.relative_to(wiki_dir)
    except ValueError:
        return False
    parts = rel.parts
    return (
        len(parts) == 2
        and parts[0] == "data-dictionary"
        and parts[1] == "index.md"
    ) or (
        len(parts) == 3
        and parts[0] == "data-dictionary"
        and parts[2] == "index.md"
    )


def main() -> int:
    def should_exclude(p: Path) -> bool:
        """Exclui páginas de navegação, exceto index.md dentro de data-dictionary/."""
        if p.stem.lower() not in EXCLUDED_STEMS:
            return False
        # Manter index.md de domínios data-dictionary no índice
        if is_data_dict_index(p, WIKI_DIR):
            return False
        return True

    md_files = sorted(p for p in WIKI_DIR.rglob("*.md") if not should_exclude(p))

    # Agrupar por type
    by_type: dict[str, list[tuple[str, dict]]] = {}
    skipped = 0

    for path in md_files:
        data = parse_frontmatter(path)
        if data is None:
            print(f"[AVISO] Frontmatter ausente/inválido, ignorando: {path.relative_to(VAULT_ROOT)}")
            skipped += 1
            continue

        page_type = data.get("type")
        if not page_type:
            print(f"[AVISO] Campo 'type' ausente, ignorando: {path.relative_to(VAULT_ROOT)}")
            skipped += 1
            continue

        # Para data-dictionary: incluir apenas os index.md de cada domínio
        if str(page_type) == "data-dictionary" and not is_data_dict_index(path, WIKI_DIR):
            continue

        link = make_link(path, WIKI_DIR)
        by_type.setdefault(str(page_type), []).append((link, data))

    # Ordenar entradas dentro de cada tipo pelo link/slug
    for page_type in by_type:
        by_type[page_type].sort(key=lambda x: x[0].lower())

    # Construir o conteúdo do índice
    today = date.today().isoformat()

    lines: list[str] = [
        INDEX_FRONTMATTER.format(today=today),
        "# Wiki Index",
        "",
        "Knowledge compiled by Claude Code · LLM Wiki Vault",
        "",
        "Navigate by type below. Run `python scripts/rebuild_index.py` to regenerate from frontmatter.",
        "",
        "---",
        "",
    ]

    # Tipos conhecidos primeiro (na ordem definida), depois quaisquer outros em ordem alfabética
    all_types_in_data = set(by_type.keys())
    ordered_types = [t for t in TYPE_ORDER if t in all_types_in_data]
    remaining = sorted(all_types_in_data - set(ordered_types))
    final_type_order = ordered_types + remaining

    total_pages = 0

    for page_type in final_type_order:
        entries = by_type[page_type]
        section_title = page_type.replace("-", " ").title()
        if page_type == "data-dictionary":
            section_title = "Data Dictionaries"
        lines.append(f"## {section_title}")
        lines.append("")
        for slug, data in entries:
            lines.append(format_entry(slug, data))
            total_pages += 1
        lines.append("")
        lines.append("---")
        lines.append("")

    content = "\n".join(lines)
    INDEX_PATH.write_text(content, encoding="utf-8")

    print(f"Index rebuilt: {total_pages} pages across {len(final_type_order)} types")
    if skipped:
        print(f"[AVISO] {skipped} página(s) ignorada(s) por frontmatter ausente/inválido")
    return 0


if __name__ == "__main__":
    sys.exit(main())
