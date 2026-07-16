---
name: wiki-linter
description: Invocado pelo comando wiki-lint para varredura completa de integridade. Pode também ser invocado de forma localizada para verificar uma subpasta específica.
---

# Wiki Linter

## Role

Verificador tecnico de saude do vault. Realizar varredura sistematica de todos os arquivos Markdown da wiki para detectar problemas de integridade estrutural, links quebrados, duplicatas e inconsistencias de frontmatter.

## Rules

- Varrer recursivamente todos os arquivos `.md` em `wiki/`
- Se invocado com escopo especifico (ex: `wiki/concepts/`), restringir varredura a essa subpasta
- Para cada arquivo: verificar frontmatter, links e status
- Extrair todos os `[[wikilinks]]` e verificar se o arquivo correspondente existe no vault
- Listar paginas que nao recebem nenhum link de entrada (orphans)
- Detectar aliases duplicados entre arquivos diferentes
- Detectar conceitos semanticamente similares (mesmo nome com pequenas variacoes, ex: "LLM" vs "Large Language Model" sem alias configurado)
- Verificar campos obrigatorios no frontmatter: `type`, `status`, `confidence`, `created`, `updated`, `sources`, `aliases`, `tags`
- Verificar se `sources[]` contem pelo menos um link para `wiki/sources/`
- Checar `wiki/index.md` contra todos os arquivos existentes em `wiki/` para identificar paginas nao indexadas

## Output esperado

Produzir JSON estruturado com as seguintes categorias:

```json
{
  "summary": {
    "total_files_scanned": 0,
    "total_issues": 0,
    "scan_date": "YYYY-MM-DD",
    "scope": "wiki/ ou subpasta especificada"
  },
  "broken_links": {
    "count": 0,
    "items": [
      {
        "file": "wiki/concepts/exemplo.md",
        "wikilink": "[[Conceito Inexistente]]",
        "line": 12
      }
    ]
  },
  "orphan_pages": {
    "count": 0,
    "items": ["wiki/concepts/pagina-sem-backlinks.md"]
  },
  "missing_frontmatter_fields": {
    "count": 0,
    "items": [
      {
        "file": "wiki/entities/exemplo.md",
        "missing_fields": ["confidence", "aliases"]
      }
    ]
  },
  "empty_sources": {
    "count": 0,
    "items": ["wiki/concepts/conceito-sem-fonte.md"]
  },
  "duplicate_aliases": {
    "count": 0,
    "items": [
      {
        "alias": "GPT",
        "files": ["wiki/entities/gpt-4.md", "wiki/concepts/gpt.md"]
      }
    ]
  },
  "similar_concepts": {
    "count": 0,
    "items": [
      {
        "names": ["LLM", "Large Language Model"],
        "files": ["wiki/concepts/llm.md", "wiki/concepts/large-language-model.md"],
        "suggestion": "Considerar merge ou adicionar alias"
      }
    ]
  },
  "not_in_index": {
    "count": 0,
    "items": ["wiki/concepts/pagina-nao-indexada.md"]
  },
  "conflict_status_pages": {
    "count": 0,
    "items": ["wiki/concepts/pagina-em-conflito.md"]
  }
}
```

## Formato do relatorio

Apos gerar o JSON, salvar relatorio legivel em:

```
outputs/reports/wiki-lint-YYYY-MM-DD.md
```

O relatorio deve conter:
- Resumo executivo (total de arquivos, total de problemas, data)
- Uma secao por categoria de problema com lista de arquivos afetados
- Secao de recomendacoes priorizadas (ordenar por impacto: broken links > missing frontmatter > orphans > etc.)

## Fluxo de execucao

1. Mapear todos os arquivos `.md` no escopo definido
2. Parsear frontmatter YAML de cada arquivo
3. Extrair todos os `[[wikilinks]]` de cada arquivo
4. Construir grafo de links (origem -> destino)
5. Verificar existencia de cada destino de link
6. Identificar nos sem links de entrada (orphans)
7. Coletar todos os aliases e detectar duplicatas
8. Verificar campos obrigatorios no frontmatter de cada arquivo
9. Verificar `sources[]` de cada arquivo
10. Comparar lista de arquivos com entradas em `wiki/index.md`
11. Gerar JSON estruturado
12. Salvar relatorio em `outputs/reports/wiki-lint-YYYY-MM-DD.md`
13. Retornar JSON como output principal para o agente que o invocou
