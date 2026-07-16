"""
validate_links.py
Verifica se todos os wikilinks [[...]] em wiki/ apontam para páginas existentes.

Resolução de links em duas camadas:
  1. Stem match: o slug do link corresponde ao nome de arquivo sem extensão (comportamento original)
  2. Path match: o link é um path relativo como [[jas/tables/foo]] que corresponde a
     wiki/data-dictionary/jas/tables/foo.md ou a qualquer .md cujo path relativo ao
     wiki_dir termina com o slug normalizado

Parsing de [[path|display]]:
  Suporta tanto [[slug]] quanto [[slug|Texto de display]] sem capturar o pipe
  ou backslash precedente gerado por alguns editores de Markdown.
"""

import sys
import re
from pathlib import Path

VAULT_ROOT = Path(__file__).parent.parent
WIKI_DIR = VAULT_ROOT / "wiki"

# Captura o target de wikilinks, ignorando o texto de display após | ou \|
WIKILINK_RE = re.compile(r"\[\[([^\]|\\]+?)(?:[\\]?\|[^\]]+)?\]\]")


def normalize_slug(raw: str) -> str:
    """Normaliza o alvo do link para comparação: lowercase, espaços → hifens, sem extensão."""
    return raw.strip().lower().replace(" ", "-").removesuffix(".md")


def build_lookup(wiki_dir: Path) -> tuple[set[str], dict[str, Path]]:
    """Constrói:
    - stem_set: conjunto de stems lowercase (nome sem extensão) de todos os .md
    - path_map: mapeamento de path-relativo-ao-wiki_dir (normalizado) → Path completo
    """
    stem_set: set[str] = set()
    path_map: dict[str, Path] = {}

    for p in wiki_dir.rglob("*.md"):
        stem = p.stem.lower()
        stem_set.add(stem)

        rel = p.relative_to(wiki_dir)
        # Registrar todas as formas de path relativo possíveis:
        # ex: data-dictionary/jas/tables/raw_hap_tb_autorizacao_senha
        path_key = str(rel.with_suffix("")).lower().replace("\\", "/")
        path_map[path_key] = p

        # Também registrar apenas os segmentos finais para compatibilidade
        # ex: jas/tables/raw_hap_tb_autorizacao_senha (sem data-dictionary/)
        parts = path_key.split("/")
        for i in range(1, len(parts)):
            suffix_key = "/".join(parts[i:])
            if suffix_key not in path_map:
                path_map[suffix_key] = p

    return stem_set, path_map


def resolve_link(raw_target: str, stem_set: set[str], path_map: dict[str, Path]) -> bool:
    """Retorna True se o link pode ser resolvido para um arquivo existente."""
    slug = normalize_slug(raw_target)

    # Camada 1: stem match (comportamento original)
    # Pega apenas o último segmento do path para o stem
    last_segment = slug.split("/")[-1]
    if last_segment in stem_set:
        return True

    # Camada 2: path match (links relativos como [[jas/tables/foo]])
    if slug in path_map:
        return True

    return False


def extract_links(path: Path) -> list[tuple[str, int]]:
    """Extrai todos os wikilinks de um arquivo, retornando (raw_target, line_number)."""
    links = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        print(f"[AVISO] Não foi possível ler {path}: {exc}")
        return links

    for lineno, line in enumerate(lines, start=1):
        for match in WIKILINK_RE.finditer(line):
            raw_target = match.group(1)
            links.append((raw_target, lineno))
    return links


def main() -> int:
    stem_set, path_map = build_lookup(WIKI_DIR)
    md_files = sorted(WIKI_DIR.rglob("*.md"))

    if not md_files:
        print(f"Nenhum arquivo .md encontrado em {WIKI_DIR}")
        return 0

    total_ok = 0
    total_dead = 0
    files_with_dead: set[str] = set()

    for path in md_files:
        rel = path.relative_to(VAULT_ROOT)
        links = extract_links(path)

        for raw_target, lineno in links:
            if resolve_link(raw_target, stem_set, path_map):
                total_ok += 1
            else:
                total_dead += 1
                files_with_dead.add(str(rel))
                print(f"[MORTO] {rel}:{lineno} — [[{raw_target}]]")

    print(
        f"\n{total_ok} links OK, {total_dead} links mortos"
        f" em {len(files_with_dead)} arquivo(s)"
    )
    return 1 if total_dead > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
