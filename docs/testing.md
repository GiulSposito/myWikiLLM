# Testing Guide

Complete walkthrough to verify that the wiki system is working correctly after a
fresh clone. Covers environment setup, automated unit tests, manual smoke tests
for every CLI subcommand, validation scripts, and Claude Code slash commands.

---

## 1. Setup after clone

### 1.1 Clone and enter the vault

```bash
git clone https://github.com/GiulSposito/myWikiLLM.git llmwiki
cd llmwiki
```

### 1.2 Python version

Requires Python ≥ 3.11.

```bash
python3 --version   # must be 3.11 or higher
```

### 1.3 Install dependencies

```bash
# Core dependencies (scanner, extractor, normalizer, resolver, curator, writer)
pip install -e .

# Add LiteLLM support (required when provider: litellm or ANTHROPIC_BASE_URL is set)
pip install -e ".[litellm]"

# Add test runner
pip install -e ".[dev]"
```

### 1.4 Configure environment

```bash
cp .env.example .env
# Edit .env and fill in the values:
#   ANTHROPIC_API_KEY    — required for provider: anthropic (direct Anthropic API)
#   ANTHROPIC_BASE_URL   — required when routing through a LiteLLM proxy
#   ANTHROPIC_AUTH_TOKEN — optional bearer token for proxies that require authentication
```

`.env` is gitignored. Never commit it.

### 1.5 Quick sanity check

```bash
python3 -c "from scripts.batch.config import load_config; cfg = load_config(); print('provider:', cfg.provider)"
python3 scripts/batch_ingest.py --help
```

Expected: prints the provider name and lists all subcommands without errors.

---

## 2. Automated unit tests

```bash
python3 -m pytest scripts/tests/ -v
```

Expected result: **all tests pass** (95 tests as of 2026-08).

| Test file | What it covers |
|-----------|---------------|
| `test_dedup.py` | Source deduplication rules, state lifecycle, BatchItem transitions |
| `test_extractor.py` | Extraction prompts, chunking, chunk-merge, cache-control headers |
| `test_idempotency.py` | Collect idempotency, state save/load roundtrip, JSON schema stability |
| `test_normalizer.py` | Unicode normalisation, slugify, alias lookup, entity/concept dedup |
| `test_planner.py` | Evidence grouping, update-plan construction, append-only invariant |
| `test_qa.py` | Post-extraction quality gate checks |
| `test_resolver.py` | Fuzzy match scoring, auto-resolve threshold, candidate selection |
| `test_scanner.py` | File discovery, custom_id generation, SHA-256 determinism |
| `test_writer.py` | Page rendering, mutation application, optimistic lock, language labels |

To run a single file:

```bash
python3 -m pytest scripts/tests/batch/test_scanner.py -v
```

---

## 3. CLI smoke tests

All smoke tests use the fixtures bundled in `scripts/tests/batch/fixtures/` (10
synthetic meeting transcripts). These files are safe to scan and process — they
never touch `raw/` and staging is gitignored.

> **Rule:** always run `models` first when using a proxy or LiteLLM.

---

### 3.1 `models` — verify model configuration

```bash
python3 scripts/batch_ingest.py models
```

| Condition | Exit code | Expected output |
|-----------|-----------|----------------|
| `provider: anthropic`, no proxy | 0 | Lists 4 configured model names |
| `models_configured: true` | 0 | "Models already configured" + current names |
| Proxy reachable, not configured | 2 | Full catalog table + per-role recommendations |
| Proxy unreachable | 1 | Error with proxy URL and instructions |

If exit code is 2, follow the interactive setup described in Step 0 of
`.claude/skills/wiki-ingest-batch/SKILL.md` to configure and lock model names.

---

### 3.2 `scan` — discover source files

```bash
python3 scripts/batch_ingest.py scan scripts/tests/batch/fixtures/
```

Expected:

```
Discovered:        10
Already ingested:   0
Changed sources:    0
Ready:             10

Batch created: staging/<batch-id>
Batch ID: <batch-id>

Next step: python3 scripts/batch_ingest.py submit staging/<batch-id>
```

Record the batch path printed — it is needed for all subsequent steps.

If the batch already exists (re-running scan on the same directory), you'll get:
```
Batch already exists: staging/<batch-id>
Use 'resume' to continue or delete the staging directory to restart.
```
In that case, use `resume` (§3.9) or delete `staging/<batch-id>/` and re-scan.

---

### 3.3 `submit` — run extraction

> Requires a working API connection and valid model names (check §3.1 first).

```bash
python3 scripts/batch_ingest.py submit staging/<batch-id>
```

**LiteLLM / synchronous path** (provider: litellm or ANTHROPIC_BASE_URL set):

```
Provider: litellm (synchronous, 10 items)
Extracted: 10  Failed: 0

Next step: python3 scripts/batch_ingest.py normalize staging/<batch-id>
```

JSON files appear in `staging/<batch-id>/extraction/`.

**Anthropic Batch API / async path** (provider: anthropic, no proxy):

```
Building 10 extraction requests...
Submitting extraction batch...
  Provider batch: msgbatch_...

Check status with: python3 scripts/batch_ingest.py status staging/<batch-id>
```

In this case, proceed to §3.4.

---

### 3.4 `status` — check async batch (async path only)

```bash
python3 scripts/batch_ingest.py status staging/<batch-id>
```

Repeat until `processing_status: ended`. Typical time: 1–5 minutes for 10 items.

---

### 3.5 `collect` — retrieve async results (async path only)

```bash
python3 scripts/batch_ingest.py collect staging/<batch-id>
```

Expected:

```
Collected: 10, Failed: 0
```

Skip §3.4–3.5 if extraction ran synchronously (LiteLLM path).

---

### 3.6 `normalize` — clean and deduplicate mentions

```bash
python3 scripts/batch_ingest.py normalize staging/<batch-id>
```

Expected:

```
Normalized: 10 items
```

No Unicode errors, no alias lookup failures.

---

### 3.7 `resolve` — map mentions to wiki pages

```bash
python3 scripts/batch_ingest.py resolve staging/<batch-id>
```

Expected:

```
Resolved: N, Deferred: M
```

`Deferred > 0` is normal — it means some mentions were ambiguous and were not
auto-resolved. They will be skipped (not auto-created) during apply.

---

### 3.8 `curate` — produce mutation plans

```bash
python3 scripts/batch_ingest.py curate staging/<batch-id>
```

Expected:

```
Groups to curate: N
Mutation plans produced: N
```

One JSON file per target wiki page in `staging/<batch-id>/curation/`.

---

### 3.9 `plan` — dry-run review (mandatory before apply)

```bash
python3 scripts/batch_ingest.py plan staging/<batch-id>
```

Prints a full summary:
- Sources to create / update
- Concepts to create / update / defer
- Entities to create / update / defer
- Conflicts detected
- Estimated file count

**No files in `wiki/` are written at this step.**

---

### 3.10 `apply` — write to wiki

> Use a separate branch. The test fixtures generate real wiki pages.

```bash
git checkout -b test/batch-apply

python3 scripts/batch_ingest.py apply staging/<batch-id> --plan-confirmed
```

`--plan-confirmed` is required. Without it, the command prints an error and exits.

If `require_clean_git: true` (default), the working tree must be clean before apply:

```bash
git status   # must show "nothing to commit"
```

After apply, verify:

```bash
git diff --stat HEAD
python3 scripts/validate_frontmatter.py
python3 scripts/validate_links.py
python3 scripts/find_orphans.py
```

Clean up the test branch:

```bash
git checkout batch-ingest   # or your working branch
git branch -D test/batch-apply
```

---

### 3.11 `resume` — recover an interrupted pipeline

If a pipeline run was interrupted (network error, Ctrl+C), resume from where it stopped:

```bash
python3 scripts/batch_ingest.py resume staging/<batch-id>
```

`resume` inspects the batch state and automatically executes the next pending step.

---

### 3.12 `run` — end-to-end shortcut

Runs all steps from scan through plan in one command. Pauses before `apply`.

```bash
# Clean up any leftover staging first
rm -rf staging/

python3 scripts/batch_ingest.py run scripts/tests/batch/fixtures/
```

Expected: all steps complete, then a prompt to review the plan and run `apply` manually.

---

## 4. Validation scripts

These scripts are deterministic (no LLM) and can run without Claude Code.

```bash
# Verify required frontmatter fields and taxonomy values on all wiki/ pages
python3 scripts/validate_frontmatter.py

# Verify all [[wikilinks]] resolve to existing pages
python3 scripts/validate_links.py

# List pages with no inbound links (informational)
python3 scripts/find_orphans.py

# Regenerate wiki/index.md from frontmatter (run after batch edits)
python3 scripts/rebuild_index.py
```

Expected on a clean vault: 0 errors from `validate_frontmatter` and `validate_links`.
`find_orphans` is informational — some orphans are expected (e.g. `wiki/index.md`).

---

## 5. Slash commands (require Claude Code)

Open Claude Code from the vault root:

```bash
claude
```

Then invoke each command:

### `/wiki-ingest`

```
/wiki-ingest raw/transcripts/<transcript>.md
```

Verifications:
- `wiki/sources/<slug>.md` created
- `wiki/entities/` and `wiki/concepts/` pages created or updated
- `wiki/index.md` and `wiki/log.md` updated
- `manifests/sources.yml` has a new entry

```bash
git diff --stat
python3 scripts/validate_frontmatter.py
python3 scripts/validate_links.py
```

### `/wiki-query`

```
/wiki-query "What are the main concepts discussed so far?"
```

Expected: a cited answer with `([[source-slug]])` references for every factual claim.

### `/wiki-lint`

```
/wiki-lint
```

Expected: a report at `outputs/reports/wiki-lint-YYYY-MM-DD.md`. Review it for
dead links, orphans, missing frontmatter, and unresolved conflicts.

### `/wiki-ingest-batch`

```
/wiki-ingest-batch
```

Claude will guide through Steps 0–8 defined in
`.claude/skills/wiki-ingest-batch/SKILL.md`. Step 0 runs `models` automatically
when a proxy is detected.

### `/wiki-map`

```
/wiki-map <concept-slug>
```

Expected: a file created in `maps/canvas/`, `maps/mermaid/`, or `maps/excalidraw/`
depending on the topic type.

### `/wiki-review`

```
/wiki-review raw/transcripts/<transcript>.md
```

Like `/wiki-ingest` but with two mandatory user confirmation gates before any file
is written.

---

## 6. Troubleshooting quick reference

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| `models` exits 1 | Proxy unreachable | Check `ANTHROPIC_BASE_URL` and proxy status |
| `models` exits 2 | `models_configured: false` | Follow Step 0 of wiki-ingest-batch skill |
| `submit` fails with model error | Model name not in proxy catalog | Run `models`, update `manifests/batch-ingest.yml` |
| `apply` fails with "working tree not clean" | Uncommitted files exist | `git stash` or commit before applying |
| `validate_frontmatter` errors | Missing or invalid YAML field | Edit the flagged page; see `manifests/taxonomy.yml` for valid values |
| `validate_links` dead links | Wikilink points to non-existent page | Create the missing page or fix the link slug |
| `pytest` import errors | Dependencies not installed | `pip install -e ".[dev]"` |
