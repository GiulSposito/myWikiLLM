# Plano: Organização de Pastas e Visibilidade no Obsidian

## Diagnóstico

### O que o usuário vê no Obsidian (file explorer)

Obsidian exibe todos os diretórios não-ocultos na raiz:
```
docs/          ← 11 arquivos de dev/design, não são conteúdo da wiki
manifests/     ← YAMLs de configuração, não são notas
maps/          ← visual, faz sentido estar visível
outputs/       ← relatórios gerados, faz sentido estar visível
raw/           ← fontes brutas, faz sentido estar visível (audit trail)
scripts/       ← Python + 10 fixtures .md de teste (poluem search/graph)
wiki/          ← o conteúdo real
```

**Problema principal:** `scripts/tests/batch/fixtures/*.md` — 10 arquivos Markdown de fixture de teste aparecem no search, no graph e no switcher do Obsidian como se fossem notas reais da wiki. Geram links fantasma no graph.

**Problema secundário:** `docs/` contém documentação de desenvolvimento (architecture.md, vision.md, optimization*.md etc.) — não são conhecimento compilado, são artefatos de projeto. Aparecem como notas no Obsidian.

---

## Achados

### 1. `pyproject.toml` aponta para `tests/` (path antigo) — BUG

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
```

Os testes foram movidos para `scripts/tests/`. pytest não os encontra via `pytest` sem especificar o path.

**Correção:** atualizar para `testpaths = ["scripts/tests"]`.

---

### 2. Fixtures `.md` de teste poluem o Obsidian — VISIBILIDADE

**Localização:** `scripts/tests/batch/fixtures/*.md` (10 arquivos)

Esses arquivos aparecem no file explorer, no global search ("meeting-01", "meeting-02"...) e no graph do Obsidian como se fossem notas da wiki. Não têm frontmatter válido para a wiki.

**Melhor solução:** usar `userIgnoreFilters` do Obsidian em `app.json` para excluir `scripts/` do file explorer e do search — **sem mover arquivos**. Obsidian respeita essa config nativamente desde a versão 1.0.

---

### 3. `docs/` visível no Obsidian — VISIBILIDADE

11 arquivos de documentação de projeto (`architecture.md`, `vision.md`, `optimization*.md`, `userguide.md`...) aparecem no file explorer e search do Obsidian. São úteis para o desenvolvedor, não para o usuário da wiki.

**Solução:** adicionar `docs/` ao `userIgnoreFilters` do Obsidian. O diretório permanece no repo e acessível via terminal/editor.

---

### 4. `.DS_Store` não commitados mas presentes — LIMPEZA

`.gitignore` já exclui `.DS_Store`, mas `raw/.DS_Store` e `wiki/.DS_Store` existem no disco (não rastreados). Inofensivos, mas bagunçam `git status`.

**Não é uma mudança de código** — apenas nota para o usuário rodar `git clean -fd --dry-run` para ver e `find . -name '.DS_Store' -delete` para limpar localmente.

---

### 5. `staging/` sem `.gitkeep` — CONSISTÊNCIA

`staging/` está no `.gitignore` mas não tem `.gitkeep` para o diretório existir no clone. O batch pipeline cria o diretório via `STAGING_ROOT.mkdir(parents=True, exist_ok=True)`, então não é bloqueante. Mas se alguém clonar e tentar `ls staging/`, o diretório não existe.

**Solução menor:** adicionar `staging/.gitkeep` com `staging/*` (não `staging/`) no `.gitignore` para manter o diretório mas ignorar o conteúdo.

---

## Mudanças Planejadas

| # | Arquivo | Mudança |
|---|---------|---------|
| 1 | `pyproject.toml` | `testpaths = ["scripts/tests"]` |
| 2 | `.obsidian/app.json` | Adicionar `userIgnoreFilters` para excluir `scripts` e `docs` |
| 3 | `.gitignore` | Trocar `staging/` por `staging/*` + adicionar `staging/.gitkeep` |
| 4 | `staging/.gitkeep` | Criar arquivo vazio para o diretório existir no clone |

## O que NÃO está sendo tocado

- Estrutura de pastas do projeto — `scripts/`, `docs/` permanecem onde estão
- `manifests/` — YAMLs não geram ruído no Obsidian (sem `.md`)
- `maps/` e `outputs/` — conteúdo legítimo de visualização e relatórios
- `raw/` — audit trail, correto estar visível
- Nenhum arquivo movido de lugar
