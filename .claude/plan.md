# Plano: Implementar Query Optimization Strategy (3 camadas)

## Objetivo

Implementar as três camadas de otimização de query descritas em `docs/query-optimization-strategy.md` nos comandos, agentes, skills e scripts do vault.

---

## Escopo: O que muda em cada arquivo

### Novos arquivos (1)

| Arquivo | O que é |
|---------|---------|
| `manifests/query-routing.yml` | Skeleton vazio, pronto para receber tópicos ao longo das ingestões |

### Arquivos modificados (9)

| Arquivo | Mudança |
|---------|---------|
| `CLAUDE.md` | (1) Schema frontmatter: adicionar `abstract:` após `aliases:`. (2) QUERY: adicionar Step 0 (routing) e Step 2b (knowledge maps). (3) INGEST Step 12: adicionar "Query routing proposals" ao relatório. (4) LINT: adicionar check de `abstract` ausente. |
| `.claude/skills/wiki-query/SKILL.md` | Adicionar Step 0 (ler query-routing.yml) antes do Step 1; adicionar Step 2b (verificar knowledge map) após Step 2. |
| `.claude/skills/wiki-ingest/SKILL.md` | Adicionar ao Step 12 report: "Query routing proposals" com instruções de quando propor. |
| `.claude/skills/wiki-lint/SKILL.md` | Adicionar check #13: pages sem `abstract:` em concepts/entities/synthesis → flag como `needs-review`. |
| `.claude/agents/wiki-linter.md` | Adicionar categoria `missing_abstract` ao JSON output; adicionar ao algoritmo single-pass (acumular `abstract` absent por arquivo). |
| `.claude/agents/concept-curator.md` | Template de página: adicionar campo `abstract:` no frontmatter (após `aliases:`), com instrução de 1–2 frases factuais. |
| `.claude/agents/entity-curator.md` | Template de página: adicionar campo `abstract:` no frontmatter (após `aliases:`), com instrução de 1–2 frases factuais. |
| `scripts/rebuild_index.py` | Em `format_entry()`: extrair `abstract` do frontmatter e appendar na linha do índice quando presente. |
| `scripts/validate_frontmatter.py` | Adicionar `abstract` à lista `REQUIRED_FIELDS` (vault está resetado; novas páginas devem ter o campo). |

---

## Detalhe por camada

### Camada 1 — Query Routing Manifest

**`manifests/query-routing.yml`** (novo)
```yaml
# manifests/query-routing.yml
# Maps topic keywords → canonical page slugs for that topic.
# Updated during INGEST Step 12 (proposals only — user confirms before adding).
topics: {}
```

**`wiki-query` SKILL.md** — inserir Step 0 antes do Step 1 atual:
```
### Step 0: Route the query
- Read `manifests/query-routing.yml`
- If the query matches one or more topic keywords:
    Load only the pages listed under that topic (pages + synthesis + decisions)
    Skip reading index.md entirely — proceed to Step 3
- If no topic matches OR the file is empty:
    Fall back to Step 1 (read index.md)
```

**`wiki-query` SKILL.md** — inserir Step 2b após Step 2 atual:
```
### Step 2b: Check for domain knowledge map
- If the matched page cluster has > 5 pages in the same domain:
    Check if wiki/synthesis/knowledge-map-<domain>.md exists
    If yes: load the knowledge map instead of the individual pages
    If no: load individual pages as usual (proceed with Step 2)
```

**`wiki-ingest` SKILL.md** — no Step 12, adicionar seção ao relatório:
```
Query routing proposals:
  - New topic entries to add to manifests/query-routing.yml
  - Existing topics to add pages to
  (Do NOT auto-update — list proposals for user confirmation)
```

---

### Camada 2 — Abstract Enrichment

**Frontmatter schema** (CLAUDE.md + agentes) — adicionar campo após `aliases:`:
```yaml
abstract: "1–2 sentence factual description of what this page contains."
```

Regras para o campo:
- 1–2 frases
- Factual, não meta ("This page describes..." é proibido)
- Mesmo idioma do conteúdo da página
- Obrigatório em: concept, entity, synthesis, source, pattern, decision
- Opcional em: question (podem ser especulativos)

**`scripts/rebuild_index.py`** — mudança na `format_entry()`:
```python
abstract = data.get("abstract", "")
entry = f"- [[{slug}]]{alias_str}"
if abstract:
    entry += f" — {abstract}"
entry += f" — status: {status}, confidence: {confidence}"
```

**`scripts/validate_frontmatter.py`** — adicionar `"abstract"` a `REQUIRED_FIELDS`.

**Linter** — nova categoria `missing_abstract` no JSON output do `wiki-linter.md`:
```json
"missing_abstract": {
  "count": 0,
  "items": ["wiki/concepts/foo.md"]
}
```

---

### Camada 3 — Domain Knowledge Maps

**`wiki-query` SKILL.md** — Step 2b já inclui a verificação do knowledge map (descrito acima).

**CLAUDE.md** — adicionar template de knowledge map (tipo `synthesis`) e regra de Step 2b no protocolo QUERY.

**Não criar** os knowledge maps agora — eles são criados via `/wiki-review` ou synthesis pass. O plano apenas conecta o protocolo de QUERY para usá-los quando existirem.

---

## Sequência de execução

1. Criar `manifests/query-routing.yml`
2. Modificar `scripts/rebuild_index.py` (format_entry)
3. Modificar `scripts/validate_frontmatter.py` (REQUIRED_FIELDS)
4. Modificar `.claude/agents/concept-curator.md` (template frontmatter)
5. Modificar `.claude/agents/entity-curator.md` (template frontmatter)
6. Modificar `.claude/agents/wiki-linter.md` (missing_abstract category)
7. Modificar `.claude/skills/wiki-lint/SKILL.md` (check #13)
8. Modificar `.claude/skills/wiki-query/SKILL.md` (Step 0 + Step 2b)
9. Modificar `.claude/skills/wiki-ingest/SKILL.md` (Step 12 routing proposals)
10. Modificar `CLAUDE.md` (frontmatter schema + QUERY Steps 0/2b + INGEST Step 12 + LINT check)
11. Verificar com `python3 scripts/validate_frontmatter.py` (wiki vazia = 0 erros esperados)

---

## O que NÃO está incluído

- Criar knowledge map files (`wiki/synthesis/knowledge-map-*.md`) — feitos on demand
- Popular `abstract:` retroativamente — vault está resetado, não há páginas existentes
- Criar entradas em `query-routing.yml` — feito progressivamente durante ingestões
