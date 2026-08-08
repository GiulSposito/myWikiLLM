Sim. A melhor forma de implementar a opção B é tratar a ingestão em batch como um **compilador em duas passagens**: primeiro extrair evidências de cada transcrição com Haiku em paralelo; depois consolidar essas evidências por entidade/conceito com Sonnet, produzindo um plano de mutações que só então é aplicado deterministicamente à wiki.

Isso preserva o `/wiki-ingest` atual para casos unitários e cria um caminho novo para volumes grandes. Hoje o fluxo unitário faz dedup → source-reader → source page → curators → contradiction review → navegação → validação para cada fonte; é justamente essa repetição que o batch deve eliminar. 

# Especificação — Batch Ingest para myWikiLLM

## 1. Objetivo

Adicionar ao `myWikiLLM` uma operação:

```bash
/wiki-ingest-batch raw/transcripts/<diretorio>
```

e uma CLI equivalente:

```bash
python3 scripts/batch_ingest.py run raw/transcripts/<diretorio>
```

capaz de processar centenas ou milhares de transcrições mantendo:

* rastreabilidade até a fonte original;
* citações por claim;
* detecção de entidades e conceitos duplicados;
* preservação de conflitos;
* idempotência;
* retomada após falha;
* revisão antes da escrita;
* baixo custo de tokens;
* nenhuma escrita concorrente em `wiki/`.

O `raw/` continua imutável, conforme a arquitetura existente do projeto. ([GitHub][1])

---

# 2. Princípio arquitetural

O pipeline passa a ter esta forma:

```text
                RAW TRANSCRIPTS
                       │
                       ▼
              1. SCAN / PREFLIGHT
                       │
                       ▼
          2. EXTRACTION BATCH — HAIKU
                 MAP: source → facts
                       │
                       ▼
               extraction/*.json
                       │
                       ▼
          3. NORMALIZE / DEDUP / RESOLVE
                       │
              ┌────────┴────────┐
              │                 │
        deterministic       ambiguous
              │                 │
              │           RESOLUTION BATCH
              │              Sonnet
              └────────┬────────┘
                       │
                       ▼
             4. GROUP BY TARGET
                       
       api-gateway ← claims de 47 reuniões
       projeto-x   ← claims de 31 reuniões
       pessoa-y    ← claims de 12 reuniões
                       │
                       ▼
          5. CURATION BATCH — SONNET
             REDUCE: facts → mutations
                       │
                       ▼
                update-plan.json
                       │
                       ▼
                 6. QA / REVIEW
                       │
                       ▼
               7. SINGLE WRITER
                       │
                       ▼
                     WIKI
                       │
                       ▼
             8. VALIDATE / REPORT
```

Regra principal:

> LLMs podem ler e propor em paralelo. Somente código determinístico modifica a wiki.

---

# 3. Dois batches de IA, não um

## Batch A — Extraction / MAP

Unidade de processamento:

```text
1 transcrição → 1 SourceExtraction
```

Modelo default:

```text
claude-haiku-4-5-20251001
```

Haiku 4.5 é o modelo mais rápido da linha ativa atual e suporta structured outputs. ([Claude Platform][2])

Não recebe a wiki inteira.

Recebe apenas:

```text
source-reader rules
+
taxonomia relevante
+
transcrição
```

O `source-reader` atual já define corretamente que sua função é extração factual, sem trazer conhecimento externo. Essas regras devem continuar sendo a fonte normativa do prompt. 

---

## Batch B — Curation / REDUCE

Unidade de processamento:

```text
1 página alvo
+
todas as novas evidências relacionadas
+
conteúdo atual da página
→
1 PageMutationPlan
```

Modelo default:

```text
claude-sonnet-5
```

Exemplo:

```text
wiki/concepts/api-gateway.md

Existing knowledge
        +
claims de transcript-001
claims de transcript-017
claims de transcript-023
claims de transcript-028
claims de transcript-091
        ↓
Sonnet
        ↓
PageMutationPlan
```

Assim uma página é interpretada **uma vez por lote**, e não uma vez para cada transcrição.

---

# 4. Estrutura de arquivos proposta

Adicionar:

```text
myWikiLLM/
│
├── staging/                         # gitignored
│
├── scripts/
│   ├── batch_ingest.py              # CLI
│   │
│   └── batch/
│       ├── __init__.py
│       ├── models.py
│       ├── config.py
│       ├── scanner.py
│       ├── extractor.py
│       ├── anthropic_batch.py
│       ├── normalizer.py
│       ├── resolver.py
│       ├── grouper.py
│       ├── curator.py
│       ├── planner.py
│       ├── renderer.py
│       ├── writer.py
│       ├── qa.py
│       └── state.py
│
├── manifests/
│   └── batch-ingest.yml
│
├── .claude/
│   └── skills/
│       └── wiki-ingest-batch/
│           └── SKILL.md
│
└── tests/
    └── batch/
        ├── fixtures/
        ├── test_scanner.py
        ├── test_dedup.py
        ├── test_normalizer.py
        ├── test_resolver.py
        ├── test_planner.py
        ├── test_writer.py
        └── test_idempotency.py
```

Alterar `.gitignore`:

```gitignore
# Batch ingestion intermediate artifacts
staging/
```

O `.env` já é ignorado pelo projeto, então a API key deve continuar somente em:

```text
ANTHROPIC_API_KEY=...
```

e nunca em configuração versionada. 

---

# 5. Estado persistente do batch

Cada execução cria:

```text
staging/
└── 20260807-architecture-transcripts/
    ├── manifest.yml
    ├── requests/
    ├── extraction/
    ├── normalized/
    ├── resolution/
    ├── grouped/
    ├── curation/
    ├── update-plan.json
    ├── qa-report.json
    └── errors/
```

Exemplo de `manifest.yml`:

```yaml
schema_version: "1"

batch_id: "20260807-architecture-transcripts"

created_at: "2026-08-07T17:00:00-03:00"

baseline:
  git_head: "abc123..."

models:
  extraction: claude-haiku-4-5-20251001
  resolution: claude-sonnet-5
  curation: claude-sonnet-5

provider_batches:
  extraction: []
  resolution: []
  curation: []

items:
  - source_key: meeting-001
    custom_id: src_a821e682
    files:
      - raw/transcripts/meeting-001.md
    sha256: "..."
    status: scanned

statistics:
  discovered: 0
  skipped_duplicate: 0
  extracted: 0
  failed: 0
  applied: 0
```

Isso permite:

```bash
python3 scripts/batch_ingest.py resume staging/<batch>
```

sem repetir requests concluídas.

---

# 6. Identificação da fonte

Não usar nome de arquivo como identidade única.

Durante `scan`:

```python
sha256 = SHA256(raw_bytes)
```

Gerar:

```text
source_key = slug + short_hash
```

Exemplo:

```text
architecture-weekly-a821e682
```

O `custom_id` da Anthropic poderia ser:

```text
src_a821e6821c98
```

A Message Batches API exige `custom_id` único, com até 64 caracteres, formado apenas por caracteres alfanuméricos, `_` e `-`. Resultados podem retornar fora de ordem, portanto `custom_id` deve ser sempre usado para associar resultado e fonte. ([Claude Platform][3])

---

# 7. Deduplicação

## Regra 1

Mesmo path + mesmo hash:

```text
SKIP
```

## Regra 2

Path diferente + mesmo hash:

```text
SKIP
duplicate_of: source-X
```

## Regra 3

Mesmo path + hash diferente:

```text
CHANGED SOURCE
```

Não reingerir silenciosamente.

Marcar:

```yaml
status: changed-source
```

Exigir:

```bash
--reingest-changed
```

## Compatibilidade com sources.yml atual

Hoje `manifests/sources.yml` funciona como o dedup guard da ingestão e armazena slug, título, tipo, data e path. 

Novas entradas passam a aceitar campos adicionais:

```yaml
- slug: architecture-weekly
  title: Architecture Weekly
  type: transcript
  ingested: 2026-08-07
  raw_path: raw/transcripts/architecture-weekly.md

  sha256: "..."
  batch_id: "20260807-architecture-transcripts"

  extraction:
    schema_version: "1"
    model: claude-haiku-4-5-20251001
```

Entradas antigas continuam válidas.

---

# 8. SourceExtraction

Não queremos Markdown saindo do Batch A.

Queremos JSON estrito.

O contrato deve ser definido como Pydantic em:

```text
scripts/batch/models.py
```

e o mesmo modelo deve gerar o JSON Schema enviado ao Claude.

Anthropic structured outputs usa JSON Schema através de `output_config.format`, e structured outputs são compatíveis com Batch Processing. ([Claude Platform][4])

Modelo conceitual:

```python
class Locator(BaseModel):
    timestamp_start: str | None
    timestamp_end: str | None

    line_start: int | None
    line_end: int | None

    speaker: str | None


class Claim(BaseModel):
    text: str

    kind: Literal[
        "fact",
        "decision",
        "requirement",
        "constraint",
        "risk",
        "plan",
        "opinion",
        "uncertainty"
    ]

    locator: Locator

    subject_terms: list[str]

    verbatim_excerpt: str | None


class EntityMention(BaseModel):
    name: str

    entity_type: Literal[
        "company",
        "person",
        "product",
        "tool",
        "organization",
        "framework",
        "place"
    ]

    aliases: list[str]


class ConceptMention(BaseModel):
    name: str
    aliases: list[str]


class OpenQuestion(BaseModel):
    text: str
    locator: Locator


class InternalTension(BaseModel):
    description: str
    claim_indexes: list[int]


class SourceExtraction(BaseModel):
    schema_version: Literal["1"]

    title: str
    authors: list[str]
    source_date: str | None
    participants: list[str]

    factual_summary: str

    claims: list[Claim]

    entities: list[EntityMention]
    concepts: list[ConceptMention]

    open_questions: list[OpenQuestion]
    internal_tensions: list[InternalTension]
```

O modelo não gera `claim_id`.

Depois da extração:

```python
claim_id = f"{source_key}:c{index:04d}"
```

Isso torna os IDs determinísticos.

---

# 9. Localização obrigatória dos claims

Para transcrições com timestamp:

```json
{
  "timestamp_start": "00:37:21",
  "timestamp_end": "00:37:43",
  "speaker": "João"
}
```

Para `.md` ou `.txt` sem timestamp, `scanner.py` passa uma versão temporária numerada ao modelo:

```text
L000001 ...
L000002 ...
L000003 ...
```

sem alterar `raw/`.

O resultado:

```json
{
  "line_start": 517,
  "line_end": 524
}
```

Um claim sem timestamp ou linha deve:

```text
QA WARNING
```

Claims considerados críticos podem exigir locator obrigatório:

```text
decision
requirement
constraint
risk
```

---

# 10. Prompt da extração

Não duplicar a lógica do `source-reader`.

`extractor.py` deve ler:

```text
.claude/agents/source-reader.md
```

remover o YAML frontmatter e utilizar suas regras como parte do system prompt.

Acrescentar apenas as regras específicas do batch:

```text
BATCH EXTRACTION MODE

Return only information explicitly supported by the transcript.

Prioritize knowledge that remains useful outside the immediate
conversation.

Ignore greetings, scheduling logistics, screen-sharing comments,
small talk, acknowledgements and repetitions unless they materially
affect a decision, requirement, risk or commitment.

Every substantive claim must contain a source locator.

Do not resolve entities against the wiki.
Do not infer external facts.
Do not synthesize across sources.
```

A diferença é importante:

```text
source-reader = epistemic rules
SourceExtraction = serialization contract
```

---

# 11. Compactação do output

O `source-reader` normal atualmente pede resumo de 3–5 parágrafos. 

Em batch:

```text
factual_summary <= ~180 palavras
```

e claims devem obedecer:

> Extrair informação reutilizável, não cada frase factual da reunião.

Excluir normalmente:

```text
"Bom dia."

"Conseguem ver minha tela?"

"Vamos começar."

"Marcamos outra conversa para terça?"
```

Incluir:

```text
"Foi aprovado migrar o serviço X para Kubernetes."

"O SLA máximo definido foi de 24 horas."

"A equipe Y será responsável pelo rollout."

"A migração depende da aprovação de segurança."
```

---

# 12. Message Batch A

Pseudoimplementação:

```python
requests = []

for source in sources:

    requests.append(
        Request(
            custom_id=source.custom_id,

            params={
                "model": config.extraction_model,

                "max_tokens": 6000,

                "system": [
                    {
                        "type": "text",
                        "text": static_source_reader_prompt,
                        "cache_control": {
                            "type": "ephemeral",
                            "ttl": "1h"
                        }
                    }
                ],

                "messages": [
                    {
                        "role": "user",
                        "content": build_transcript_message(source)
                    }
                ],

                "output_config": {
                    "format": {
                        "type": "json_schema",
                        "schema": SourceExtraction.model_json_schema()
                    }
                }
            }
        )
    )
```

A Message Batches API aceita até 100.000 requests ou 256 MB por batch, o que ocorrer primeiro. ([Claude Platform][3])

Internamente eu seria mais conservador:

```yaml
provider_limits:
  max_requests_per_batch: 5000
  max_payload_mb: 200
```

e dividiria automaticamente:

```text
logical batch
   ├── anthropic batch #1
   ├── anthropic batch #2
   └── anthropic batch #3
```

---

# 13. Prompt caching

O bloco estático:

```text
source-reader
+
taxonomia
+
batch rules
```

deve ser idêntico entre requests.

Utilizar:

```json
{
  "cache_control": {
    "type": "ephemeral",
    "ttl": "1h"
  }
}
```

A Anthropic recomenda considerar o cache de 1 hora para batches, já que o processamento assíncrono pode ultrapassar a janela padrão de cinco minutos. Cache e desconto de Batch podem ser combinados, embora os cache hits em batch sejam best-effort. ([Claude Platform][3])

---

# 14. Coleta de resultados

Comandos:

```bash
python3 scripts/batch_ingest.py submit <batch>
```

```bash
python3 scripts/batch_ingest.py status <batch>
```

```bash
python3 scripts/batch_ingest.py collect <batch>
```

ou:

```bash
python3 scripts/batch_ingest.py resume <batch>
```

Cada resultado é salvo imediatamente:

```text
staging/<batch>/extraction/<source_key>.json
```

Nunca manter todos os resultados em RAM.

A própria API recomenda processamento em streaming para resultados grandes. ([Claude Platform][3])

---

# 15. Política de retries

Resultado:

```text
succeeded
```

→ armazenar.

```text
errored / invalid_request
```

→ não repetir automaticamente; configuração ou conteúdo precisa ser corrigido.

```text
errored / server error
expired
```

→ incluir em retry batch.

```text
refusal
```

→ marcar `needs-review`.

```text
max_tokens
```

→ uma nova tentativa com limite maior.

No máximo:

```yaml
max_provider_retries: 2
```

Nunca criar loop infinito.

---

# 16. Transcrições extremamente grandes

Haiku 4.5 possui janela de contexto de 200k tokens atualmente. ([Claude Platform][2])

Definir um limite operacional menor:

```yaml
chunking:
  target_tokens: 100000
  overlap_tokens: 1500
```

Uma transcrição grande vira:

```text
meeting-X
 ├── meeting-X-part-001
 ├── meeting-X-part-002
 └── meeting-X-part-003
```

Cada parte produz claims.

Depois:

```text
merge_source_extraction()
```

faz:

* remoção de claims idênticos;
* remoção de near-duplicates;
* merge de entities;
* merge de concepts;
* merge de open questions.

Somente o resumo global exige uma chamada adicional barata sobre as **extrações**, não sobre a transcrição original inteira.

---

# 17. Normalização

Depois do Batch A:

```bash
python3 scripts/batch_ingest.py normalize <batch>
```

Fazer deterministicamente:

```text
Unicode normalization
trim
case folding para comparação
slugify
entity type validation
dedup exato
alias lookup
```

Não modificar texto original dos claims.

---

# 18. Construir índice de resolução

Carregar:

```text
wiki/concepts/
wiki/entities/
manifests/aliases.yml
```

Criar em memória:

```python
lookup = {
    normalized_name: target_slug
}
```

Exemplo:

```text
"ci&t"       → ci-and-t
"ci and t"   → ci-and-t
"ciandt"     → ci-and-t

"rag"        → retrieval-augmented-generation
```

O projeto já exige que os curators busquem páginas e aliases antes de criar duplicatas; aqui essa regra passa a ser aplicada primeiramente por código. 

---

# 19. Três classes de resolução

## A. Exact

```text
RAG → alias conhecido
```

Resultado automático.

## B. Clear fuzzy candidate

Por exemplo:

```text
Retrieval Augmented Generation
Retrieval-Augmented Generation
```

Pode ser resolvido deterministicamente acima de threshold conservador.

Sugestão:

```yaml
resolution:
  fuzzy_auto_threshold: 0.97
```

## C. Ambiguous

Exemplo:

```text
"Flow"

candidatos:
- flow-platform
- flow-framework
- workflow-engine
```

Somente estes casos vão para LLM.

---

# 20. Resolution Batch

Input extremamente pequeno:

```json
{
  "mention": {
    "kind": "concept",
    "name": "Flow"
  },

  "candidates": [
    {
      "slug": "flow-platform",
      "title": "...",
      "aliases": [],
      "abstract": "..."
    },
    {
      "slug": "flow-framework",
      "title": "...",
      "aliases": [],
      "abstract": "..."
    }
  ],

  "evidence": [
    "trecho da reunião..."
  ]
}
```

Output:

```json
{
  "action": "existing",
  "target_slug": "flow-platform",
  "canonical_name": "Flow",
  "alias_to_add": null,
  "confidence": "high"
}
```

ou:

```json
{
  "action": "new",
  "canonical_name": "...",
  "suggested_slug": "...",
  "confidence": "high"
}
```

ou:

```json
{
  "action": "defer",
  "confidence": "low"
}
```

`defer` nunca cria página automaticamente.

---

# 21. Group / Reduce

Depois da resolução:

```python
groups = {
    ("concept", "api-gateway"): [...],
    ("concept", "oauth"): [...],
    ("entity", "company-x"): [...],
}
```

Cada grupo contém:

```json
{
  "target": "api-gateway",

  "evidence": [
    {
      "claim_id": "meeting-001:c0017",
      "source_slug": "meeting-001",
      "text": "...",
      "locator": {}
    },
    {
      "claim_id": "meeting-037:c0004",
      "source_slug": "meeting-037",
      "text": "...",
      "locator": {}
    }
  ]
}
```

---

# 22. Curation Batch

Para página existente:

```text
existing page
+
new evidence bundle
+
curator rules
```

Para página nova:

```text
evidence bundle
+
page template
+
curator rules
```

Não pedir ao Sonnet para escrever o arquivo.

Pedir:

```text
PageMutationPlan
```

---

# 23. PageMutationPlan

Contrato:

```python
class ClaimAddition(BaseModel):
    text: str
    source_slug: str
    source_claim_id: str


class RelationAddition(BaseModel):
    target_slug: str
    relation_type: str


class Conflict(BaseModel):
    conflict_type: Literal[
        "direct",
        "partial",
        "different-data",
        "divergent-interpretation",
        "stale"
    ]

    existing_claim: str
    existing_source: str | None

    new_claim: str
    new_source: str

    explanation: str


class PageMutationPlan(BaseModel):

    page_type: Literal["concept", "entity"]

    action: Literal[
        "create",
        "update",
        "defer"
    ]

    slug: str
    title: str

    aliases_to_add: list[str]

    claims_to_add: list[ClaimAddition]

    relations_to_add: list[RelationAddition]

    conflicts: list[Conflict]

    proposed_open_questions: list[str]

    proposed_decisions: list[str]
```

Para `create`, incluir adicionalmente:

```text
abstract
definition/description
related concepts
related entities
```

---

# 24. Contradiction reviewer é absorvido pelo REDUCE

Hoje o `contradiction-reviewer` compara cada nova fonte contra as páginas relacionadas e não modifica a wiki diretamente. 

No batch, não devemos chamá-lo uma vez por source.

A mesma regra epistemológica passa a fazer parte do Curation Batch:

```text
existing api-gateway page
+
TODOS os novos claims de API Gateway
       ↓
1 contradiction evaluation
```

Isso detecta também contradições **entre transcrições do próprio lote**, coisa que fica mais difícil quando cada fonte é processada isoladamente.

---

# 25. Restrição crítica do mutation plan

No MVP, o LLM nunca pode pedir:

```text
delete claim
replace page
delete section
rename file
remove source
```

A operação é append-oriented.

Permitidas:

```text
CREATE page

ADD alias
ADD claim
ADD fact
ADD source
ADD relation
ADD conflict
ADD open question proposal

SET status = conflict
UPDATE updated
```

Isso reduz drasticamente risco de perda de conhecimento.

---

# 26. Source pages são deterministicamente renderizadas

O template de source existente já estabelece metadata, summary, key claims, quotes, entities, concepts, contradictions, pages updated e open questions. ([GitHub][5])

Portanto:

```python
render_source_page(
    extraction,
    resolutions,
    mutation_results
)
```

produz:

```markdown
---
type: source
status: draft
confidence: medium
...
---

# Architecture Weekly

## Bibliographic Metadata
...

## Summary
...

## Key Claims

1. A equipe decidiu ...
2. O SLA estabelecido ...

## Important Quotes
...

## Relevant Entities

- [[company-x]]

## Relevant Concepts

- [[api-gateway]]

## Contradictions

- Conflicts with [[api-gateway]]: ...

## Pages Updated

- [[api-gateway]]
- [[company-x]]

## Open Questions
...
```

Nenhum LLM adicional é necessário.

---

# 27. Update Plan global

Após curation:

```text
staging/<batch>/update-plan.json
```

Exemplo:

```json
{
  "batch_id": "...",

  "sources": {
    "create": 247,
    "update": 0
  },

  "concepts": {
    "create": 18,
    "update": 47,
    "defer": 3
  },

  "entities": {
    "create": 11,
    "update": 24,
    "defer": 2
  },

  "conflicts": [
    "api-timeout",
    "authorization-sla"
  ],

  "decision_proposals": [
    "migrate-api-gateway"
  ],

  "promotion_candidates": [
    "event-driven-architecture"
  ],

  "files": [...]
}
```

---

# 28. Optimistic locking

Durante `plan`, guardar:

```json
{
  "path": "wiki/concepts/api-gateway.md",
  "baseline_sha256": "..."
}
```

Antes de `apply`:

```python
if current_hash != baseline_hash:
    raise ConcurrentModificationError
```

Isso evita:

```text
batch planejado
       ↓
humano edita página
       ↓
batch sobrescreve edição humana
```

O arquivo é marcado:

```text
needs-replan
```

---

# 29. Single Writer

Somente:

```text
writer.py
```

pode modificar:

```text
wiki/**
manifests/sources.yml
```

Fluxo:

```text
update-plan
     ↓
temporary files
     ↓
validate temporary result
     ↓
atomic replace
```

O writer deve conhecer as estruturas das páginas; não fazer substituições arbitrárias por texto.

---

# 30. Index e log

Não deixar 247 workers alterarem:

```text
wiki/index.md
wiki/log.md
```

Após aplicar todo o lote:

```bash
python3 scripts/rebuild_index.py
```

O projeto já possui `rebuild_index.py` justamente como mecanismo determinístico para regeneração do índice. ([GitHub][6])

No log, uma única entrada:

```markdown
## 2026-08-07 — Batch ingest: architecture-transcripts

- Sources ingested: 247
- New concepts: 18
- Updated concepts: 47
- New entities: 11
- Updated entities: 24
- Conflicts detected: 2
- Deferred resolutions: 5
- Batch report: outputs/reports/batch-ingest-20260807-architecture-transcripts.md
```

Não criar 247 grandes entradas repetitivas.

---

# 31. manifests/sources.yml

Atualizar somente no final.

Uma transação:

```text
247 source registrations
       ↓
one YAML rewrite
```

Não:

```text
load → write
load → write
load → write
...
```

---

# 32. QA antes da escrita

`qa.py` deve bloquear `apply` se houver:

```text
invalid extraction schema
unknown entity type
claim pointing to missing source
missing locator em critical claim
duplicate target slugs
invalid page type
mutation pointing to unknown target
broken source relationship
unresolved provider error
```

Threshold default:

```yaml
quality:
  require_all_extractions_valid: true

  critical_claim_locator_rate: 1.0

  minimum_claim_locator_rate: 0.95

  allow_deferred_resolution: true

  allow_unresolved_provider_errors: false
```

---

# 33. QA por amostragem

Além das verificações determinísticas:

```yaml
quality:
  sample_rate: 0.10
  min_sample_size: 20
  max_sample_size: 100
```

Selecionar deterministicamente pelo hash do source para que a amostra seja reproduzível.

Gerar:

```text
outputs/reports/
batch-ingest-<batch-id>.md
```

contendo exemplos de:

```text
claim
locator
trecho original
source
target page
```

para revisão rápida.

---

# 34. Validation pós-apply

Executar:

```bash
python3 scripts/validate_frontmatter.py
python3 scripts/validate_links.py
python3 scripts/find_orphans.py
python3 scripts/rebuild_index.py
```

O fluxo atual já considera frontmatter e links checks obrigatórios após ingestão e recomenda wiki-lint após ingestões em lote. 

Depois:

```text
/wiki-lint
```

continua sendo a revisão semântica/global.

---

# 35. Rollback

Antes do `apply` registrar:

```text
baseline git HEAD
```

O batch **não faz git commit automaticamente**.

Depois do apply:

```bash
git diff --stat
git diff
```

O próprio projeto já exige revisão do diff antes de commits de ingestões que toquem muitos arquivos. ([GitHub][5])

Se algo estiver errado, o usuário continua tendo Git como mecanismo de rollback.

---

# 36. CLI

Interface principal:

```bash
python3 scripts/batch_ingest.py scan raw/transcripts/Q3
```

retorna:

```text
Discovered:             258
Already ingested:         9
Changed sources:           2
Ready:                   247
Potential pairs:           3
Ambiguous pairs:           1
```

Depois:

```bash
python3 scripts/batch_ingest.py submit staging/<batch>
```

Depois:

```bash
python3 scripts/batch_ingest.py status staging/<batch>
```

Depois:

```bash
python3 scripts/batch_ingest.py resume staging/<batch>
```

`resume` executa automaticamente a próxima etapa possível.

Fluxo completo interativo:

```bash
python3 scripts/batch_ingest.py run raw/transcripts/Q3
```

---

# 37. Dry-run obrigatório

O comando:

```bash
python3 scripts/batch_ingest.py plan staging/<batch>
```

não toca na wiki.

Mostra:

```text
Batch: architecture-transcripts

247 sources will be created

18 concepts:
  + 8 create
  ~ 10 update

13 entities:
  + 4 create
  ~ 9 update

2 pages will become conflict

5 ambiguous mentions deferred

Estimated files:
  create: 259
  update: 21
```

Somente:

```bash
python3 scripts/batch_ingest.py apply staging/<batch>
```

efetua alterações.

---

# 38. Skill Claude Code

Adicionar:

```text
.claude/skills/wiki-ingest-batch/SKILL.md
```

Responsabilidade do skill:

```text
1. executar scan;
2. apresentar preflight;
3. executar ou retomar batch;
4. apresentar update-plan;
5. não editar wiki diretamente;
6. chamar apply somente após review;
7. apresentar QA report;
8. sugerir /wiki-lint.
```

O skill funciona como UX.

A engine Python continua sendo a autoridade operacional.

---

# 39. Configuração

`manifests/batch-ingest.yml`:

```yaml
schema_version: "1"

models:
  extraction: claude-haiku-4-5-20251001
  resolution: claude-sonnet-5
  curation: claude-sonnet-5

tokens:
  extraction_max_output: 6000
  resolution_max_output: 1500
  curation_max_output: 6000

cache:
  enabled: true
  ttl: 1h

provider_batch:
  max_requests: 5000
  max_payload_mb: 200
  max_retries: 2

chunking:
  enabled: true
  target_tokens: 100000
  overlap_tokens: 1500

resolution:
  fuzzy_auto_threshold: 0.97
  max_candidates: 5

quality:
  sample_rate: 0.10
  min_sample_size: 20
  max_sample_size: 100

  critical_claim_locator_rate: 1.0
  minimum_claim_locator_rate: 0.95

apply:
  require_clean_git: true
  optimistic_locking: true
```

---

# 40. Privacidade e classificação

Antes do submit:

```text
classification:
public
internal
confidential
restricted
```

Sugestão de comportamento:

```text
public      → permitido

internal    → permitido com configuração explícita

confidential
restricted  → bloquear API externa por default
```

Para liberar:

```bash
--allow-external-processing
```

Isso formaliza a regra de segurança já existente no vault, que exige atenção especial para fontes confidenciais ou contendo PII. ([GitHub][5])

---

# 41. Custos

Todo o MAP deve usar Message Batches.

A Anthropic cobra atualmente 50% da tarifa normal para Message Batches. Haiku 4.5 em batch custa atualmente US$0,50/MTok de input e US$2,50/MTok de output. ([Claude Platform][3])

O Batch B também deve usar Message Batches.

A principal redução, entretanto, não vem apenas do preço do provider.

Vem de:

```text
N transcripts
×
M concepts repetidos
```

virar:

```text
N cheap extractions
+
U unique affected pages
```

onde:

```text
U << N × M
```

quando as reuniões pertencem aos mesmos projetos e domínios.

---

# 42. O que NÃO fazer no batch

Não fazer:

```text
LLM escrevendo arquivos diretamente

um concept-curator por conceito por source

contradiction reviewer por transcript

rebuild index por transcript

wiki-lint por transcript

source page gerada por outro LLM

todo o vault enviado ao source-reader

semantic retrieval sobre raw como fonte final

auto-resolução de ambiguidades de baixa confiança

auto-criação de ADR

auto-promoção draft → active
```

Decisões e promoção continuam sendo propostas, em coerência com as regras atuais do `/wiki-ingest`. 

---

# 43. Definition of Done do MVP

O MVP está pronto quando:

### Functional

* [ ] processa 100+ transcripts em um batch;
* [ ] suporta retomada;
* [ ] utiliza Message Batches API;
* [ ] produz JSON estruturado;
* [ ] não grava em wiki durante extraction;
* [ ] resolve aliases conhecidos deterministicamente;
* [ ] agrupa evidências por target page;
* [ ] produz PageMutationPlan;
* [ ] usa single writer;
* [ ] atualiza sources.yml;
* [ ] atualiza log;
* [ ] reconstrói index.

### Quality

* [ ] 100% dos critical claims têm locator;
* [ ] nenhum factual claim inserido fica sem source;
* [ ] conflitos não são sobrescritos;
* [ ] ambiguous resolution pode ser deferred;
* [ ] existing claims nunca são removidos pelo batch.

### Reliability

* [ ] reexecutar `collect` não duplica resultados;
* [ ] reexecutar `plan` produz mesmo plano com mesmos inputs;
* [ ] reexecutar `apply` não duplica claims;
* [ ] mudança concorrente numa página aborta aquela mutation;
* [ ] erro numa source não invalida as outras;
* [ ] resultados fora de ordem são corretamente associados via `custom_id`.

### Safety

* [ ] raw nunca é modificado;
* [ ] staging está gitignored;
* [ ] API key nunca é registrada;
* [ ] apply pode exigir working tree limpa;
* [ ] nenhum git commit automático.

---

# 44. Teste de aceitação principal

Fixture:

```text
10 transcripts

3 mencionam API Gateway
5 mencionam OAuth
4 mencionam Company X

2 transcripts contradizem timeout:
  30 segundos
  60 segundos

2 utilizam "RAG"
1 utiliza "Retrieval Augmented Generation"

1 contém uma nova entidade

1 arquivo está duplicado
```

Resultado esperado:

```text
9 sources ingeridas
1 skipped duplicate

1 página RAG
não duas

API Gateway atualizado uma vez

OAuth atualizado uma vez

Company X atualizada uma vez

timeout marcado conflict

nova entidade criada

todos claims citados

1 único rebuild_index

1 único batch log entry
```

Esse fixture deveria tornar-se o primeiro golden test do pipeline.

---

# 45. Fases de implementação

## PR 1 — Infraestrutura

Implementar:

```text
pyproject.toml
batch config
models.py
state.py
scanner.py
CLI scan
hash/dedup
staging
.gitignore
tests de scanner/dedup
```

Sem API ainda.

---

## PR 2 — MAP

Implementar:

```text
extractor.py
anthropic_batch.py
structured output
submit
status
collect
resume
retry
chunking básico
```

Resultado:

```text
raw → SourceExtraction JSON
```

Nenhuma wiki alterada.

---

## PR 3 — Resolution

Implementar:

```text
normalizer.py
local alias index
exact resolution
fuzzy candidates
resolution batch
defer
```

Resultado:

```text
mentions → canonical targets
```

---

## PR 4 — REDUCE

Implementar:

```text
grouper.py
curator.py
PageMutationPlan
conflict detection
decision proposals
promotion candidates
```

Resultado:

```text
extractions → update-plan.json
```

---

## PR 5 — Writer

Implementar:

```text
renderer.py
writer.py
optimistic locking
source page generation
concept/entity mutations
sources.yml
wiki/log.md
rebuild_index
```

---

## PR 6 — QA + Claude UX

Implementar:

```text
qa.py
batch report
golden tests
/wiki-ingest-batch
README
CLAUDE.md
```

---

# Arquitetura final

```text
                           myWikiLLM

                              RAW
                               │
                               │ immutable
                               ▼
                    ┌─────────────────────┐
                    │ Batch Extraction    │
                    │ Haiku / Message API │
                    └──────────┬──────────┘
                               │
                         SourceExtraction
                               │
                               ▼
                    ┌─────────────────────┐
                    │ Deterministic       │
                    │ normalization       │
                    │ + entity resolution │
                    └──────────┬──────────┘
                               │
                         ambiguous only
                               ▼
                    ┌─────────────────────┐
                    │ Semantic resolver   │
                    │ Sonnet              │
                    └──────────┬──────────┘
                               │
                               ▼
                       GROUP BY TARGET
                               │
                               ▼
                    ┌─────────────────────┐
                    │ Batch Curation      │
                    │ Sonnet / Message API│
                    └──────────┬──────────┘
                               │
                        PageMutationPlan
                               │
                               ▼
                     ┌──────────────────┐
                     │ QA + Dry Run     │
                     └────────┬─────────┘
                              │
                              ▼
                     ┌──────────────────┐
                     │ Single Writer    │
                     │ deterministic    │
                     └────────┬─────────┘
                              │
                 ┌────────────┼────────────┐
                 ▼            ▼            ▼
             wiki/*      sources.yml    log/index
                 │
                 ▼
          validators + wiki-lint
```

A mudança conceitual mais importante é esta:

**`/wiki-ingest` continua source-centric.**

**`/wiki-ingest-batch` passa a ser evidence-centric.**

O primeiro pergunta:

```text
"O que faço com este documento?"
```

O segundo pergunta:

```text
"Que novas evidências existem neste lote,
e quais unidades de conhecimento elas alteram?"
```

Essa é a diferença que permite aumentar o volume em uma ou duas ordens de grandeza sem degradar proporcionalmente custo e qualidade.

Eu implementaria exatamente nessa ordem de PRs. **PR 1 + PR 2 já entregam valor imediatamente**, porque resolvem a ingestão massiva e criam o IR (`SourceExtraction`) sem ainda assumir o risco de modificar a wiki. PRs 3–5 então transformam essa extração em compilação batch completa. A API de batches suporta o desenho: requests independentes, structured outputs em batch, resultados correlacionados por `custom_id` e desconto de 50%. ([Claude Platform][3])

O ponto que eu manteria como requisito não negociável é o `update-plan.json`: **nenhum resultado direto do modelo deve chegar à wiki sem passar por esse contrato intermediário e pelo writer determinístico**. Isso é o que fará o batch ser não apenas barato, mas seguro e reproduzível.

[1]: https://github.com/GiulSposito/myWikiLLM/blob/main/CLAUDE.md?utm_source=chatgpt.com "myWikiLLM/CLAUDE.md at main · GiulSposito/myWikiLLM · GitHub"
[2]: https://platform.claude.com/docs/en/about-claude/models/overview "Models overview - Claude Platform Docs"
[3]: https://platform.claude.com/docs/en/build-with-claude/batch-processing "Batch processing - Claude Platform Docs"
[4]: https://platform.claude.com/docs/en/build-with-claude/structured-outputs "Structured outputs - Claude Platform Docs"
[5]: https://github.com/GiulSposito/myWikiLLM/blob/main/CLAUDE.md "myWikiLLM/CLAUDE.md at main · GiulSposito/myWikiLLM · GitHub"
[6]: https://github.com/GiulSposito/myWikiLLM/compare/main%40%7B1day%7D...main.diff?utm_source=chatgpt.com "GitHub"
