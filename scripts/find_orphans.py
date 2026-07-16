"""
find_orphans.py
Lista todas as páginas em wiki/ que não recebem nenhum link de entrada (páginas órfãs).

Usa o mesmo regex e lógica de resolução de links que validate_links.py:
- Suporta [[slug]], [[slug|display]], [[path/to/slug|display]] e \| (backslash-pipe)
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


def collect_all_slugs(wiki_dir: Path) -> dict[str, Path]:
    """Retorna mapeamento stem_lowercase -> Path para todos os .md."""
    return {p.stem.lower(): p for p in wiki_dir.rglob("*.md")}


def collect_referenced_slugs(wiki_dir: Path) -> set[str]:
    """Coleta todos os stems referenciados por wikilinks em qualquer .md.

    Para links com path (ex: [[jas/tables/foo]]), coleta o último segmento
    como stem, além do path completo normalizado.
    """
    referenced: set[str] = set()
    for path in wiki_dir.rglob("*.md"):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            print(f"[AVISO] Não foi possível ler {path}: {exc}")
            continue
        for match in WIKILINK_RE.finditer(text):
            raw = match.group(1)
            slug = normalize_slug(raw)
            # Adicionar o slug completo (pode ser path como jas/tables/foo)
            referenced.add(slug)
            # Adicionar também apenas o último segmento (stem), para resolver
            # links relativos como [[jas/tables/foo]] → stem "foo"
            last_segment = slug.split("/")[-1]
            referenced.add(last_segment)
    return referenced


def main() -> int:
    all_slugs = collect_all_slugs(WIKI_DIR)
    referenced_slugs = collect_referenced_slugs(WIKI_DIR)

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
