Sim. Depois de olhar as fontes e implementações, eu faria **um modelo híbrido**:

1. **Obsidian como interface humana** para navegação, graph view, backlinks, leitura e edição eventual.
2. **GitHub como versionamento/auditoria** do vault.
3. **Claude Code como agente mantenedor da wiki**, com `CLAUDE.md`, skills, subagents e comandos.
4. **Plugins Obsidian somente onde agregam**, sem depender de um plugin mágico para tudo.

A recomendação principal seria: **começar com Claude Code + vault GitHub + Obsidian**, e só depois avaliar se vale ativar o plugin “Karpathy LLM Wiki” dentro do Obsidian.

---

## 1. O que já existe pronto

### 1.1 Karpathy LLM Wiki Plugin para Obsidian

Existe um plugin no marketplace chamado **Karpathy LLM Wiki**. Ele implementa diretamente a ideia de transformar notas em uma wiki estruturada com `wiki/sources`, `wiki/entities`, `wiki/concepts`, `wiki/index.md` e `wiki/log.md`. O plugin suporta ingestão de arquivo atual, pasta, múltiplos arquivos, query sobre a wiki e lint para duplicatas, links mortos, páginas órfãs e contradições. ([Obsidian Community][1])

Pontos positivos:

* É o caminho mais rápido para experimentar.
* Já tem comandos de ingestão, query e lint.
* Mantém os arquivos originais sem modificar.
* Usa links Obsidian `[[...]]`.
* Tem uma filosofia alinhada ao Karpathy: wiki estruturada primeiro, não RAG vetorial tradicional. ([Obsidian Community][1])

Pontos de atenção:

* Ele é opinionado: gera uma estrutura específica.
* Você fica mais dependente da evolução do plugin.
* Para um caso corporativo/consultivo, pode faltar governança fina: taxonomia própria, templates por domínio, aprovação humana, regras de confidencialidade e pipelines de validação.
* Ele afirma usar PageRank sobre o grafo de links em vez de embeddings, o que é elegante, mas pode ser limitado quando você precisa buscar trechos muito específicos ou documentos pouco conectados. ([GitHub][2])

Minha avaliação: **bom para protótipo e aprendizado**, mas eu não começaria um sistema estratégico dependendo só dele.

---

### 1.2 Ar9av/obsidian-wiki

Esse é um dos projetos mais interessantes. O repositório **Ar9av/obsidian-wiki** se posiciona como um framework para agentes construírem e manterem uma “digital brain” no Obsidian usando o padrão LLM Wiki. Ele parece mais maduro que muitos projetos menores: tem estrutura para agentes, skills, scripts, CLI, sincronização GitHub, browser capture, análise de grafo e suporte a diferentes ambientes de agente como Claude, Cursor, Windsurf, Kiro e outros. ([GitHub][3])

Pontos positivos:

* Mais próximo do que você quer: **Claude Code + Obsidian + GitHub**.
* Mais flexível do que um plugin fechado.
* Já pensa em skills, comandos, lint, query e update.
* Tem sinais de atividade recente e adoção relevante. ([GitHub][3])

Pontos de atenção:

* Pode trazer complexidade demais no início.
* Precisa avaliar a qualidade dos scripts e padrões antes de usar diretamente.
* Como qualquer framework novo, pode mudar rápido e quebrar convenções.

Minha avaliação: **é o candidato mais forte para servir de referência técnica**, mas eu começaria copiando o padrão arquitetural, não necessariamente adotando tudo de imediato.

---

### 1.3 kfchou/wiki-skills

O projeto **wiki-skills** implementa o padrão como um conjunto de skills para Claude Code. A proposta é justamente dar ao agente uma disciplina de manutenção de wiki: criar, atualizar, consultar e enriquecer uma base Markdown persistente em vez de reprocessar documentos do zero a cada pergunta. ([GitHub][4])

Pontos positivos:

* Muito alinhado com Claude Code.
* Mais leve que um app completo.
* Bom para padronizar operações como `/wiki-ingest`, `/wiki-query`, `/wiki-lint`.
* Funciona bem se você quer manter o vault como arquivos simples.

Pontos de atenção:

* Skills ajudam o comportamento do agente, mas não substituem validações determinísticas.
* Você ainda precisará de scripts para checar links quebrados, frontmatter inválido, duplicatas e consistência de índices.

Minha avaliação: **excelente ponto de partida para o seu caso**.

---

### 1.4 lucasastorian/llmwiki

O projeto **lucasastorian/llmwiki** é mais produto/aplicação: tem backend FastAPI, MCP server, interface Next.js e possibilidade de self-hosting. A proposta é capturar documentos, conectar Claude e gerar uma wiki persistente. ([GitHub][5])

Pontos positivos:

* Mais completo como aplicação.
* Tem MCP.
* Pode ser útil se você quiser virar isso em produto multiusuário.

Pontos de atenção:

* É mais pesado que o necessário para um vault pessoal/profissional no Obsidian.
* Pode introduzir Supabase, backend, webapp e deploy antes da hora.
* Para começar rápido com Obsidian + GitHub, é overengineering.

Minha avaliação: **bom para estudar arquitetura de produto**, mas eu não usaria como base inicial.

---

### 1.5 SamurAIGPT/llm-wiki-agent

Esse projeto é mais simples: um agente/skill onde você coloca documentos em `raw/` e o agente ingere, extrai conhecimento e mantém uma wiki interligada. ([GitHub][6])

Pontos positivos:

* Simples.
* Fácil de entender.
* Bom como referência de fluxo mínimo.

Pontos de atenção:

* Menos robusto.
* Provavelmente exigirá ajustes para taxonomia, qualidade, segurança e versionamento.

Minha avaliação: **bom para inspiração**, não como plataforma principal.

---

### 1.6 ScrapingArt/Karpathy-LLM-Wiki-Stack e gists de setup

O repositório **Karpathy-LLM-Wiki-Stack** é mais um blueprint técnico do que uma aplicação. Ele propõe arquitetura de três camadas: `raw/`, `wiki/` e `CLAUDE.md`, além das operações centrais `ingest`, `query` e `lint`. ([GitHub][7])

O gist de setup também é bem prático: recomenda configurar Obsidian CLI, criar estrutura `sources/`, `entities/`, `concepts/`, `synthesis/`, manter fontes brutas imutáveis, atualizar `index.md` e `log.md`, usar wikilinks e registrar contradições explicitamente. ([Gist][8])

Minha avaliação: **excelente como documento de referência para criar seu próprio `CLAUDE.md`**.

---

## 2. Minha recomendação de stack

Eu usaria esta stack:

| Camada                 | Ferramenta recomendada            | Por quê                                                     |
| ---------------------- | --------------------------------- | ----------------------------------------------------------- |
| Interface humana       | Obsidian                          | Graph view, backlinks, Markdown local, leitura confortável  |
| Versionamento          | Git + GitHub                      | Auditoria, diff, rollback, branch, PR                       |
| Agente                 | Claude Code                       | Lê/escreve arquivos, executa scripts, mantém wiki           |
| Regras do agente       | `CLAUDE.md`                       | Schema operacional da wiki                                  |
| Automação do agente    | Claude Code skills/slash commands | Padronizar ingest/query/lint                                |
| Subtarefas             | Claude Code subagents             | Separar pesquisa, lint, extração, revisão                   |
| Hooks                  | Claude Code hooks                 | Bloquear alterações perigosas, validar Markdown, rodar lint |
| Captura web            | Obsidian Web Clipper              | Salvar páginas como Markdown durável/offline                |
| Git dentro do Obsidian | Obsidian Git                      | Commit/pull/push pelo Obsidian                              |
| Relatórios internos    | Dataview                          | Tabelas por frontmatter, status, fontes, páginas órfãs      |
| Busca auxiliar         | ripgrep / scripts / qmd opcional  | Busca local rápida                                          |

O Obsidian Web Clipper é oficial e salva conteúdo web em Markdown durável para o vault. ([GitHub][9]) O plugin Obsidian Git integra commit, pull e push diretamente no vault. ([GitHub][10]) O Dataview permite tratar o vault como uma base consultável por metadados/frontmatter. ([GitHub][11])

---

## 3. Desenho do vault no GitHub

Eu criaria um repositório chamado, por exemplo:

```text
llm-wiki-vault
```

Com esta estrutura:

```text
llm-wiki-vault/
  CLAUDE.md
  README.md
  .gitignore

  .claude/
    settings.json
    commands/
      wiki-ingest.md
      wiki-query.md
      wiki-lint.md
      wiki-review.md
      wiki-map.md
    agents/
      source-reader.md
      concept-curator.md
      entity-curator.md
      contradiction-reviewer.md
      wiki-linter.md

  .obsidian/
    app.json
    community-plugins.json
    plugins/

  raw/
    articles/
    papers/
    slides/
    transcripts/
    repos/
    images/
    web-clippings/

  wiki/
    index.md
    log.md
    overview.md

    sources/
    entities/
    concepts/
    projects/
    patterns/
    decisions/
    synthesis/
    comparisons/
    questions/

  outputs/
    reports/
    maps/
    briefings/
    presentations/

  scripts/
    validate_frontmatter.py
    validate_links.py
    rebuild_index.py
    find_orphans.py
    extract_pdf_text.py
    ingest_manifest.py

  manifests/
    sources.yml
    taxonomy.yml
    aliases.yml
```

A separação mais importante é:

```text
raw/   = fonte bruta, imutável
wiki/  = conhecimento compilado pelo LLM
outputs/ = artefatos derivados
CLAUDE.md = constituição operacional do sistema
```

Essa estrutura segue o padrão recorrente nas referências: fontes brutas imutáveis, wiki gerada em Markdown, índice/log sempre atualizados e um arquivo de schema/instrução que disciplina o agente. ([Starmorph AI Web Development Blog][12])

---

## 4. Como implementar com Claude Code

### Passo 1 — Criar o vault/repo

No terminal:

```bash
mkdir llm-wiki-vault
cd llm-wiki-vault
git init

mkdir -p raw/{articles,papers,slides,transcripts,repos,images,web-clippings}
mkdir -p wiki/{sources,entities,concepts,projects,patterns,decisions,synthesis,comparisons,questions}
mkdir -p outputs/{reports,maps,briefings,presentations}
mkdir -p scripts manifests .claude/commands .claude/agents

touch README.md CLAUDE.md wiki/index.md wiki/log.md wiki/overview.md
```

Depois conecte ao GitHub:

```bash
git add .
git commit -m "Initialize LLM Wiki vault"
git branch -M main
git remote add origin git@github.com:SEU_USUARIO/llm-wiki-vault.git
git push -u origin main
```

---

### Passo 2 — Abrir o diretório no Claude Code

Dentro do repo:

```bash
claude
```

A partir daí, o Claude Code deve operar **dentro do vault**.

O ponto mais importante é o `CLAUDE.md`. A documentação atual do Claude Code trata configurações, plugins, hooks, skills e MCP em escopos de usuário/projeto/local, e o escopo de projeto é apropriado para padronizar comportamento dentro de um repositório. ([Claude][13])

---

## 5. O `CLAUDE.md` mínimo

Eu colocaria algo assim no `CLAUDE.md`:

```markdown
# LLM Wiki Operating Manual

You are the knowledge compiler for this Obsidian vault.

## Architecture

- `raw/` contains immutable source material.
- `wiki/` contains LLM-generated knowledge pages.
- `outputs/` contains derived reports, maps and deliverables.
- `manifests/` contains controlled vocabularies, taxonomies and ingestion manifests.
- `scripts/` contains deterministic validation utilities.

Never modify files under `raw/` unless explicitly instructed.

## Core Operations

### Ingest

When ingesting a source:
1. Read the source.
2. Create or update one page under `wiki/sources/`.
3. Identify entities and update `wiki/entities/`.
4. Identify concepts and update `wiki/concepts/`.
5. Identify projects, patterns, decisions or synthesis pages when relevant.
6. Add wikilinks using `[[...]]`.
7. Update `wiki/index.md`.
8. Append an entry to `wiki/log.md`.
9. Report changed files and unresolved questions.

### Query

When answering a question:
1. Search `wiki/index.md`.
2. Read relevant pages.
3. Follow important backlinks.
4. Use source pages for evidence.
5. Answer with references to wiki pages.
6. If the answer reveals reusable insight, propose writing it to `wiki/questions/` or `wiki/synthesis/`.

### Lint

When linting:
1. Find orphan pages.
2. Find dead wikilinks.
3. Find duplicate concepts.
4. Find stale low-confidence claims.
5. Find contradictions.
6. Save results to `outputs/reports/wiki-lint-YYYY-MM-DD.md`.

## Page Rules

Every generated page must include YAML frontmatter:

type:
status:
confidence:
created:
updated:
sources:
aliases:
tags:

## Human Review

For large edits:
- Prefer proposing a diff before modifying many files.
- Never silently overwrite a conflicting claim.
- Record contradictions explicitly.
```

Esse arquivo é mais importante que qualquer plugin. A literatura prática sobre o padrão reforça que o `CLAUDE.md` funciona como schema e “manual operacional” do agente. ([Starmorph AI Web Development Blog][12])

---

## 6. Criar comandos no Claude Code

Você pode criar comandos em `.claude/commands/`.

### `.claude/commands/wiki-ingest.md`

```markdown
# Wiki Ingest

Ingest the source(s) requested by the user.

Rules:
- Never modify `raw/`.
- Create or update `wiki/sources/`.
- Update relevant `wiki/entities/`, `wiki/concepts/`, `wiki/projects/`, `wiki/patterns/`, `wiki/decisions/`, and `wiki/synthesis/`.
- Use Obsidian wikilinks.
- Update `wiki/index.md`.
- Append to `wiki/log.md`.
- Run validation scripts when available.
- Summarize changed files at the end.
```

### `.claude/commands/wiki-query.md`

```markdown
# Wiki Query

Answer the user's question using the compiled wiki.

Steps:
1. Search `wiki/index.md`.
2. Search `wiki/` for relevant pages.
3. Read the most relevant pages.
4. Follow key wikilinks if needed.
5. Synthesize the answer.
6. Cite wiki page paths.
7. Suggest whether the answer should become a permanent page.
```

### `.claude/commands/wiki-lint.md`

```markdown
# Wiki Lint

Run a knowledge health check.

Check:
- Dead wikilinks
- Orphan pages
- Duplicate concepts
- Missing aliases
- Pages without sources
- Stale pages
- Contradictions
- Broken frontmatter

Save the report to `outputs/reports/wiki-lint-YYYY-MM-DD.md`.
```

A própria documentação recente do Claude Code recomenda extensões como skills, subagents e hooks para encapsular fluxos repetíveis; subagents são úteis quando uma tarefa lateral poderia poluir o contexto principal. ([Claude][14])

---

## 7. Subagents recomendados

Eu criaria subagents simples:

```text
.claude/agents/
  source-reader.md
  concept-curator.md
  entity-curator.md
  contradiction-reviewer.md
  wiki-linter.md
```

### `source-reader.md`

Responsabilidade:

```markdown
Read raw source material and produce factual source summaries.
Do not interpret beyond the source.
Extract claims, definitions, named entities, dates, references and uncertainties.
```

### `concept-curator.md`

Responsabilidade:

```markdown
Maintain concept pages.
Merge duplicate concepts.
Add aliases.
Connect related concepts.
Flag uncertainty.
```

### `contradiction-reviewer.md`

Responsabilidade:

```markdown
Compare new claims with existing wiki pages.
Identify conflicts, outdated claims or competing interpretations.
Never resolve contradictions silently.
```

Isso endereça um problema real citado em discussões do próprio gist: agentes podem desperdiçar tokens relendo manifests, índices e fontes repetidamente; uma estratégia melhor é separar busca/leitura em subagents e manter o agente principal para orquestração e decisão. ([Gist][15])

---

## 8. Scripts determinísticos

Eu não deixaria tudo na mão do LLM. Criaria scripts simples em Python.

### `validate_frontmatter.py`

Verifica se toda página em `wiki/` tem:

```yaml
type:
status:
confidence:
created:
updated:
sources:
aliases:
tags:
```

### `validate_links.py`

Verifica se todo `[[wikilink]]` aponta para uma página existente.

### `find_orphans.py`

Lista páginas sem links de entrada.

### `rebuild_index.py`

Gera `wiki/index.md` a partir do frontmatter das páginas.

Esse é um ponto crítico: **LLM é bom para síntese; script é melhor para consistência mecânica**. Eu usaria o Claude para curadoria e os scripts para validação.

---

## 9. Plugins Obsidian que eu instalaria

### Essenciais

| Plugin                   | Uso                                                 |
| ------------------------ | --------------------------------------------------- |
| Obsidian Git             | Commit, pull e push do vault pelo Obsidian          |
| Dataview                 | Views de páginas por tipo, status, confiança, fonte |
| Obsidian Web Clipper     | Capturar páginas web como Markdown                  |
| Karpathy LLM Wiki Plugin | Opcional para experimentar ingest/query/lint pronto |

O plugin Obsidian Git é bastante usado e aparece no marketplace com milhões de downloads, enquanto o Dataview também é um dos plugins mais populares para consultar metadados do vault. ([Obsidian Community][16])

### Úteis, mas opcionais

| Plugin     | Uso                                                                     |
| ---------- | ----------------------------------------------------------------------- |
| Templater  | Templates avançados                                                     |
| Excalidraw | Mapas visuais                                                           |
| Canvas     | Mapas conceituais nativos                                               |
| Omnisearch | Busca melhorada                                                         |
| Linter     | Formatação Markdown                                                     |
| Tasks      | Gestão de pendências                                                    |
| Bases      | Views estruturadas, se você estiver usando versões recentes do Obsidian |

---

## 10. Como usar o plugin Karpathy LLM Wiki no seu desenho

Eu não misturaria tudo de cara.

Faria assim:

### Fase A — Vault manual com Claude Code

Use:

```text
raw/
wiki/
CLAUDE.md
.claude/commands/
scripts/
GitHub
```

### Fase B — Instalar o plugin Karpathy LLM Wiki em um branch

Crie uma branch:

```bash
git checkout -b experiment/karpathy-plugin
```

Instale o plugin e teste com 5 a 10 fontes.

Compare:

```text
1. Qualidade das páginas
2. Nomes de conceitos
3. Links criados
4. Controle de fontes
5. Custo/token
6. Capacidade de evitar duplicatas
7. Capacidade de lidar com português/inglês
8. Facilidade de customizar taxonomia
```

### Fase C — Decidir

Minha hipótese:

* Para wiki pessoal: plugin pode bastar.
* Para wiki profissional/consultoria: Claude Code + schema próprio vence.
* Para produto multiusuário: estudar `lucasastorian/llmwiki`.

---

## 11. Modelo de ingestão recomendado

Eu faria ingestão em dois modos.

### Modo 1 — Ingestão supervisionada

Para fontes importantes:

```text
Você adiciona um paper, artigo, proposta ou apresentação
↓
Claude lê
↓
Gera source summary
↓
Mostra alterações propostas
↓
Você aprova
↓
Claude atualiza wiki
↓
Scripts validam
↓
Commit no Git
```

Esse é o modo que eu usaria para documentos estratégicos, propostas, RFPs e temas corporativos.

### Modo 2 — Ingestão em lote

Para fontes menos críticas:

```text
raw/web-clippings/
↓
Claude processa lote
↓
Cria páginas preliminares com confidence: low/medium
↓
Registra no log
↓
Você revisa depois
```

O próprio gist de setup recomenda calibrar com 2 ou 3 fontes ricas antes de processar em lote. ([Gist][8])

---

## 12. Frontmatter padrão

Eu usaria este padrão:

```yaml
---
type: concept
status: active
confidence: medium
created: 2026-07-07
updated: 2026-07-07
aliases:
  - LLM Wiki
  - AI-maintained wiki
sources:
  - "[[wiki/sources/karpathy-llm-wiki-gist]]"
tags:
  - wiki/concept
  - knowledge-management
  - ai-agent
---
```

Tipos sugeridos:

```text
source
entity
concept
project
pattern
decision
synthesis
comparison
question
```

Status:

```text
draft
active
needs-review
deprecated
conflict
```

Confidence:

```text
low
medium
high
```

---

## 13. Templates de páginas

### Source page

```markdown
---
type: source
status: active
confidence: high
created:
updated:
aliases: []
sources: []
tags:
  - wiki/source
---

# Source: <title>

## Bibliographic metadata

- Author:
- Date:
- URL/file:
- Captured:
- Source type:

## Summary

## Key claims

## Relevant entities

## Relevant concepts

## Important quotes or evidence

## Contradictions or tensions

## Pages updated from this source

## Open questions
```

### Concept page

```markdown
---
type: concept
status: active
confidence: medium
created:
updated:
aliases: []
sources: []
tags:
  - wiki/concept
---

# <Concept>

## Definition

## Why it matters

## How it works

## Related concepts

## Related entities

## Examples

## Source-backed claims

## Contradictions / competing views

## Open questions
```

### Decision page

```markdown
---
type: decision
status: active
confidence: high
created:
updated:
aliases: []
sources: []
tags:
  - wiki/decision
---

# Decision: <title>

## Context

## Decision

## Rationale

## Alternatives considered

## Consequences

## Related pages

## Source evidence
```

---

## 14. Workflow diário

O fluxo prático ficaria assim:

```text
1. Capturar fontes
   - Web Clipper
   - PDFs
   - apresentações
   - notas de reunião

2. Jogar em raw/

3. No Claude Code:
   /wiki-ingest raw/articles/nome-do-artigo.md

4. Revisar diff:
   git diff

5. Rodar lint:
   /wiki-lint

6. Commit:
   git add .
   git commit -m "Ingest source: nome do artigo"
   git push
```

No Obsidian, você navega a wiki, abre Graph View, usa Dataview para dashboards e, se quiser, usa Obsidian Git para sincronizar sem terminal.

---

## 15. Exemplo de dashboard Dataview

Em `wiki/dashboard.md`:

````markdown
# Wiki Dashboard

## Pages needing review

```dataview
TABLE type, confidence, updated
FROM "wiki"
WHERE status = "needs-review"
SORT updated DESC
````

## Low confidence pages

```dataview
TABLE type, status, updated
FROM "wiki"
WHERE confidence = "low"
SORT updated DESC
```

## Recent sources

```dataview
TABLE updated, confidence
FROM "wiki/sources"
SORT updated DESC
LIMIT 20
```

````

Isso transforma o vault em uma base navegável e operacional, não apenas uma coleção de notas.

---

## 16. Onde entra busca semântica?

Eu começaria **sem vector DB**.

A própria abordagem LLM Wiki nasceu como alternativa ao RAG tradicional: compilar conhecimento em Markdown interligado em vez de recuperar chunks brutos em toda pergunta. :contentReference[oaicite:20]{index=20}

Mas eu deixaria uma porta aberta:

```text
Fase 1:
  Markdown + grep + Obsidian search + wikilinks

Fase 2:
  qmd / BM25 / busca local

Fase 3:
  embeddings sobre wiki/, não sobre raw/

Fase 4:
  GraphRAG ou knowledge graph formal
````

Regra prática:

* Embedding em `raw/` replica RAG tradicional.
* Embedding em `wiki/` busca conhecimento já sintetizado.
* Graph traversal por wikilinks ajuda em perguntas multi-hop.

Pesquisas recentes sobre LLM-Wiki apontam justamente para recuperação como raciocínio: buscar, ler, seguir links e decidir quando a evidência é suficiente, em vez de só fazer lookup de chunks. ([arXiv][17])

---

## 17. Pontos críticos de qualidade

### 17.1 Não deixar o LLM “apagar história”

Toda atualização deve preservar:

```text
- fonte
- data
- páginas afetadas
- contradições
- grau de confiança
```

### 17.2 Não criar conceito duplicado

Exemplo ruim:

```text
semantic-layer.md
semantic-layers.md
camada-semantica.md
ontology-layer.md
```

Para evitar isso, use:

```yaml
aliases:
  - camada semântica
  - semantic layer
  - semantic layers
```

### 17.3 Separar fonte de interpretação

Eu manteria esta regra:

```text
wiki/sources/ = factual, o que a fonte diz
wiki/concepts/ = síntese conceitual
wiki/synthesis/ = interpretação e visão autoral
```

Essa separação é importante para auditoria.

### 17.4 Revisão humana em fontes estratégicas

Para temas críticos, o Claude deve propor diffs, não sair sobrescrevendo tudo.

---

## 18. Segurança e privacidade

Aqui eu seria cuidadoso, especialmente se houver documentos de clientes.

Claude Code pode executar comandos, editar arquivos e usar extensões como hooks e MCP. A documentação oficial trata hooks como comandos shell, endpoints HTTP ou prompts que disparam em eventos do ciclo de vida do Claude Code. ([Claude][18])

Boas práticas:

```text
1. Não colocar documentos confidenciais em repo público.
2. Usar GitHub privado.
3. Não commitar chaves/API keys.
4. Usar .gitignore para arquivos sensíveis.
5. Revisar hooks antes de aceitar.
6. Não abrir repositórios desconhecidos com Claude Code em modo permissivo.
7. Manter raw/ e wiki/ separados.
8. Usar branch para ingestões grandes.
9. Fazer git diff antes de commit.
```

Eu também evitaria hooks muito agressivos no começo. Hooks são poderosos, mas aumentam superfície de risco.

---

## 19. Avaliação crítica das abordagens

| Abordagem                 | Vantagem                          | Risco                          | Minha nota |
| ------------------------- | --------------------------------- | ------------------------------ | ---------- |
| Só Obsidian manual        | Simples, controle total           | Não escala, manutenção morre   | 5/10       |
| Karpathy LLM Wiki Plugin  | Rápido, pronto, integrado         | Menos customizável             | 7/10       |
| Claude Code + CLAUDE.md   | Flexível, auditável, ajustável    | Exige disciplina técnica       | 9/10       |
| Ar9av/obsidian-wiki       | Framework forte, próximo do ideal | Complexidade inicial           | 8/10       |
| lucasastorian/llmwiki     | Produto mais completo             | Overengineering para começar   | 7/10       |
| Vector DB/RAG tradicional | Bom para busca bruta              | Não gera conhecimento composto | 6/10       |
| Markdown + Git + lint     | Simples, auditável, portátil      | Precisa de bons padrões        | 9/10       |

Minha recomendação final:

> **Use Claude Code como compilador de conhecimento, Obsidian como IDE da wiki e GitHub como ledger/auditoria. Use plugins apenas como apoio.**

---

## 20. MVP recomendado para você

Eu faria um MVP em 3 ciclos.

### Ciclo 1 — Vault funcional

Entregas:

```text
- Repo GitHub privado
- Vault Obsidian
- Estrutura raw/wiki/outputs
- CLAUDE.md
- 3 comandos Claude Code: ingest, query, lint
- Obsidian Git
- Web Clipper
- Dataview
```

### Ciclo 2 — Calibração com 10 fontes

Use fontes como:

```text
- Post/gist Karpathy
- Plugin Obsidian
- Artigo Starmorph
- Artigo LevelUp
- 2 projetos GitHub
- 2 artigos técnicos
- 2 documentos próprios
```

Objetivo:

```text
- ajustar templates
- ajustar taxonomia
- validar qualidade dos links
- medir esforço/custo
- ver se a wiki fica útil
```

### Ciclo 3 — Operação real

Aplicar a um domínio seu, por exemplo:

```text
- Ontologia / Semantic Layer / Palantir / Databricks
- GenAI corporativo
- Slide Finder
- Consultoria vertical
- Saúde / Operadora / Regulação
```

Aí sim a wiki começa a ter valor composto.

---

## 21. Prompt inicial para Claude Code

Você pode abrir o repo no Claude Code e colar:

```text
Quero implementar um LLM Wiki Vault no padrão Karpathy usando Obsidian + GitHub.

Objetivo:
- Este repositório é um vault Obsidian.
- `raw/` contém fontes brutas imutáveis.
- `wiki/` contém páginas Markdown geradas e mantidas pelo agente.
- `outputs/` contém relatórios e artefatos derivados.
- O vault deve ser versionado em Git.
- O agente deve operar com disciplina de knowledge compiler.

Tarefas:
1. Inspecione a estrutura atual do repositório.
2. Crie ou ajuste a estrutura:
   - raw/articles
   - raw/papers
   - raw/slides
   - raw/transcripts
   - raw/web-clippings
   - wiki/sources
   - wiki/entities
   - wiki/concepts
   - wiki/projects
   - wiki/patterns
   - wiki/decisions
   - wiki/synthesis
   - wiki/comparisons
   - outputs/reports
   - manifests
   - scripts
   - .claude/commands
   - .claude/agents
3. Crie um CLAUDE.md completo com:
   - arquitetura
   - regras de ingestão
   - regras de query
   - regras de lint
   - templates de página
   - regras de frontmatter
   - regras de segurança
4. Crie comandos:
   - .claude/commands/wiki-ingest.md
   - .claude/commands/wiki-query.md
   - .claude/commands/wiki-lint.md
   - .claude/commands/wiki-review.md
5. Crie scripts simples:
   - scripts/validate_frontmatter.py
   - scripts/validate_links.py
   - scripts/find_orphans.py
   - scripts/rebuild_index.py
6. Crie páginas iniciais:
   - wiki/index.md
   - wiki/log.md
   - wiki/overview.md
   - wiki/dashboard.md
7. Não modifique raw/ sem autorização explícita.
8. Depois de criar a estrutura, explique o que foi criado e como devo usar.
```

---

## Conclusão

Eu implementaria assim:

```text
Obsidian
  ↓ interface humana

GitHub
  ↓ versionamento e auditoria

Claude Code
  ↓ agente compilador

CLAUDE.md + commands + subagents
  ↓ disciplina operacional

raw/
  ↓ fontes imutáveis

wiki/
  ↓ conhecimento compilado, linkado e versionado

scripts/
  ↓ validação determinística

outputs/
  ↓ relatórios e sínteses
```

A decisão mais importante é esta:

> **Não tente começar com uma plataforma complexa. Comece com arquivos Markdown, Git e um `CLAUDE.md` muito bem escrito.**

Depois que o processo estiver funcionando, você pode incorporar o plugin Karpathy LLM Wiki, partes do `Ar9av/obsidian-wiki`, skills do `wiki-skills`, ou até um app/MCP próprio.

[1]: https://community.obsidian.md/plugins/karpathywiki "Karpathy LLM Wiki - Obsidian Plugin"
[2]: https://github.com/green-dalii/obsidian-llm-wiki "GitHub - green-dalii/obsidian-llm-wiki: Karpathy's LLM Wiki implementation plugin for Obsidian - multi-page knowledge generation with entity/concept pages and conversational query. · GitHub"
[3]: https://github.com/Ar9av/obsidian-wiki?utm_source=chatgpt.com "GitHub - Ar9av/obsidian-wiki: Framework for AI agents to build and ..."
[4]: https://github.com/kfchou/wiki-skills?utm_source=chatgpt.com "GitHub - kfchou/wiki-skills: LLM-maintained personal wiki skills for ..."
[5]: https://github.com/lucasastorian/llmwiki?utm_source=chatgpt.com "GitHub - lucasastorian/llmwiki: Open Source Implementation of Karpathy ..."
[6]: https://github.com/SamurAIGPT/llm-wiki-agent?utm_source=chatgpt.com "GitHub - SamurAIGPT/llm-wiki-agent: A personal knowledge base that ..."
[7]: https://github.com/ScrapingArt/Karpathy-LLM-Wiki-Stack "GitHub - ScrapingArt/Karpathy-LLM-Wiki-Stack: A comprehensive, build-ready reference for constructing a high-performance personal knowledge system using Obsidian and Claude Code, grounded in Andrej Karpathy's \"LLM Wiki\" pattern. · GitHub"
[8]: https://gist.github.com/kennyg/6c45cace2e1c4e424a28fcd51dd6c25b "LLM-Wiki Obsidian Setup Guide — full implementation of Karpathy's llm-wiki pattern · GitHub"
[9]: https://github.com/obsidianmd/obsidian-clipper?utm_source=chatgpt.com "GitHub - obsidianmd/obsidian-clipper: Highlight and capture the web in ..."
[10]: https://github.com/Vinzent03/obsidian-git?utm_source=chatgpt.com "Obsidian Git Plugin - GitHub"
[11]: https://github.com/blacksmithgu/obsidian-dataview?utm_source=chatgpt.com "GitHub - blacksmithgu/obsidian-dataview: A data index and query ..."
[12]: https://blog.starmorph.com/blog/karpathy-llm-wiki-knowledge-base-guide "How to Build Karpathy's LLM Wiki: The Complete Guide to AI-Maintained Knowledge Bases"
[13]: https://code.claude.com/docs/en/settings?utm_source=chatgpt.com "Claude Code settings - Claude Code Docs"
[14]: https://code.claude.com/docs/en/sub-agents?utm_source=chatgpt.com "Create custom subagents - Claude Code Docs"
[15]: https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f "llm-wiki · GitHub"
[16]: https://community.obsidian.md/plugins/obsidian-git?utm_source=chatgpt.com "Git - Obsidian Plugin"
[17]: https://arxiv.org/abs/2605.25480?utm_source=chatgpt.com "Retrieval as Reasoning: Self-Evolving Agent-Native Retrieval via LLM-Wiki"
[18]: https://code.claude.com/docs/en/hooks?utm_source=chatgpt.com "Hooks reference - Claude Code Docs"
