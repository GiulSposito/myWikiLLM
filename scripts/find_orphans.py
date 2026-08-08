"""
find_orphans.py
Lista todas as páginas em wiki/ que não recebem nenhum link de entrada (páginas órfãs).

Usa o mesmo regex e lógica de resolução de links que validate_links.py:
- Suporta [[slug]], [[slug|display]], [[path/to/slug|display]] e \\| (backslash-pipe)
- Resolve tanto por stem (nome do arquivo sem extensão) quanto por path relativo
"""

import sys
import re
from pathlib import Path

VAULT_ROOT = Path(__file__).parent.parent
WIKI_DIR = VAULT_ROOT / "wiki"

# Mesmo regex do validate_links.py: não captura o pipe nem o backslash antes dele
WIKILINK_RE = re.compile(r"\[\[([^\]|\\]+?)(?:[\\]?\|[^\]]+)?\]\]")

# Páginas de navegação — excluídas da lista de órfãs
NAV_PAGES = {"index", "log", "overview", "dashboard"}


def normalize_slug(raw: str) -> str:
    """Normaliza o alvo do link: lowercase, espaços → hifens, sem extensão."""
    return raw.strip().lower().replace(" ", "-").removesuffix(".md")


def collect_slugs_and_refs(wiki_dir: Path) -> tuple[dict[str, Path], set[str]]:
    """Única passagem: retorna (all_slugs, referenced_slugs) lendo cada arquivo uma vez.

    Para links com path (ex: [[jas/tables/foo]]), coleta o último segmento
    como stem, além do path completo normalizado.
    """
    all_slugs: dict[str, Path] = {}
    referenced: set[str] = set()

    for path in wiki_dir.rglob("*.md"):
        all_slugs[path.stem.lower()] = path
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            print(f"[AVISO] Não foi possível ler {path}: {exc}")
            continue
        for match in WIKILINK_RE.finditer(text):
            slug = normalize_slug(match.group(1))
            referenced.add(slug)
            referenced.add(slug.split("/")[-1])

    return all_slugs, referenced


def main() -> int:
    all_slugs, referenced_slugs = collect_slugs_and_refs(WIKI_DIR)

    total_pages = len(all_slugs)
    orphans: list[Path] = []

    for slug, path in sorted(all_slugs.items()):
        if slug in NAV_PAGES:
            continue
        if slug not in referenced_slugs:
            orphans.append(path)

    nav_not_referenced = sum(1 for s in NAV_PAGES if s not in referenced_slugs and s in all_slugs)
    pages_with_incoming = total_pages - len(orphans) - nav_not_referenced

    if orphans:
        print("Páginas órfãs (sem links de entrada):")
        for path in orphans:
            print(f"  {path.relative_to(VAULT_ROOT)}")
    else:
        print("Nenhuma página órfã encontrada.")

    print(
        f"\n{total_pages} páginas totais, "
        f"{pages_with_incoming} páginas com links de entrada, "
        f"{len(orphans)} páginas órfãs"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
