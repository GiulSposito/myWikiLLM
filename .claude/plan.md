# Plano: Auditoria e Otimização do wiki-ingest

## Contexto

wiki-ingest é um fluxo LLM-driven (não Python scripts): os agentes fazem leituras e escritas diretas via tool calls. wiki-ingest-batch é um pipeline Python com scripts determinísticos. A questão é o que do batch pode ser incorporado sem perder qualidade ou mudar a natureza do fluxo.

---

## Achados

### 1. `manifests/aliases.yml` não é consultado pelos curadores — BUG QUALIDADE

**Arquivos:** `entity-curator.md`, `concept-curator.md`

O batch pipeline carrega `aliases.yml` via `load_alias_index()` **antes** de decidir se uma entidade/conceito é novo ou existente. Assim, "Retrieval-Augmented Generation" resolve para "retrieval-augmented-generation" mesmo sem estar no frontmatter de nenhum arquivo.

Os curadores do wiki-ingest apenas buscam em `wiki/concepts/` e `wiki/entities/` por nome e aliases no frontmatter. Se o nome canônico só está em `aliases.yml` (não em nenhum arquivo), **o curador cria uma página duplicada**.

**Correção:** adicionar passo explícito nos curadores: "antes de criar nova página, checar `manifests/aliases.yml` para ver se o nome é alias de um slug já existente."

---

### 2. Dedup em Step 1 não detecta "changed source" (SHA256) — QUALIDADE

**Arquivo:** `SKILL.md:Step 1`

O dedup check atual apenas verifica se o slug/path já está em `sources.yml`. O batch pipeline adiciona `sha256:` no registro de cada fonte e detecta quando o arquivo mudou (mesmo path, hash diferente) — emitindo um aviso explícito.

O wiki-ingest não faz isso: se o usuário re-ingesta um transcript modificado, o Step 1 apenas diz "já foi ingerido" sem indicar que o conteúdo mudou.

**Correção:** Step 1 do SKILL.md: instruir a verificar o campo `sha256:` em `sources.yml` comparando com `python3 -c "import hashlib; print(hashlib.sha256(open('<path>','rb').read()).hexdigest())"`. Se hash divergir: reportar como "changed source" (não apenas "already ingested").

---

### 3. Step 10 ainda usa dois scripts sequenciais — PARALELISMO

**Arquivo:** `SKILL.md:Step 10`

```
python3 scripts/validate_frontmatter.py
python3 scripts/validate_links.py
```

Já criamos `scripts/wiki_lint.py` que roda os dois (+ `find_orphans.py`) em paralelo.

**Correção:** trocar por `python3 scripts/wiki_lint.py`.

---

### 4. Steps 6 e 7 são sequenciais mas poderiam ser paralelos — PARALELISMO

**Arquivo:** `SKILL.md:Steps 6, 7`

Step 6 (detectar decisions/patterns) e Step 7 (contradiction-reviewer) ambos trabalham sobre os dados já extraídos no Step 2 e a source page criada no Step 3. Nenhum depende do output do outro.

O SKILL.md não instrui explicitamente rodá-los em paralelo — são apresentados como sequenciais.

**Correção:** adicionar nota explícita: "Steps 6 e 7 podem ser executados em paralelo."

---

### 5. Geração de slug sem função canônica — QUALIDADE

**Arquivo:** `SKILL.md:Step 3`, curators

O SKILL.md diz `slug = lowercase, hyphens, no special chars` mas não especifica como tratar caracteres acentuados. O batch tem `slugify()` em `scripts/batch/normalizer.py` que faz NFD decomposition para `"ação" → "acao"`, `"São Paulo" → "sao-paulo"`.

Sem isso, o agente pode gerar slugs inconsistentes: uma fonte em português pode gerar `acao.md` numa run e `ao.md` em outra dependendo de como o LLM interpreta "no special chars".

**Correção:** SKILL.md Step 3 e curadores: referenciar o comando canônico de geração de slug:
```bash
python3 -c "from scripts.batch.normalizer import slugify; print(slugify('Texto com Acentos'))"
```

---

## Mudanças Planejadas

| # | Arquivo | Mudança |
|---|---------|---------|
| 1 | `entity-curator.md` | Adicionar passo: checar `manifests/aliases.yml` antes de criar nova página |
| 2 | `concept-curator.md` | Idem |
| 3 | `SKILL.md` Step 1 | Adicionar SHA256 check para changed-source detection |
| 4 | `SKILL.md` Step 10 | Substituir dois scripts por `python3 scripts/wiki_lint.py` |
| 5 | `SKILL.md` Steps 6+7 | Marcar explicitamente como paralelizáveis |
| 6 | `SKILL.md` Step 3 + curadores | Referenciar `slugify()` do batch para geração canônica de slugs |

## O que NÃO está sendo tocado

- Fluxo de extração (source-reader agent) — bem definido e separado
- `prepare_transcript()` / `inject_line_numbers()` — útil só no path assíncrono do batch; wiki-ingest usa o LLM para ler diretamente
- Templates de página (`page-templates.md`) — corretos e completos
- Steps 4+5 — já são explicitamente paralelos no SKILL.md
- Agente `contradiction-reviewer` — bem definido
