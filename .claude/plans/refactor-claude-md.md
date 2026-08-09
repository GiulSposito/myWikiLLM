# Plano: Fatoração do CLAUDE.md

## Diagnóstico

O `CLAUDE.md` tem **1178 linhas / ~39 KB / ~9–10 mil tokens** e é carregado automaticamente em toda sessão e em todo subagente custom (os 5 agentes herdam o arquivo por padrão via Claude Code). Isso gera o problema de **duplicação ativa com inconsistência**: as seções "Operation: INGEST/QUERY/LINT" (~337 linhas) replicam os `SKILL.md` que já existem em `.claude/skills/`, mas na versão desatualizada pré-round1 (sem batch de curadores, sem paralelismo, sem escopo restrito para contradiction-reviewer).

Análise por seção:

| Seção | Linhas atuais | Destino | Linhas resultantes |
|---|---|---|---|
| Intro + papel | 10 | Manter (condensado) | 10 |
| Architecture / Directory Map | 99 | Condensar (lista + notas não-óbvias) | 20 |
| Frontmatter Schema | 78 | Manter só YAML mínimo + pointer para `taxonomy.yml` | 15 |
| **Page Templates** (6 tipos + knowledge-map) | ~430 | Mover para `references/page-templates.md` | 0 |
| Type/Status/Confidence tables | ~43 | Mover junto com templates | 0 |
| **Operation: INGEST** | 163 | Deletar — já existe em `wiki-ingest/SKILL.md` (versão mais recente) | 0 |
| **Operation: QUERY** | 63 | Deletar — já existe em `wiki-query/SKILL.md` | 0 |
| **Operation: LINT** | 111 | Deletar — já existe em `wiki-lint/SKILL.md` | 0 |
| Quality Rules | 60 | Condensar prosa+exemplos → bullets | 25 |
| Wikilink Conventions | 40 | Condensar, cortar exemplos redundantes | 10 |
| Security Rules | 28 | Manter com cortes menores | 20 |
| Status Promotion Criteria | 15 | Manter condensado (cross-cutting) | 10 |
| Frontmatter Quick Reference | 36 | Mover para `references/page-templates.md` | 0 |
| **Common Patterns and Examples** | 55 | Deletar — redundante com SKILL.md + templates | 0 |
| Operational Checklist | 19 | Manter | 12 |
| **Task routing** (nova seção) | 0 | Criar (~8 linhas) | 8 |

**Resultado esperado: ~130–150 linhas / <4 KB / <2 mil tokens** (redução de ~87%).

---

## Fase 1 — Refatoração do CLAUDE.md (este plano)

### Ação 1: Deletar as 3 seções de operação do CLAUDE.md

As seções `## Operation: INGEST`, `## Operation: QUERY`, `## Operation: LINT` são deletadas integralmente. Elas são a maior fonte de desperdício (337 linhas) e as versões nos `SKILL.md` já são mais recentes e corretas. Não há migração — o conteúdo correto já está nos skills.

### Ação 2: Mover templates e tabelas para `references/page-templates.md`

Criar `.claude/skills/wiki-ingest/references/page-templates.md` contendo:
- Todos os 6 templates completos (source, concept, entity, decision, synthesis, pattern) + knowledge-map
- As tabelas de Type Taxonomy, Status Values, Confidence Levels (com colunas descritivas)
- O bloco "Frontmatter Quick Reference" (minimal + fully populated)

Ajustar `wiki-ingest/SKILL.md` Step 3 para referenciar `page-templates.md` quando precisar de um template.

> Nota: os templates de `concept` e `entity` já existem completos nos agentes `concept-curator.md` e `entity-curator.md`. A cópia em `page-templates.md` serve como referência canônica para os tipos que não têm agente dedicado (source, decision, synthesis, pattern, knowledge-map).

### Ação 3: Condensar seções que permanecem no CLAUDE.md

- **Directory Map**: de ~99 linhas (prosa + tabelas descritivas) → ~20 linhas (lista simples dos diretórios + 4–5 notas não-deriváveis do próprio repo: `raw/` é imutável, `data-dictionary` é tipo emergente, etc.)
- **Frontmatter Schema**: de ~78 linhas → ~15 linhas (YAML mínimo obrigatório + pointer: "valores permitidos em `manifests/taxonomy.yml`")
- **Quality Rules**: de ~60 linhas (prosa + exemplos) → ~25 linhas de bullets diretos (os exemplos de diff já estão nos SKILL.md onde são usados)
- **Wikilink Conventions**: de ~40 → ~10 linhas (regras de slug + sintaxe básica; cortar exemplos redundantes com o que os curadores já têm)
- **Security Rules**: de ~28 → ~20 linhas (cortar exemplos, manter regras)

### Ação 4: Adicionar seção "Task routing" (nova)

Uma tabela de ~8 linhas que mapeia: operação → onde está o procedimento completo. Substitui a necessidade de descrever o procedimento no CLAUDE.md:

```
| Operação | Skill / Agente |
|---|---|
| Ingest source | /wiki-ingest → .claude/skills/wiki-ingest/SKILL.md |
| Query wiki | /wiki-query → .claude/skills/wiki-query/SKILL.md |
| Lint / health check | /wiki-lint → .claude/skills/wiki-lint/SKILL.md |
| Create map | /wiki-map → .claude/commands/wiki-map.md |
| Supervised review | /wiki-review → .claude/commands/wiki-review.md |
| Validate structure | python3 scripts/validate_frontmatter.py && validate_links.py |
```

### Ação 5: Deletar "Common Patterns and Examples"

A seção (~55 linhas) é redundante: os exemplos de claims, contradições e log entries já aparecem nos SKILL.md e nos templates que serão movidos para `page-templates.md`. Deletar sem migração.

---

## Fase 2 — Ajustes de baixo risco em agentes (pós-Fase 1)

Executar em separado após validar a Fase 1:

1. **Adicionar `tools:` restritos nos 5 agentes** (sem Bash, apenas as ferramentas que cada um usa):
   - `source-reader`: `Read, Grep, Glob`
   - `contradiction-reviewer`: `Read, Grep, Glob`
   - `concept-curator`, `entity-curator`: `Read, Edit, Write, Grep, Glob`
   - `wiki-linter`: `Read, Write, Grep, Glob`

2. **Adicionar `maxTurns`** conservador (6–8) nos 5 agentes.

3. **Adicionar `disable-model-invocation: true`** às skills que só fazem sentido sob invocação explícita: `excalidraw-diagram`, `json-canvas`, `mermaid-visualizer`, `obsidian-canvas-creator`, `obsidian-cli`.

---

## O que NÃO está neste plano

- `model: haiku` nos agentes (experimento — depende de validação de qualidade)
- `context: fork` no wiki-query (mudança de comportamento, avaliar separado)
- Catálogo `manifests/catalog.jsonl` + `search_wiki.py` (esperar volume real de páginas)
- Contratos JSON compactos entre agentes (mudança estrutural grande)
- Tier `--deep` no wiki-ingest (aguardar ciclo de ingest real)

---

## Critério de sucesso

- `CLAUDE.md` com ≤ 170 linhas
- Zero duplicação de protocolo entre `CLAUDE.md` e `SKILL.md`
- `python3 scripts/validate_frontmatter.py` e `validate_links.py` passam sem erros
- Comportamento funcional idêntico: um ingest de teste com fonte curta e uma transcript deve produzir os mesmos arquivos de output

## Ordem de execução

1. Criar `references/page-templates.md` com todo o conteúdo movido
2. Atualizar `wiki-ingest/SKILL.md` Step 3 para apontar ao arquivo de templates
3. Reescrever `CLAUDE.md` (nova versão compacta)
4. Confirmar com o usuário antes de commitar
