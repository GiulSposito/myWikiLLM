# Plan: LiteLLM Model Selection — Interactive Configuration

## Problem

`batch_ingest.py` hardcodes Anthropic model names as defaults
(`claude-haiku-4-5-20251001`, `claude-sonnet-5`). When running through a
LiteLLM proxy (`ANTHROPIC_BASE_URL` set or `provider: litellm`), those names
almost certainly don't exist in the proxy's catalog, causing silent fallbacks or
runtime failures.

Current `resolve_model_names()` in `config.py` does auto-resolve via keyword
matching (haiku → extraction, sonnet → curation/resolution), but:
- It picks the **first matching model** silently — the user never sees what was chosen
- If no match is found, it falls back to the Anthropic default name (which is wrong for LiteLLM)
- Resolved names are **only in-memory** — every run re-queries and re-picks silently
- The user has no way to control which specific model goes to which pipeline step

## Goal

On first run through LiteLLM/proxy, detect that model names need configuration,
query available models, present them to the user with recommendations, let the
user choose one per pipeline step, and persist the choices to
`manifests/batch-ingest.yml` so all future runs use those names directly.

---

## Proposed Changes

### 1. `scripts/batch/config.py`

**a) Add `models_configured: bool = False` to `BatchIngestConfig`**

A flag that means "the user has explicitly chosen and persisted model names for
this environment." When `True`, `resolve_model_names()` becomes a no-op — the
configured names are used as-is without keyword matching.

**b) Load `models_configured` in `load_config()`**

```python
cfg.models_configured = bool(raw.get("models_configured", False))
```

**c) Modify `resolve_model_names()` to respect the flag**

```python
def resolve_model_names(cfg, vault_root=VAULT_ROOT):
    if cfg.models_configured:
        return   # user has explicitly set models — skip auto-resolution
    ...  # existing keyword-matching logic
```

**d) Extract `list_proxy_models(base_url, token) -> list[str]`**

Pull the HTTP request logic out of `resolve_model_names()` into a reusable
function so the new CLI subcommand can call it independently.

---

### 2. `scripts/batch_ingest.py`

**Add new `models` subcommand**

```
python3 scripts/batch_ingest.py models
```

Behavior:
1. Reads `manifests/batch-ingest.yml` (provider, base URL, current model names, `models_configured`)
2. If `models_configured: true` → prints current models and exits 0
3. If `ANTHROPIC_BASE_URL` is set or `provider: litellm` → queries proxy `/v1/models`
   - On success: prints available models + current configured models + recommendation per step → exits **2** (needs configuration)
   - On failure (proxy unreachable): prints warning, exits 1
4. If neither proxy nor litellm → prints "Using direct Anthropic — no model resolution needed" → exits 0

Exit codes are meaningful:
- `0` = already configured or not needed
- `1` = error (proxy unreachable, bad response)
- `2` = needs interactive configuration (models available, user must choose)

Output format (exit 2) — human-readable table for the SKILL:
```
Available models (12 found):
  anthropic.claude-haiku-4-5  ← recommended for extraction, curation_new
  anthropic.claude-sonnet-5   ← recommended for resolution, curation
  openai.gpt-4o-mini
  ...

Current configuration:
  extraction:    claude-haiku-4-5-20251001  [NOT FOUND in proxy catalog]
  resolution:    claude-sonnet-5            [NOT FOUND in proxy catalog]
  curation:      claude-sonnet-5            [NOT FOUND in proxy catalog]
  curation_new:  claude-haiku-4-5-20251001  [NOT FOUND in proxy catalog]
```

Recommendation logic (same keyword heuristics as before, but shown to user):
- extraction / curation_new → keyword `haiku` → cheapest/fastest tier
- resolution / curation → keyword `sonnet` → smarter, handles ambiguity

---

### 3. `.claude/skills/wiki-ingest-batch/SKILL.md`

**Add Step 0: Verify model configuration** (before Step 1: Scan)

```
### Step 0: Verify model configuration (LiteLLM/proxy only)
```

Logic:
1. Check if `ANTHROPIC_BASE_URL` env var is set OR `provider: litellm` in
   `manifests/batch-ingest.yml`
2. If neither → skip this step entirely
3. Run `python3 scripts/batch_ingest.py models`
4. **Exit 0** → already configured, skip
5. **Exit 1** → warn user, offer to continue anyway or abort
6. **Exit 2** → present the available models table and ask:
   > "Which model do you want to use for each step?
   > (Recommended models are marked above)"
   
   For each of the 4 roles (extraction, resolution, curation, curation_new),
   the user picks from the available list (or accepts the recommended one).
   
7. After user selects, Claude directly edits `manifests/batch-ingest.yml`:
   - Updates the 4 model names under `models:`
   - Adds `models_configured: true`
   
8. Confirm to the user: "Model configuration saved. These names will be used
   for all future runs."

---

### 4. `manifests/batch-ingest.yml`

Add a commented entry explaining the new flag (not set by default — only written
after interactive configuration):

```yaml
# Set to true after running the model configuration wizard (Step 0 of wiki-ingest-batch).
# When true, model names above are used exactly as written, bypassing auto-resolution.
# models_configured: false
```

---

## What stays the same

- Auto keyword-resolution in `resolve_model_names()` still runs for all
  non-configured cases (direct script calls, old batches, CI)
- All existing pipeline subcommands and their interfaces
- `provider: anthropic` direct path is completely unaffected
- No changes to extractor, curator, resolver, writer, or any pipeline logic

---

## Implementation Order

1. `config.py` — add flag, extract `list_proxy_models()`, guard in `resolve_model_names()`
2. `batch_ingest.py` — add `models` subcommand
3. `SKILL.md` — add Step 0
4. `batch-ingest.yml` — add comment for new field
