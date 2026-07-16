# Avaliação do Sistema LLM Wiki — jul/2026

> Documento de análise crítica da primeira fase de uso do vault. Baseado em evidências concretas: outputs gerados, logs de ingestão, resultados dos scripts de validação e comparação com a visão original documentada em `docs/`.

---

## 1. Contexto: o que foi processado

**Período:** 13–16 julho de 2026 (~3 dias de uso ativo)

**Domínio:** Hapvida — projeto Regulação 2.0 / Jornada de Autorização de Senhas (JAS)

**Volume de inputs:**

| Tipo | Quantidade | Localização |
|------|-----------|-------------|
| Transcrições de reuniões/entrevistas/áudios | 20+ arquivos | `raw/transcripts/` |
| Documentos de planejamento (artigos MD) | 14 arquivos | `raw/articles/` |
| Catálogo de dados JAS (repo snapshot) | 58 tabelas + índice + indicadores | `raw/repos/jas/` |
| **Total de fontes brutas** | ~95 arquivos | `raw/` |

**Volume de outputs:**

| Tipo | Quantidade |
|------|-----------|
| Source pages | 25 |
| Concept pages | 14 |
| Entity pages | 14 |
| Synthesis pages | 5 |
| Question pages | 3 |
| Comparison pages | 1 |
| Pattern pages | 1 |
| Project pages | 1 |
| Data-dictionary pages (tipo emergente) | 62 |
| **Total de páginas wiki** | ~126 |
| Entradas em `manifests/sources.yml` | 33 |
| Entradas em `wiki/log.md` | 20 |

**Comandos e operações realizadas:**
- `/wiki-ingest` — múltiplas execuções, incluindo batches
- `/wiki-query` — consultas que geraram sínteses e questões
- Criação manual de data-dictionary via ingest especializado

---

## 2. O que funcionou bem

### 2.1 Acumulação incremental funciona

O comportamento central do padrão Karpathy — conhecimento que se acumula em vez de ser recuperado do zero — foi observado na prática.

Exemplos concretos:

- **`wiki/concepts/sla-autorizacao.md`** foi alimentado por 5 fontes diferentes em sequência: `jas-jornada-autorizacao-senhas` (criação), `hapvida-slas-autorizacao-jul2026` (valores concretos: 12h urgência, 24h emergência, 10 dias eletivo), `hapvida-slas-autorizacao-transcricao-jul2026` (SLA dinâmico, subáreas GMA/Fidelização), `gestao-autorizacoes-slas-jul14-tarde` (SLA interdepartamental, lacuna confirmada). Cada ingestão adicionou claims com citação, sem apagar o que já existia.

- **`wiki/entities/siga.md`** foi atualizado três vezes por fontes diferentes, cada uma adicionando uma camada: diferença SIGA (assistencial) vs SIGO (autorização), sistema de Emergência como candidato a migração.

- **`wiki/entities/ciandt.md`** recebeu um fato novo sobre estrutura de Growth Units a partir da transcrição completa, complementando o registro inicial.

### 2.2 Sínteses são o artefato mais valioso

As páginas de synthesis são o output que não seria possível com RAG tradicional. Cada uma integra múltiplas fontes e produz conhecimento que não está em nenhuma fonte individual.

**Evidências:**

- **`fluxo-autorizacao-ponta-a-ponta`** (6 fontes): diagrama Mermaid com 5 estágios do fluxo, SLAs por etapa, subáreas paralelas, problema estrutural de fragmentação departamental identificado e nomeado. Este insight — que o problema não é a complexidade das regras, mas a fragmentação — emerge da leitura cruzada de 6 documentos, não de nenhum deles isoladamente.

- **`event-log-dependencia-central`** (10+ fontes): tese de que o event log é o único investimento que desbloqueia simultaneamente painéis, copiloto, flywheel e process mining. Com mapa de dependências, roadmap por tier e conexões específicas (P4→motor, P6→copiloto).

- **`product-backlog-candidato-jul2026`** (7 fontes): 6 temas, 20 épicos, ~80 itens priorizados — gerado por `/wiki-query` sobre o estado acumulado, não por leitura de um único documento. Exemplo direto do potencial que justifica o padrão.

- **`visao-estrategica-candidata-jul2026`** (9 fontes): 3 objetivos estratégicos com contexto operacional completo (20M sol./mês, 94% automação, R$ 2,5M judicialização). Pronto para uso em apresentação de liderança.

### 2.3 Contradições documentadas, não silenciadas

A regra mais importante do vault ("nunca resolver contradições silenciosamente") foi aplicada com rigor.

**Casos reais detectados:**

1. **`rfn_dim_jas_retroativo`** — `status: conflict`. Dicionário documenta como active; `sm-critica-paineis` classifica como descontinuada (B.1, nível CRÍTICO). Ambas as posições registradas, com fontes. A dimensão foi marcada como conflict e avisos adicionados.

2. **`protocolo-assistencial`** — automação via flags de aderência: fonte `hapvida-protocolos-protomake-jul2026` sugeria flags habilitando "liberação automática". Dr. Thurlierme clarificou que é "proposta em avaliação", não implementada. Diferença de grau documentada sem escolher um vencedor.

3. **Taxa de automação: 94% vs 95%** — diferença de 1pp entre `hapvida-visao-geral-jul2026` (94%) e Alberto na reunião de SLAs (95%). Registrada como estimativa operacional, não dado exato, sem conflict formal mas com nota.

4. **ETLs do domínio ATEH** listados na seção ELT da fato RFN mas pertencentes ao domínio incorreto (C.2, ALTO). Aviso adicionado na tabela afetada.

### 2.4 Taxonomia extendida organicamente — e rastreada

O tipo `data-dictionary` não estava na visão original. O sistema o criou ao ingerir o catálogo JAS — 62 tabelas que não se encaixavam bem em `source`, `concept` ou `entity`. O tipo foi adicionado a `manifests/taxonomy.yml` com uma entrada de log:

> "Type: data-dictionary (novo tipo adicionado a manifests/taxonomy.yml)"

A extensão foi legítima, rastreável e não quebrou a estrutura existente. Isso mostra que o modelo é mais elástico do que parece — a taxonomia pode crescer com o domínio.

### 2.5 Log.md como audit trail efetivo

O `wiki/log.md` com 20 entradas datadas é genuinamente útil:
- Cada entrada lista fontes, páginas criadas, atualizadas, conflitos detectados, questões abertas
- Entradas de síntese explicam o raciocínio ("derivada de wiki-query", "integração das análises de painéis")
- Permite reconstituir o que foi feito, em que ordem, com que intenção
- Funciona como commit message estruturado independente do git

### 2.6 Questions pages capturam o que não se sabe

`wiki/questions/inventario-dados-necessarios-sm.md` é o melhor exemplo: não é apenas uma pergunta — é uma análise estruturada de gaps, com 4 categorias (disponíveis, bloqueadas, a criar, fora de escopo), tiers de esforço, checklist de Sprint 0 e 3 estruturas a criar. Gerada a partir de uma query que revelou uma lacuna real.

As questions funcionam como o mecanismo de consciência do que falta — algo que RAG tradicional não produz.

---

## 3. Problemas identificados

### 3.1 Scripts de validação dessincronizados da taxonomia

**Evidência:** `validate_frontmatter.py` retorna 62 erros falso-positivos:
```
[ERRO] wiki/data-dictionary/jas/index.md: Campo 'type' com valor inválido 'data-dictionary'
(válidos: comparison, concept, decision, entity, pattern, project, question, source, synthesis)
```

O script hardcoda os tipos válidos em vez de ler `manifests/taxonomy.yml`. Quando o sistema adicionou `data-dictionary` ao taxonomy, o script ficou para trás.

**Impacto:** Todo run do linter produz ruído que mascara erros reais. O desenvolvedor para de confiar nos scripts.

**Solução:** `validate_frontmatter.py` deve carregar tipos, status e confidence de `manifests/taxonomy.yml` em vez de ter essas listas embutidas.

### 3.2 validate_links.py não resolve wikilinks relativos em subdiretórios

**Evidência:** O script reporta 70+ links mortos em `wiki/data-dictionary/jas/index.md`:
```
[MORTO] wiki/data-dictionary/jas/index.md:39 — [[jas/requirements\]]
[MORTO] wiki/data-dictionary/jas/index.md:68 — [[jas/tables/raw_hap_tb_autorizacao_senha\]]
```

Os arquivos existem em `wiki/data-dictionary/jas/requirements.md` e `wiki/data-dictionary/jas/tables/raw_hap_tb_autorizacao_senha.md`. O script resolve links a partir do root de `wiki/` e não considera que dentro de `wiki/data-dictionary/jas/`, um link `[[jas/tables/...]]` pode ser relativo.

Também há um problema com backslash no final do link (`\]]`) que aparece quando o link tem texto de display (`[[path\|Display Text]]`).

**Impacto:** 57 páginas aparecem como órfãs quando não são (são referenciadas pelo index.md). O developer ignora os avisos.

**Solução:** O script precisa (a) resolver links relativos ao arquivo de origem além de absolutos ao root, e (b) parsear corretamente a sintaxe `[[path|display]]` sem incluir o `\` antes do pipe.

### 3.3 Status nunca avança além de `draft`

**Evidência:** Todos os 25 source pages, 14 concept pages e 14 entity pages permanecem em `status: draft`. Nenhuma página chegou a `active`.

**Causa:** Não há:
- Critério explícito para promoção (quando um conceito deixa de ser draft?)
- Gatilho no fluxo de ingest (o agente nunca propõe promoção)
- Hábito de revisão periódica

**Impacto:** `status` perde significado. O dashboard Dataview que filtra por `status: needs-review` não produz nada útil. O campo vira ornamento.

**Solução:** Definir critérios explícitos no CLAUDE.md — por exemplo, um conceito passa para `active` após ser corroborado por 2+ fontes e revisado uma vez. O agente de ingest deve propor promoção quando o critério for atingido.

### 3.4 `wiki/index.md` e `wiki/data-dictionary/` desconectados

**Evidência:** `wiki/index.md` lista 25 sources, 21 concepts, 9 entities — mas não lista nenhuma das 62 páginas de data-dictionary. As pages em `wiki/data-dictionary/jas/tables/` são invisíveis para quem navega pelo index.

**Causa:** O tipo emergente `data-dictionary` foi adicionado à taxonomia mas o `wiki/index.md` não tem seção para ele. O script `rebuild_index.py` também não o considera.

**Impacto:** 62 páginas — o maior bloco de conhecimento estruturado do vault — não aparecem no ponto de entrada principal.

**Solução:** Adicionar seção `## Data Dictionaries` ao index e ao `rebuild_index.py`. Considerar se o índice do data-dictionary (`wiki/data-dictionary/jas/index.md`) deve ser o ponto de entrada listado no índice principal, com as tabelas como folhas a partir dele.

### 3.5 `maps/` e `outputs/` vazios

**Evidência:** `ls outputs/reports/` e `ls maps/` retornam vazio. Nenhuma execução de `/wiki-lint` produziu um relatório. Nenhuma skill visual produziu um Canvas ou Excalidraw.

**Causa:** Skills de visualização e lint estão definidas mas não foram invocadas como parte de nenhum workflow regular.

**Impacto:** O Obsidian não tem nenhum artefato visual navegável. O grafo do Obsidian (que usa backlinks) existe implicitamente, mas não há Canvas curado que mostre as relações estratégicas.

**Solução:** 
1. Rotina de lint periódico (`/wiki-lint` após cada batch de ingest)
2. Canvas de alto nível para o projeto Regulação 2.0 mapeando as relações entre as sínteses, conceitos e projetos centrais

### 3.6 Subagents podem não estar sendo efetivamente spawned

**Evidência:** O `wiki-ingest/SKILL.md` descreve o protocolo em 8 passos mas não menciona explicitamente delegação para `source-reader`, `concept-curator` ou `contradiction-reviewer`. O log.md não registra invocações de subagents.

**Causa provável:** O Claude Code executa todo o ingest no contexto principal, usando os agentes como referência de comportamento (via `name:` no frontmatter), não como contextos isolados.

**Impacto:** Não há isolamento de contexto real. O agente principal carrega e processa tudo — o que pode causar contaminação de contexto em ingests grandes (como o batch de 14 fontes do JAS). A promessa de subagents como "separação de responsabilidade" não está sendo realizada.

**Solução:** Reescrever o SKILL.md de ingest para usar `Agent tool` explicitamente para leitura de fontes grandes, com outputs estruturados. A skill deveria ser um orquestrador que delega, não um executor monolítico.

### 3.7 Duplas verbatim+resumo sem protocolo codificado

**Evidência:** Várias transcrições chegaram com dois arquivos por reunião:
- `Gest-o-de-Autoriza-es-e-SLAs-a0fdc0b1-8142.md` (verbatim, primário)
- `Gestão de Autorizações e SLAs Jul 14, 2026.md` (resumo estruturado)

O sistema tratou como uma única fonte mas a decisão foi ad-hoc — registrada no log como "tratados como uma única fonte" sem que isso esteja codificado no CLAUDE.md ou no SKILL.md.

**Impacto:** Se o próximo usuário encontrar duplas similares, pode duplicar a ingestão ou perder a fonte primária.

**Solução:** Documentar no CLAUDE.md o protocolo para duplas: "quando encontrar um arquivo verbatim e um resumo da mesma sessão, combine em uma única source page, referenciando ambos os caminhos em `raw_files:` no frontmatter."

### 3.8 Comparisons e decisions sub-utilizados

**Evidência:** 1 comparison page criada (`glossario-processos-areas`), 0 decision pages.

O vault capturou várias decisões de produto e arquitetura que ocorreram nas reuniões, mas nenhuma virou um ADR:
- Decisão: event log estruturado como prioridade máxima antes de copiloto
- Decisão: nenhuma negativa automatizada — médico auditor sempre no comando
- Decisão: piloto em 6 unidades de Fortaleza antes de expansão nacional
- Decisão: não expandir acesso médico credenciado além do experimento pontual

Essas decisões aparecem diluídas nas synthesis pages mas não são acessíveis como ADRs isolados.

**Impacto:** Quando alguém quiser entender "por que escolhemos event log primeiro?", terá que varrer as sínteses em vez de navegar para `wiki/decisions/`.

**Solução:** O wiki-query deveria propor criação de decision page sempre que identificar uma decisão explícita ("foi decidido que...", "optamos por...") nas fontes.

---

## 4. Potenciais não explorados

### 4.1 Canvas como interface de navegação semântica

A skill `obsidian-canvas-creator` está instalada. O Canvas do Obsidian é especialmente potente neste vault porque seus nós podem ser as próprias páginas reais — não caixas desenhadas, mas wikilinks para os `.md` existentes.

**O que poderia existir:**
```
maps/canvas/regulacao-2-0-landscape.canvas
  → nós: sínteses, conceitos e projetos centrais do projeto
  → grupos: fundação de dados / automação / visibilidade / aprendizado
  → conexões: dependências entre epics e conceitos
```

Este canvas seria navegável no Obsidian — clicar em um nó abre a página. É a visualização estratégica que não existe hoje.

### 4.2 `/concept-synthesis` em conceitos maduros

Os conceitos com mais fontes acumuladas são candidatos para uma passagem de síntese que consolide sua estrutura:
- `sla-autorizacao` (5 fontes)
- `regulacao-auditoria-medica` (3+ fontes)
- `copiloto-auditoria` (3+ fontes)
- `fila-dinamica-autorizacao` (3+ fontes)

Esses conceitos têm seções crescentes de "Source-backed claims" mas não foram submetidos ao fluxo `/concept-synthesis`, que lê todas as fontes e reescreve a página com estrutura melhorada.

### 4.3 Bases files para dashboards operacionais

A skill `obsidian-bases` está instalada. `wiki/dashboard.md` usa Dataview (sintaxe mais antiga) mas `.base` files poderiam criar views mais ricas:

```
wiki/bases/sources-by-confidence.base
wiki/bases/concepts-needs-review.base
wiki/bases/conflict-tracker.base
wiki/bases/questions-open.base
```

A diferença prática: Bases são renderizadas pelo Obsidian como pequenas aplicações de dados, não como tabelas Markdown estáticas.

### 4.4 Extraction de patterns a partir dos comportamentos observados

Apenas 1 pattern foi criado (`agente-ai-native`). Vários comportamentos recorrentes observados nas fontes merecem páginas de pattern:

- **Pattern: Validação Sprint 0 antes de engenharia** — confirmar hipóteses com queries diretas antes de construir pipelines
- **Pattern: Event log como pré-requisito** — não construir features analíticas antes da fundação de dados estar validada
- **Pattern: Copiloto com feedback loop explícito** — "concordo/não concordo" como dado de treino, não como UX apenas
- **Pattern: Piloto localizado antes de escala nacional** — 6 unidades de Fortaleza como unidade experimental

Esses patterns têm valor reutilizável além do projeto Hapvida.

### 4.5 Integração com wiki-query para consultas exploratórias contínuas

O `product-backlog-candidato-jul2026` e `visao-estrategica-candidata-jul2026` foram gerados por consultas ao vault acumulado. Esse é o caso de uso mais poderoso do sistema — e os menos explorado como prática regular.

A proposta seria: ao final de cada sessão de ingest, executar 2-3 queries padrão:
- "Quais questões abertas foram parcialmente respondidas pelas novas fontes?"
- "Há novas sínteses que podem ser criadas com o conhecimento acumulado?"
- "Algum conceito com múltiplas fontes está pronto para concept-synthesis?"

---

## 5. Recomendações priorizadas

### Prioridade 1 — Corriger os scripts (impacto imediato, custo baixo)

**5.1** `validate_frontmatter.py`: carregar tipos, status e confidence de `manifests/taxonomy.yml` em vez de hardcodar. Uma linha de mudança, elimina 62 falsos positivos.

**5.2** `validate_links.py`: corrigir resolução de links relativos em subdiretórios e parsing de `[[path|display]]`. Elimina 70+ mortos falsos; restaura confiança no script.

**5.3** `rebuild_index.py`: adicionar suporte a `data-dictionary` e listar `wiki/data-dictionary/*/index.md` como ponto de entrada no `wiki/index.md`.

### Prioridade 2 — Codificar o que existe mas não está escrito

**5.4** CLAUDE.md: adicionar seção "Protocolos de ingestão para tipos especiais":
- Duplas verbatim+resumo da mesma sessão → uma source page com `raw_files: [path1, path2]`
- Catálogos de dados estruturados → usar tipo `data-dictionary` com path `wiki/data-dictionary/<domínio>/`
- Áudios sem transcrição full → inferir conteúdo de resumo estruturado, marcar `confidence: low`

**5.5** CLAUDE.md: adicionar critérios de promoção de status:
- `draft → active`: 2+ fontes corroborando, ao menos uma revisão manual
- `active → needs-review`: data `updated` > 60 dias OU nova fonte conflitante
- `draft → conflict`: claim contraditório identificado sem resolução

**5.6** wiki-ingest SKILL.md: codificar protocolo para duplas de arquivo verbatim+resumo.

### Prioridade 3 — Ampliar o uso das capacidades já instaladas

**5.7** Criar rotina de lint periódico: executar `/wiki-lint` após cada batch de ingest e salvar relatório em `outputs/reports/`. Não deixar o diretório vazio.

**5.8** Criar Canvas estratégico de alto nível do projeto Regulação 2.0 em `maps/canvas/`. Usar a skill `obsidian-canvas-creator`. Este deve ser o artefato de navegação visual do vault.

**5.9** Executar `/concept-synthesis` nos 4-5 conceitos com mais fontes acumuladas.

**5.10** Criar 4-6 ADRs nas decisões identificadas nas sínteses.

### Prioridade 4 — Melhorar a pipeline de subagents

**5.11** Revisar o wiki-ingest SKILL.md para tornar a delegação de leitura ao `source-reader` explícita como instrução de Agent tool, especialmente para documentos com mais de 5.000 palavras. Documentar quando é aceitável processar diretamente vs. delegar.

**5.12** Adicionar ao protocolo de ingest uma chamada explícita ao `contradiction-reviewer` após processar entities/concepts, com output estruturado listado no log.md.

---

## 6. Próximos passos sugeridos

**Sprint imediato (1-2h):**
1. Corrigir `validate_frontmatter.py` para ler taxonomy.yml
2. Corrigir `validate_links.py` para resolver links relativos
3. Executar `/wiki-lint` e salvar primeiro relatório formal
4. Adicionar seção data-dictionary ao wiki/index.md

**Próximo ciclo de ingest:**
1. Criar Canvas do projeto Regulação 2.0
2. Executar `/concept-synthesis sla-autorizacao` e `regulacao-auditoria-medica`
3. Criar 3 ADRs a partir das decisões capturadas nas sínteses

**Evolução de médio prazo:**
1. Avaliar se subagents devem ser explicitamente invocados (vs. comportamento guiado por system prompt)
2. Considerar adicionar `briefings/` como tipo de output: documentos para humanos gerados a partir do vault, com data e destinatário
3. Explorar integração da skill `obsidian-bases` para dashboards operacionais

---

## Apêndice: Métricas do vault (jul/2026)

| Métrica | Valor |
|---------|-------|
| Total de pages | 139 |
| Pages com links de entrada | 82 (59%) |
| Pages órfãs | 57 (41%) — maioria data-dictionary com bug de script |
| Erros de frontmatter | 62 falso-positivos (data-dictionary) + ~0 reais |
| Links mortos | 70+ reportados, quase todos falso-positivos do bug de resolução |
| Fontes ingeridas | 33 |
| Dias de uso ativo | 3 |
| Status `draft` | 100% das páginas — nunca promovido |
| Status `conflict` | 2 páginas confirmadas |
| Pages em `maps/` | 0 |
| Relatórios em `outputs/reports/` | 0 |

---

*Documento gerado em 2026-07-16 por análise do vault + outputs dos scripts de validação.*
