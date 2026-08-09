# Plan: Fix cross-pathway source dedup (wiki-ingest vs wiki-ingest-batch)

## Problema

Uma fonte ingerida via `/wiki-ingest` (skill LLM) não é detectada como "já ingerida"
quando o scanner do `/wiki-ingest-batch` executa. Isso causa reingestão duplicada.

---

## Diagnóstico: as três causas raiz

### Causa 1 — `sha256:` ausente nas entradas do wiki-ingest (causa principal)

O scanner indexa fontes conhecidas por dois critérios: `by_hash` (SHA256) e `by_path`
(caminho absoluto). Para acionar qualquer uma das duas:

- `by_hash` requer o campo `sha256:` no `sources.yml`
- `by_path` requer o campo `raw_path:` ou `path:` no `sources.yml`

O Step 9 do skill `wiki-ingest` diz apenas "Register in `manifests/sources.yml`",
mas o template de comentário no cabeçalho do `sources.yml` não lista os campos
`sha256:` nem `raw_path:` — lista apenas `slug`, `title`, `type`, `ingested`,
`path`, `pages_created`, `pages_updated`. Resultado: o LLM omite `sha256:` na
maioria das vezes, e às vezes usa `path:` com um caminho relativo ou URL.

Sem `sha256:`, o `by_hash` lookup fica cego para a entrada.

### Causa 2 — Resolução de caminho relativa ao CWD, não ao vault

`load_known_sources()` faz `Path(ks.raw_path).resolve()`, que usa `os.getcwd()`.
Se o CWD na hora do scan não for a raiz do vault, a path absoluta calculada é errada
e o `by_path` lookup falha mesmo quando o arquivo é o mesmo.

O correto é resolver caminhos relativos contra `VAULT_ROOT` (que é definido no
topo do módulo como `Path(__file__).parent.parent.parent`).

### Causa 3 — Formato do `slug` diverge entre os dois caminhos

O scanner gera `source_key = slugify(path.stem) + "-" + sha256[:8]`, por exemplo
`meeting-001-a821e682`. O skill `/wiki-ingest` usa o slugifier do normalizer
(`from scripts.batch.normalizer import slugify`) ou ad hoc, gerando slugs como
`meeting-001-api-gateway` (sem hash). Esses slugs são diferentes.

A checagem de Rule 1 é:
```python
if known_by_hash.slug == known_by_path.slug:
    # Rule 1: skip
```
Se os slugs divergem (mesmo que hash e path matchem), essa condição falha e o
arquivo entra como `scanned` em vez de `skipped_duplicate`.

Na prática: com `sha256:` presente, o `by_hash` lookup já causa skip independente
do slug (Rule 2 ou Rule 1). Mas a divergência de slug ainda quebra Rule 1 quando
ambos hash e path estão presentes.

---

## Solução: três correções

### Fix 1 — `scanner.py`: resolver paths relativas contra VAULT_ROOT (1 linha)

**Arquivo:** `scripts/batch/scanner.py`

Em `load_known_sources()`, linha 112:

```python
# Antes (usa os.getcwd()):
by_path[str(Path(ks.raw_path).resolve())] = ks

# Depois (usa VAULT_ROOT como base):
p = Path(ks.raw_path)
resolved = str((VAULT_ROOT / p).resolve() if not p.is_absolute() else p.resolve())
by_path[resolved] = ks
```

### Fix 2 — `wiki-ingest` SKILL.md: Step 9 mandatório de registrar sha256 + raw_path

**Arquivo:** `.claude/skills/wiki-ingest/SKILL.md`

No Step 9 ("Update navigation"), tornar explícito o formato de registro em
`sources.yml`, incluindo `sha256:` e usando `raw_path:` (não `path:`):

```yaml
- slug: <source-key>
  title: <title>
  type: <type>
  ingested: <today>
  raw_path: <path relativo ao vault root, ex: raw/transcripts/foo.md>
  sha256: <hash>   # obrigatório — compute com: python3 -c "import hashlib; print(hashlib.sha256(open('<path>','rb').read()).hexdigest())"
  pages_created: [<lista de slugs>]
  pages_updated: [<lista de slugs>]
```

### Fix 3 — `sources.yml` template: atualizar comentário de cabeçalho

**Arquivo:** `manifests/sources.yml`

Atualizar o comentário de formato para incluir `raw_path:` e `sha256:`:

```yaml
# Registry of ingested sources
# Format:
# - slug: source-slug
#   title: Source Title
#   type: pdf|article|slides|transcript|repo|web
#   ingested: YYYY-MM-DD
#   raw_path: raw/... (use raw_path for files; url: https://... for web sources)
#   sha256: <64-char hex>   # required for dedup across ingest pathways
#   pages_created: []
#   pages_updated: []

sources: []
```

---

## Testes a adicionar

**Arquivo:** `scripts/tests/batch/test_dedup.py`

Adicionar 3 novos casos de teste:

1. **`test_cross_pathway_dedup_hash_only`** — entry no sources.yml sem `raw_path`
   mas com `sha256` correto → scanner deve detectar como `skipped_duplicate`
   (via Rule 2: different path, same hash).

2. **`test_cross_pathway_dedup_relative_path`** — entry no sources.yml com
   `raw_path` relativo (como escreveria o skill) → `by_path` lookup deve funcionar
   mesmo quando CWD ≠ vault root.

3. **`test_cross_pathway_dedup_slug_mismatch`** — entry com slug divergente
   (`meeting-001-api-gateway`) mas hash correto → deve ainda detectar como
   `skipped_duplicate` (Rule 2 baseia-se apenas em hash, não em slug).

---

## Ordem de implementação

1. Fix `scanner.py` (1 linha) — baixo risco, resolve Causa 2
2. Adicionar testes para as 3 novas situações — TDD para validar os outros fixes
3. Fix `wiki-ingest` SKILL.md Step 9 — instrução mais explícita
4. Fix `manifests/sources.yml` cabeçalho
5. Rodar `pytest scripts/tests/batch/test_dedup.py -v` para confirmar

---

## Arquivos modificados

| Arquivo | Tipo de mudança |
|---------|----------------|
| `scripts/batch/scanner.py` | Bug fix: 3 linhas substituídas |
| `scripts/tests/batch/test_dedup.py` | 3 novos testes |
| `.claude/skills/wiki-ingest/SKILL.md` | Step 9: formato de registro explícito |
| `manifests/sources.yml` | Cabeçalho de comentário atualizado |
