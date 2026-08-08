# Plano: Auditoria do wiki-lint

## Achados

### 1. `SyntaxWarning` em `find_orphans.py` — BUG

**Arquivo:** `scripts/find_orphans.py:6`

Docstring contém `"\|"` — sequência de escape inválida em Python 3.12+. Gera `SyntaxWarning` em cada execução.

```python
# bugado
- Suporta [[slug]], [[slug|display]], [[path/to/slug|display]] e \| (backslash-pipe)
```

**Correção:** mudar para `"\\|"` ou raw string na docstring.

---

### 2. `find_orphans.py` faz dois rglob sobre os mesmos arquivos — PERFORMANCE

**Arquivo:** `scripts/find_orphans.py:29-55`

`collect_all_slugs()` percorre `wiki_dir.rglob("*.md")` e coleta apenas os stems (sem ler conteúdo).  
`collect_referenced_slugs()` percorre `wiki_dir.rglob("*.md")` **novamente** e lê o conteúdo de cada arquivo.

Para uma wiki grande (ex: 500 arquivos), isso é 2x o I/O. Um único passo resolve ambos.

**Correção:** merge em `collect_slugs_and_refs()` — uma passagem que retorna `(all_slugs, referenced_slugs)`.

---

### 3. `rebuild_index.py` faz double-parse em arquivos data-dictionary — PERFORMANCE

**Arquivo:** `scripts/rebuild_index.py:82-90, 144-162`

No loop principal, cada arquivo já foi parseado via `parse_frontmatter(path)` → `data`.  
Depois, `make_link(path, WIKI_DIR)` chama `parse_frontmatter(path)` **novamente** para verificar `data.get("type") == "data-dictionary"`.

```python
# main loop:
data = parse_frontmatter(path)          # parse #1
link = make_link(path, WIKI_DIR)        # faz parse #2 internamente!
```

**Correção:** passar `data` já parseado para `make_link(path, wiki_dir, data)`.

---

### 4. Os 3 scripts rodam sequencialmente no fluxo wiki-lint — PARALELISMO

O skill `wiki-lint` instrui rodar em sequência:
1. `python3 scripts/validate_frontmatter.py`
2. `python3 scripts/validate_links.py`
3. `python3 scripts/find_orphans.py`

Os três são **completamente independentes** — sem dependência de dados entre eles. São uma oportunidade natural de paralelismo.

**Correção:** novo `scripts/wiki_lint.py` que lança os 3 subprocessos em paralelo via `subprocess.Popen`, coleta outputs, imprime em sequência, e retorna exit code combinado.

---

## Mudanças Planejadas

| # | Arquivo | Mudança |
|---|---------|---------|
| 1 | `scripts/find_orphans.py` | Fix SyntaxWarning no docstring |
| 2 | `scripts/find_orphans.py` | Merge dos dois rglob em um único passo |
| 3 | `scripts/rebuild_index.py` | `make_link()` recebe `data` já parseado |
| 4 | `scripts/wiki_lint.py` (novo) | Orquestrador paralelo dos 3 scripts |
| 5 | `.claude/skills/wiki-lint/SKILL.md` | Atualizar referência para o novo orquestrador |

## O que NÃO está sendo tocado

- Lógica de resolução de links — correta em `validate_links.py` e `find_orphans.py`
- Regex WIKILINK_RE — sem duplicação acidental (cada script já roda independente)
- Extração de frontmatter compartilhada — função pequena e estável, duplicação aceitável (YAGNI)
- O agente `wiki-linter` — faz varredura semântica separada, não é Python puro
