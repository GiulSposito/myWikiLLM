# Plan: `/wiki-ref` — Lightweight External Reference Ingest

## Problema / Motivação

O comando `/wiki-ingest` é otimizado para absorver totalmente o conteúdo de uma fonte:
extrai claims, cria/atualiza páginas de entidade e conceito, roda contradiction review.
Isso é valioso para fontes primárias, mas excessivo para manuais técnicos extensos,
documentação de bibliotecas, ou referências que o usuário quer "apontar" na wiki sem
importar o conteúdo.

O novo comando `/wiki-ref` cria um **cartão de referência leve** — uma entrada em
`wiki/sources/` que documenta o que a fonte cobre e para que serve, sem extrair nem
propagar conhecimento para concept/entity pages.

---

## Decisões de Design

### 1. Nome do comando: `/wiki-ref`
Evita ambiguidade com `/wiki-ingest`. "ref" sinaliza que é uma referência, não uma
ingestão completa.

### 2. Pasta `raw/external/`
Nova sub-pasta dentro de `raw/` para receber stubs de fontes externas. Para URLs, o
stub é um arquivo `.md` com metadados (título, URL, data de acesso, resumo) — NÃO o
conteúdo completo. Para documentos locais extensos, o arquivo original permanece onde
está; o stub contém apenas os metadados de registro.

### 3. Tipo de página: `source` existente, com campo extra `ingest_depth: reference`
Não cria novo tipo (evita breaking changes no taxonomy). O campo `ingest_depth`
sinaliza para ferramentas e para leitura humana que a fonte foi indexada em modo leve.
Adicionar ao taxonomy como campo opcional de frontmatter (não validado como type).

### 4. O que o `/wiki-ref` FAZ vs. NÃO FAZ

| Ação | `/wiki-ingest` | `/wiki-ref` |
|------|---------------|-------------|
| Cria `wiki/sources/<slug>.md` | ✅ | ✅ |
| Cria stub em `raw/external/` | ❌ | ✅ |
| Extrai claims detalhados | ✅ | ❌ — apenas tópicos chave |
| Cria/atualiza entity pages | ✅ | ❌ — apenas menciona com wikilinks |
| Cria/atualiza concept pages | ✅ | ❌ — apenas menciona com wikilinks |
| Roda contradiction-reviewer | ✅ | ❌ |
| Propõe question pages | ✅ | ❌ |
| Atualiza index.md, log.md | ✅ | ✅ |
| Registra em sources.yml | ✅ | ✅ |

### 5. Seções do source page em modo reference
O template padrão de `source` é adaptado:
- **Key Topics** (em vez de "Key Claims") — lista de temas cobertos, não claims verificáveis
- **Mentioned Concepts** — wikilinks para conceitos existentes, sem criar páginas
- **Mentioned Entities** — wikilinks para entidades existentes, sem criar páginas
- **Access Note** — URL + como acessar a fonte completa
- Banner callout: `> [!note] Reference-only ingest...`
- **Sem** seções: "Important Quotes", "Contradictions", "Pages Updated" (ou apenas "None")

---

## Arquivos a Criar/Modificar

| Arquivo | Ação |
|---------|------|
| `.claude/skills/wiki-ref/SKILL.md` | CRIAR — protocolo completo do novo comando |
| `raw/external/.gitkeep` | CRIAR — inicializa a pasta no repositório |
| `CLAUDE.md` | MODIFICAR — adicionar `/wiki-ref` na tabela de Task Routing |

**Não modificar:**
- `manifests/taxonomy.yml` — `ingest_depth` é um campo opcional de frontmatter, não um tipo validado
- `.claude/skills/wiki-ingest/references/page-templates.md` — adicionar template "source (reference mode)" como nova seção ao arquivo existente

---

## Protocolo do SKILL.md

### Step 1: Dedup check
Igual ao wiki-ingest: verificar `manifests/sources.yml` por slug e sha256.

### Step 2: Identificar e obter o conteúdo
- **URL**: usar WebFetch para obter título, descrição, estrutura de seções. NÃO baixar o documento completo — apenas o suficiente para um resumo de 3-5 parágrafos.
- **Arquivo local extenso**: ler as primeiras ~500 linhas (ou Table of Contents se existir) para inferir escopo e tópicos.
- **Arquivo local curto** (< 800 palavras): ler completo — mas AINDA assim aplicar o protocolo reference (não criar entity/concept pages).

### Step 3: Criar stub em `raw/external/<slug>.md`
Conteúdo:
```markdown
# <Title> — External Reference Stub

- **URL / Path**: <url ou caminho>
- **Accessed**: YYYY-MM-DD
- **Type**: url | pdf | doc | repo | manual
- **Summary**: <2-3 frases sobre o que a fonte cobre>
```
Esse arquivo é o "audit trail" da referência. Imutável após criação (respeita invariante do `raw/`).

### Step 4: Criar source page em `wiki/sources/<slug>.md`
Usar template "source (reference mode)" — ver seção de templates.

Frontmatter adicional:
```yaml
ingest_depth: reference
external_url: <url se aplicável>
```

### Step 5: Identificar vínculos (SEM criar páginas)
Escanear conceitos e entidades mencionados na fonte. Para cada um:
- Se já existe página na wiki: incluir `[[slug]]` nas seções "Mentioned Concepts" / "Mentioned Entities"
- Se NÃO existe: mencionar o nome em texto plano (não criar wikilink para página inexistente)
- Registrar como "link candidates" no Step 7 report para que o usuário decida se quer ingeri-los depois

### Step 6: Atualizar navegação
- `wiki/index.md`: adicionar entrada
- `wiki/log.md`: append com entry específica marcando `[reference]`
- `manifests/sources.yml`: registrar com `sha256` e `raw_path: raw/external/<slug>.md`

### Step 7: Report
```
Mode: reference (lightweight)
Source page: wiki/sources/<slug>.md
Raw stub: raw/external/<slug>.md
Mentioned concepts (existing wiki pages): [list]
Mentioned entities (existing wiki pages): [list]
Link candidates (mentioned but no wiki page exists): [list]
  → Run /wiki-ingest or /wiki-ref on these to create pages
```

---

## Template: source (reference mode)

Nova seção a adicionar em `.claude/skills/wiki-ingest/references/page-templates.md`:

```markdown
## Template: source (reference mode)

File path: `wiki/sources/<slug>.md`
Used by: `/wiki-ref`

---
type: source
status: draft
confidence: low
created: YYYY-MM-DD
updated: YYYY-MM-DD
aliases: []
abstract: ""
sources: []
tags: []
ingest_depth: reference
external_url: ""
---

# <Title of the Source>

> [!note] Reference-only ingest
> Esta fonte foi indexada em modo referência. Conceito e entidade pages NÃO foram criados ou atualizados. Para ingestão completa, use `/wiki-ingest`.

## Bibliographic Metadata

- **Author(s) / Publisher**: 
- **Date**: 
- **Type**: url | pdf | manual | repo | doc
- **URL / Path**: 
- **Raw stub**: `raw/external/<slug>.md`
- **Accessed**: YYYY-MM-DD

## Summary

2–4 parágrafos descrevendo o escopo, propósito e audiência da fonte.

## Key Topics

Temas principais cobertos pela fonte (não claims verificáveis).

- Topic 1
- Topic 2

## Mentioned Concepts

Conceitos relevantes identificados. Wikilinks apenas para páginas existentes.

- [[concept-slug]] — como se relaciona com esta fonte
- Concept Name (sem página wiki ainda)

## Mentioned Entities

- [[entity-slug]] — como se relaciona
- Entity Name (sem página wiki ainda)

## Access Notes

Como acessar o conteúdo completo, seções relevantes, pré-requisitos.

## Open Questions

-
```

---

## Ordem de Implementação

1. Criar `raw/external/.gitkeep`
2. Criar `.claude/skills/wiki-ref/SKILL.md` com o protocolo completo
3. Adicionar template "source (reference mode)" em `page-templates.md`
4. Atualizar `CLAUDE.md` tabela de Task Routing

---

## O que NÃO está no escopo deste plano

- Modificar `taxonomy.yml` — `ingest_depth` é campo livre, não enum validado
- Criar agentes especializados — o protocolo é simples o suficiente para execução direta
- Integrar com `/wiki-ingest-batch` — referências são sempre unitárias, não em lote
