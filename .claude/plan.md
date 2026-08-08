# Batch Ingest Implementation Plan

Based on `docs/batch-ingestion.md`. Implements `/wiki-ingest-batch` as a 6-phase pipeline.

---

## Language Fix: Wiki em inglês apesar de fontes em português

### Diagnóstico — causa raiz em 3 camadas

A transcrição VTT está em português (`"Pitch, né? Oo cockpit é uma ferramenta que vamos conseguir
manipular"`), mas a wiki gerada fica em inglês. Rastreando o idioma por cada etapa:

```
VTT (pt-BR) → Extração (EN) → Curadoria (EN) → Renderer/Writer (EN hardcoded)
                ↑ raiz         ↑ cascata               ↑ crôme estrutural
```

**Camada 1 — Extração (raiz):** `BATCH_EXTRACTION_RULES` está escrito inteiramente em inglês.
O Haiku recebe um prompt misto: `source-reader.md` em português + `BATCH_EXTRACTION_RULES` em
inglês + transcrição em português. Sem instrução explícita de idioma, o LLM infere que inglês é o
idioma esperado (o "idioma de trabalho" do prompt) e escreve `factual_summary`, textos de claims,
nomes de conceitos e entidades em inglês.

**Camada 2 — Curadoria (cascata):** `CURATION_SYSTEM_PROMPT` está 100% em inglês e não tem
instrução de idioma. As evidências recebidas (claims da extração) já chegam em inglês. O Sonnet
escreve `abstract` e `definition` em inglês.

**Camada 3 — Renderer/Writer (chrome estrutural):** Todos os headers de seção estão hardcoded em
inglês em `renderer.py` e `writer.py`: "Bibliographic Metadata", "Key Claims", "Relevant Entities",
"Key Facts", "Claims Added by Batch Ingest", etc.

### Solução

Adicionar configuração `wiki_language` ao pipeline e propagar para todas as camadas:

- `wiki_language: source` → instrução dinâmica ao LLM: "escreva no idioma da fonte"
- `wiki_language: pt` / `wiki_language: en` → instrução explícita de idioma

---

### Mudanças planejadas

#### 1. `manifests/batch-ingest.yml` — novo campo de configuração

```yaml
wiki_language: source   # "source" = match source language | "pt" | "en" | etc.
```

#### 2. `scripts/batch/config.py` — field no dataclass

```python
@dataclass
class BatchIngestConfig:
    ...
    wiki_language: str = "source"
```
Ler via `cfg.wiki_language = str(raw.get("wiki_language", "source"))`.

#### 3. `scripts/batch/extractor.py` — injeção de instrução de idioma

Transformar `get_system_prompt()` para receber `wiki_language` e injetar instrução ao final:

```python
_LANGUAGE_INSTRUCTIONS = {
    "source": (
        "Write all extracted text fields (factual_summary, claim texts, title, "
        "entity names, concept names) in the same language as the source document."
    ),
    "pt": "Write all extracted text fields in Portuguese.",
    "en": "Write all extracted text fields in English.",
}
```

Inserir como último parágrafo de `BATCH_EXTRACTION_RULES`.

Assinatura muda para `get_system_prompt(vault_root: Path, wiki_language: str = "source") -> str`.

#### 4. `scripts/batch/curator.py` — instrução de idioma na curadoria

Adicionar ao final de `CURATION_SYSTEM_PROMPT`:

```
## Language

Write abstract, definition, claim texts, and all prose in the same language as
the evidence claims provided. Do not translate content to English.
```

Quando `wiki_language` é explícito (ex: "pt"), usar "Write all prose in Portuguese."

Para propagar o `wiki_language` do config, `build_curation_requests()` recebe o cfg e gera o
system prompt dinamicamente (atualmente é uma constante de módulo).

#### 5. `scripts/batch/renderer.py` — headers localizados

Criar um dicionário de traduções e selecionar via `wiki_language`:

```python
_LABELS = {
    "en": {
        "bibliographic_metadata": "Bibliographic Metadata",
        "summary": "Summary",
        "key_claims": "Key Claims",
        "important_quotes": "Important Quotes",
        "relevant_entities": "Relevant Entities",
        "relevant_concepts": "Relevant Concepts",
        "contradictions": "Contradictions",
        "pages_updated": "Pages Updated",
        "open_questions": "Open Questions",
    },
    "pt": {
        "bibliographic_metadata": "Metadados Bibliográficos",
        "summary": "Resumo",
        "key_claims": "Claims Principais",
        "important_quotes": "Citações Importantes",
        "relevant_entities": "Entidades Relevantes",
        "relevant_concepts": "Conceitos Relevantes",
        "contradictions": "Contradições",
        "pages_updated": "Páginas Atualizadas",
        "open_questions": "Questões Abertas",
    },
}
```

`render_source_page()` recebe `wiki_language: str = "source"` — quando `"source"`, usa `"pt"` como
fallback (maioria das fontes do projeto) mas o design permite expansão.

> Nota: `wiki_language: "source"` é um hint para LLMs (instruction dinâmica) mas o renderer
> precisa de um idioma concreto para os labels. Quando `"source"`, o renderer usa o idioma detectado
> a partir do `extraction.title` ou cai no default configurável via
> `resolution.language_fallback: pt` em `batch-ingest.yml`.

#### 6. `scripts/batch/writer.py` — headers localizados

Mesma abordagem: dicionário `_LABELS` com `"en"` e `"pt"`, aplicado às seções:
"Claims Added by Batch Ingest", "Contradictions", "Open Questions (Proposed)",
"Definition", "Key Facts", "Related Pages".

---

### Testes a adicionar/ajustar

| Arquivo | Teste |
|---------|-------|
| `tests/batch/test_extractor.py` | `test_system_prompt_contains_language_instruction` — verifica que a instrução de idioma aparece no prompt quando `wiki_language="source"` |
| `tests/batch/test_extractor.py` | `test_system_prompt_explicit_language_pt` — verifica instrução "in Portuguese" quando `wiki_language="pt"` |
| `tests/batch/test_normalizer.py` | já coberto (slugify com acentos) |

---

### Arquivos impactados (resumo)

| Arquivo | Tipo de mudança |
|---------|----------------|
| `manifests/batch-ingest.yml` | novo campo `wiki_language: source` |
| `scripts/batch/config.py` | novo field `wiki_language: str = "source"` |
| `scripts/batch/extractor.py` | `get_system_prompt()` injeta instrução de idioma |
| `scripts/batch/curator.py` | system prompt gerado dinamicamente com instrução de idioma |
| `scripts/batch/renderer.py` | labels localizados + `wiki_language` param |
| `scripts/batch/writer.py` | labels localizados + `wiki_language` param |

Nenhuma mudança em modelos Pydantic, scanner, normalizer, resolver, grouper, state, planner.

---

## Phase 1 — Infrastructure (no API calls)

### New files

| File | Purpose |
|------|---------|
| `pyproject.toml` | Dependencies: pydantic>=2, anthropic, rapidfuzz, pyyaml |
| `manifests/batch-ingest.yml` | Config: models, token limits, quality thresholds (spec §39) |
| `scripts/batch/__init__.py` | Package marker |
| `scripts/batch/models.py` | Pydantic v2 models: `Claim`, `Locator`, `EntityMention`, `ConceptMention`, `OpenQuestion`, `InternalTension`, `SourceExtraction`, `ClaimAddition`, `RelationAddition`, `Conflict`, `PageMutationPlan` (spec §8, §23) |
| `scripts/batch/config.py` | Load `manifests/batch-ingest.yml` into typed dataclass |
| `scripts/batch/state.py` | `BatchState`: create/load/save `staging/<batch>/manifest.yml`; item status transitions |
| `scripts/batch/scanner.py` | Walk directory; SHA256 per file; dedup against `manifests/sources.yml` (rules 1–3, spec §7); line-number injector for `.md` without timestamps |
| `scripts/batch_ingest.py` | CLI entry point — `scan` subcommand + skeleton for remaining subcommands |
| `tests/batch/fixtures/` | 10-transcript golden fixture set (spec §44) |
| `tests/batch/test_scanner.py` | Discovery, SHA256, dedup rules 1–3 |
| `tests/batch/test_dedup.py` | Idempotent scan, changed-source flag |

### Modified files
- `.gitignore`: add `staging/`

---

## Phase 2 — MAP (Extraction Batch)

### New files

| File | Purpose |
|------|---------|
| `scripts/batch/extractor.py` | Read `source-reader.md`; build system prompt with batch rules + language instruction; chunking; `merge_source_extraction()` |
| `scripts/batch/anthropic_batch.py` | Wrap Anthropic `client.beta.messages.batches`; submit, status, collect, retry |

### CLI subcommands added
`submit`, `status`, `collect`, `resume`, `run`

---

## Phase 3 — Resolution

### New files

| File | Purpose |
|------|---------|
| `scripts/batch/normalizer.py` | Unicode normalization, transliteration (NFD), slugify, entity-type validation, exact dedup, alias lookup |
| `scripts/batch/resolver.py` | Exact → fuzzy (≥0.85) → LLM resolution; `defer` never creates pages |

---

## Phase 4 — REDUCE (Curation Batch)

### New files

| File | Purpose |
|------|---------|
| `scripts/batch/grouper.py` | Group resolved evidence by target wiki page |
| `scripts/batch/curator.py` | Build Curation Batch with language-aware system prompt |
| `scripts/batch/planner.py` | Merge PageMutationPlans → `update-plan.json` |

---

## Phase 5 — Writer

### New files

| File | Purpose |
|------|---------|
| `scripts/batch/renderer.py` | Deterministic source page generation with localized labels |
| `scripts/batch/writer.py` | Single writer with localized section headers |

---

## Phase 6 — QA + Claude Skill

### New files

| File | Purpose |
|------|---------|
| `scripts/batch/qa.py` | Pre-apply blocking checks; sampling-based QA report |
| `.claude/skills/wiki-ingest-batch/SKILL.md` | Claude UX skill |

---

## Key Design Decisions

1. **Pydantic v2** — structured outputs directly from JSON Schema.
2. **`anthropic` Python SDK** — Message Batches API.
3. **`rapidfuzz`** — fuzzy entity resolution, threshold 0.85.
4. **`wiki_language: source`** — LLMs follow source document language; renderer/writer use explicit language code with `pt` as project default fallback.
5. **`staging/` is gitignored** — no intermediate artifacts in version control.
6. **No automatic git commits** — writer leaves working tree dirty for user review.
7. **`renderer.py` is deterministic** — source pages generated from templates, no LLM.
8. **Contradictions in REDUCE** — embedded in Curation Batch (spec §24).
9. **`sources.yml` backwards-compatible** — additive new fields.
