# Plano: Reset da base de conhecimento para zero

## Objetivo

Remover todo o conteúdo de domínio acumulado (raw + wiki compilado) deixando o vault pronto para uma nova base de conhecimento. A infraestrutura do sistema (agentes, skills, scripts, manifests de taxonomia, configurações) é preservada integralmente.

---

## O que DELETAR

### raw/ — todo o conteúdo de fonte (exceto .gitkeep)

```
raw/articles/
  plano_analise_dados.md
  plano_service_management.md
  service_managment_completo.md
  service_managment_overview.md
  sm_critica_paineis.md
  sm_paineis_gap_analysis.md
  sm_paineis_mvp_visual.md
  sm_painel_01_torre_controle.md
  sm_painel_02_gestao_filas.md
  sm_painel_03_sla_aging_risco.md
  sm_painel_04_fluxo_gargalos.md
  sm_painel_05_pendencias_qualidade.md
  sm_painel_06_capacidade_produtividade.md
  srv_mgt_generic_mvp_panels.md

raw/transcripts/
  (todos os .md exceto .gitkeep)
  Atualiza-o-dos-Protocolos-no-Protomake-6dcbc856-5812.md
  "Atualização dos Protocolos no Protomake Jul 13, 2026.md"
  "Audio - Assistencial Emergencia Dusléia.m4a Jul 14, 2026.md"
  "Audio Protocolos - Dr Thurlierme.mp3 Jul 14, 2026.md"
  Audio-Assistencial-Emergencia-Dusle-ia-m4a-5d8a6744-80f6.md
  Audio-Protocolos-Dr-Thurlierme-mp3-1802ef1c-c27a.md
  Gest-o-de-Autoriza-es-e-SLAs-a0fdc0b1-8142.md
  "Gestão de Autorizações e SLAs Jul 14, 2026.md"
  Hapvida - SLAs Autorização - summário.md
  Hapvida - SLAs Autorização - transcricao.md
  "Hapvida - Visão geral Rápida do Projeto e Status Jul 13, 2026.md"
  "Hapvida In Loco Jul 7, 2026.md"
  Hapvida-In-Loco-db9c0fa7-4304.md
  Hapvida-Vis-o-geral-R-pida-do-Projeto-e-Status-8f525163-4d03.md
  Jul-14-11-46-AM-d83fcc91-9acf.md
  regulacao_briefing.md
  summary_20260622.md
  transcription_20260622.md
  WhatsApp-Audio-2026-07-14-at-14-35-35-mp4-d7e1ed6f-bccb.md

raw/repos/
  _domains_overview.md
  Autorizacoes.md
  "Contas Medicas.md"
  SAC.md
  aut/  (diretório inteiro com todas as subpastas e tabelas)
  cm/   (diretório inteiro)
  jas/  (diretório inteiro)
  sac/  (diretório inteiro)
  (manter .gitkeep)
```

### wiki/ — todo o conhecimento compilado

Subdiretórios inteiros (apagar recursivamente):
```
wiki/sources/       (27 arquivos)
wiki/entities/      (14 arquivos)
wiki/concepts/      (21 arquivos)
wiki/projects/      (1 arquivo)
wiki/patterns/      (5 arquivos)
wiki/decisions/     (4 arquivos)
wiki/synthesis/     (6 arquivos)
wiki/comparisons/   (1 arquivo)
wiki/questions/     (3 arquivos)
wiki/data-dictionary/  (aut/, cm/, jas/, sac/ — ~250 arquivos de tabelas)
```

### maps/ — visualizações geradas

```
maps/canvas/regulacao-2-0-landscape.canvas
```

### outputs/ — artefatos derivados

```
outputs/reports/wiki-lint-2026-07-16.md
```

---

## O que RESETAR (reescrever com scaffold vazio)

Esses arquivos existem como parte da estrutura permanente do vault mas contêm conteúdo de domínio acumulado que precisa ser limpo:

### wiki/index.md
Reescrever com frontmatter completo e seções vazias (sem entradas de conteúdo).

### wiki/log.md
Reescrever com frontmatter completo e nenhuma entrada de ingestão.

### wiki/overview.md
Já está quase em branco; a seção "Domains covered" já diz "No domains ingested yet". Manter sem alteração (está correto para o estado zero).

### manifests/sources.yml
Manter apenas o cabeçalho de comentários e `sources: []` vazio.

### .claude/plan.md
Limpar (este arquivo) após execução — era o plano da sessão anterior.

---

## O que PRESERVAR intacto

```
CLAUDE.md                         ← constituição operacional
README.md                         ← visão geral do sistema
.gitignore
.obsidian/                        ← configuração Obsidian

.claude/
  agents/                         ← source-reader, concept-curator, entity-curator,
                                     contradiction-reviewer, wiki-linter
  skills/                         ← wiki-ingest, wiki-query, wiki-lint,
                                     concept-synthesis + outros skills visuais
  commands/                       ← wiki-map, wiki-review
  settings.local.json

scripts/
  validate_frontmatter.py
  validate_links.py
  find_orphans.py
  rebuild_index.py

manifests/
  taxonomy.yml                    ← taxonomia de tipos e status (agnóstica de domínio)
  aliases.yml                     ← já vazio, manter

docs/
  architecture.md
  detail.md
  skills.md
  userguide.md
  vision.md
  avaliacao-sistema-jul2026.md    ← doc de avaliação do sistema (não é domínio)

wiki/
  dashboard.md                    ← queries Dataview — infraestrutura Obsidian
  overview.md                     ← descrição do vault (domínio neutro)

raw/
  articles/.gitkeep
  images/.gitkeep
  papers/.gitkeep
  slides/.gitkeep
  transcripts/.gitkeep
  web-clippings/.gitkeep
  repos/.gitkeep
```

---

## Sequência de execução

1. Deletar todo o conteúdo de `raw/articles/`, `raw/transcripts/`, `raw/repos/` (exceto .gitkeep)
2. Deletar `wiki/sources/`, `wiki/entities/`, `wiki/concepts/`, `wiki/projects/`, `wiki/patterns/`, `wiki/decisions/`, `wiki/synthesis/`, `wiki/comparisons/`, `wiki/questions/`, `wiki/data-dictionary/` — completamente
3. Deletar `maps/canvas/regulacao-2-0-landscape.canvas`
4. Deletar `outputs/reports/wiki-lint-2026-07-16.md`
5. Resetar `wiki/index.md` para scaffold vazio
6. Resetar `wiki/log.md` para scaffold vazio
7. Resetar `manifests/sources.yml` para `sources: []`
8. Verificar com `git status` e confirmar antes de commitar
9. Commit: "Reset: clear all domain knowledge content, preserve system infrastructure"

---

## Nota sobre histórico git

O histórico git anterior ficará preservado (os commits do projeto Hapvida ainda estarão acessíveis via `git log`). O reset apenas cria um novo estado limpo no branch. Se o objetivo for também apagar o histórico, isso requer `git filter-branch` ou um repo novo — operação destrutiva que vale confirmar separadamente.
