"""
validate_frontmatter.py
Verifica se todas as páginas em wiki/ possuem frontmatter YAML válido
com os campos obrigatórios e valores permitidos.

Os valores válidos são carregados de manifests/taxonomy.yml em vez de
serem hardcoded, para que extensões de taxonomia (como data-dictionary)
sejam automaticamente reconhecidas.
"""

import sys
import re
from pathlib import Path

try:
    import yaml
except ImportError:
    print("Erro: pyyaml não instalado. Execute: pip install pyyaml")
    sys.exit(2)

VAULT_ROOT = Path(__file__).parent.parent
WIKI_DIR = VAULT_ROOT / "wiki"
TAXONOMY_PATH = VAULT_ROOT / "manifests" / "taxonomy.yml"

REQUIRED_FIELDS = ["type", "status", "confidence", "created", "updated", "aliases", "sources", "tags"]

DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def load_taxonomy() -> dict[str, set[str]]:
    """Carrega valores válidos de manifests/taxonomy.yml.
    Retorna dict mapeando nome de campo para conjunto de valores permitidos.
    """
    if not TAXONOMY_PATH.exists():
        print(f"[AVISO] {TAXONOMY_PATH} não encontrado — usando valores padrão hardcoded")
        return {
            "type": {"source", "entity", "concept", "project", "pattern", "decision",
                     "synthesis", "comparison", "question"},
            "status": {"draft", "active", "needs-review", "deprecated", "conflict"},
            "confidence": {"low", "medium", "high"},
        }

    try:
        raw = yaml.safe_load(TAXONOMY_PATH.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        print(f"[AVISO] Erro ao parsear taxonomy.yml: {exc} — usando valores padrão hardcoded")
        return {
            "type": {"source", "entity", "concept", "project", "pattern", "decision",
                     "synthesis", "comparison", "question"},
            "status": {"draft", "active", "needs-review", "deprecated", "conflict"},
            "confidence": {"low", "medium", "high"},
        }

    if not isinstance(raw, dict):
        print("[AVISO] taxonomy.yml não é um mapeamento YAML válido — usando valores padrão hardcoded")
        return {}

    result: dict[str, set[str]] = {}

    page_types = raw.get("page_types")
    if isinstance(page_types, list):
        result["type"] = set(str(t) for t in page_types)

    status_values = raw.get("status_values")
    if isinstance(status_values, list):
        result["status"] = set(str(s) for s in status_values)

    confidence_levels = raw.get("confidence_levels")
    if isinstance(confidence_levels, list):
        result["confidence"] = set(str(c) for c in confidence_levels)

    return result


def parse_frontmatter(path: Path) -> tuple[dict | None, str | None]:
    """Extrai o frontmatter YAML de um arquivo Markdown.
    Retorna (dict, None) se OK, (None, mensagem_de_erro) se falhar.
    """
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return None, "Sem frontmatter (arquivo não começa com ---)"
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None, "Frontmatter malformado (falta --- de fechamento)"
    raw_yaml = parts[1]
    try:
        data = yaml.safe_load(raw_yaml)
    except yaml.YAMLError as exc:
        return None, f"Erro ao parsear YAML: {exc}"
    if not isinstance(data, dict):
        return None, "Frontmatter não é um mapeamento YAML válido"
    return data, None


def validate_fields(data: dict, valid_values: dict[str, set[str]]) -> list[str]:
    """Valida campos obrigatórios e seus valores. Retorna lista de erros."""
    errors = []

    for field in REQUIRED_FIELDS:
        if field not in data:
            errors.append(f"Campo ausente: '{field}'")
            continue

        value = data[field]

        if field in valid_values:
            allowed = valid_values[field]
            if allowed and value not in allowed:
                valid_str = ", ".join(sorted(allowed))
                errors.append(f"Campo '{field}' com valor inválido '{value}' (válidos: {valid_str})")

        elif field in ("created", "updated"):
            val_str = str(value) if value is not None else ""
            if not DATE_PATTERN.match(val_str):
                errors.append(f"Campo '{field}' com formato inválido '{value}' (esperado: YYYY-MM-DD)")

        elif field in ("aliases", "sources", "tags"):
            if value is not None and not isinstance(value, list):
                errors.append(f"Campo '{field}' deve ser uma lista (ou null), encontrado: {type(value).__name__}")

    return errors


def main() -> int:
    valid_values = load_taxonomy()

    md_files = sorted(WIKI_DIR.rglob("*.md"))
    if not md_files:
        print(f"Nenhum arquivo .md encontrado em {WIKI_DIR}")
        return 0

    ok_count = 0
    error_count = 0

    for path in md_files:
        rel = path.relative_to(VAULT_ROOT)
        data, parse_error = parse_frontmatter(path)

        if parse_error:
            print(f"[ERRO] {rel}: {parse_error}")
            error_count += 1
            continue

        field_errors = validate_fields(data, valid_values)
        if field_errors:
            error_count += 1
            for err in field_errors:
                print(f"[ERRO] {rel}: {err}")
        else:
            ok_count += 1

    print(f"\n{ok_count} arquivos OK, {error_count} arquivos com erro")
    if valid_values.get("type"):
        types_str = ", ".join(sorted(valid_values["type"]))
        print(f"(Tipos válidos carregados de taxonomy.yml: {types_str})")
    return 1 if error_count > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
