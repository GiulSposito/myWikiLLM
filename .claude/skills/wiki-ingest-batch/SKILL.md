---
name: wiki-ingest-batch
description: Ingests a directory of transcripts in bulk. Two-pass compiler: fast model extracts facts, smart model curates per-page mutation plans, deterministic Python writer applies the result.
---

# Wiki Ingest Batch Skill

## Trigger
Use this skill when the user wants to ingest a directory containing multiple transcripts, meeting recordings, or similar documents in bulk.

For single-source ingestion, use `/wiki-ingest` instead.

---

## Protocol

### Step 0: Verify model configuration (LiteLLM/proxy only)

Check whether a proxy or LiteLLM is in use:
- `ANTHROPIC_BASE_URL` is set in the environment, **or**
- `provider: litellm` is set in `manifests/batch-ingest.yml`

If neither condition is true, skip this step entirely and proceed to Step 1.

Otherwise, run:

```bash
python3 scripts/batch_ingest.py models
```

**Exit 0 — already configured or not needed:**
Nothing to do. Proceed to Step 1.

**Exit 1 — proxy unreachable:**
Warn the user: the proxy catalog could not be reached. Ask whether to continue
with the currently configured model names (which may fail at runtime) or abort.

**Exit 2 — proxy reachable, model names need review:**
Present the full output to the user. It shows:
- All models available in the proxy catalog (with recommendations per pipeline step)
- The currently configured names, flagged if not found in the catalog

Ask the user to choose a model for each of the four pipeline steps:

> "Which model should be used for each pipeline step?
> The recommended models are marked above.
> You can accept the recommendation or pick any model from the list."

Steps and their role:
| Step | Config key | Recommended tier | Why |
|------|-----------|-----------------|-----|
| Extraction | `extraction` | haiku (fast/cheap) | High volume, structured JSON output |
| Curation (new pages) | `curation_new` | haiku (fast/cheap) | Creating pages from scratch, simpler task |
| Resolution | `resolution` | sonnet (smart) | Disambiguating entity mentions |
| Curation (updates) | `curation` | sonnet (smart) | Merging new claims into existing pages |

After the user confirms their choices, edit `manifests/batch-ingest.yml` directly:
1. Update the four model names under `models:`
2. Set `models_configured: true`

Confirm to the user:
> "Model configuration saved. These names will be used for all future runs.
> To reconfigure, set `models_configured: false` in `manifests/batch-ingest.yml`
> and run `python3 scripts/batch_ingest.py models` again."

---

### Step 0.5: Rich document pre-processing

Before scanning, convert any non-Markdown source documents in the target directory:

```bash
python3 scripts/convert_to_md.py <directory> -v
```

This converts every supported rich document (`.pdf`, `.docx`, `.odt`, `.rtf`, `.epub`, `.html`, `.htm`, `.rst`, `.org`, `.tex`) that does not yet have a companion `.md` in the same directory (idempotent — existing `.md` files are skipped). The batch scanner in Step 1 will then discover the converted `.md` files as normal sources.

If any conversions fail, report the errors to the user and ask whether to:
- Continue without the failed files (they will not appear in the scan), or
- Abort and fix the conversion errors first.

If no supported rich documents are present, the script exits cleanly — no action needed.

---

### Step 1: Scan and preflight

```bash
python3 scripts/batch_ingest.py scan <directory>
```

Show the user:
- Discovered: N
- Already ingested: N (skipped)
- Changed sources: N (blocked unless --reingest-changed)
- Ready: N

If `Changed sources > 0` and the user wants to include them, add `--reingest-changed`.

Ask the user to confirm before proceeding. Present the batch ID that was created.

---

### Step 2: Submit extraction

```bash
python3 scripts/batch_ingest.py submit staging/<batch-id>
```

Each transcript is processed independently.
**No wiki files are written at this stage.**

If the extraction runs asynchronously, tell the user to check back shortly.
If it runs synchronously, report how many were extracted vs. failed.

---

### Step 3: Collect results (async path only)

If extraction ran asynchronously, check when it's done:
```bash
python3 scripts/batch_ingest.py status staging/<batch-id>
```

Then collect:
```bash
python3 scripts/batch_ingest.py collect staging/<batch-id>
```

Skip this step if extraction already completed synchronously in Step 2.

---

### Step 4: Normalize and resolve

```bash
python3 scripts/batch_ingest.py normalize staging/<batch-id>
python3 scripts/batch_ingest.py resolve staging/<batch-id>
```

Normalization is deterministic (Unicode, dedup, alias lookup).
Resolution maps entity/concept mentions to canonical wiki pages.
Ambiguous mentions are resolved with an additional model call.
Deferred mentions are never auto-created.

---

### Step 5: Curate

```bash
python3 scripts/batch_ingest.py curate staging/<batch-id>
```

Groups evidence by target wiki page.
One model call per target page — not one per source × target.
Contradiction detection is embedded here.

---

### Step 6: Review the update plan

```bash
python3 scripts/batch_ingest.py plan staging/<batch-id>
```

**Do NOT apply without user review.**

Present the full dry-run summary:
- Sources to create/update
- Concepts to create/update/defer
- Entities to create/update/defer
- Conflicts detected
- Decision proposals
- Estimated file count

Ask the user to confirm. Highlight:
- Any conflicts (the user may want to review those pages first)
- Any deferred resolutions (ambiguous mentions not resolved)
- Decision proposals (require explicit user action to create ADRs)

---

### Step 7: Apply

Only after user explicitly confirms:

```bash
python3 scripts/batch_ingest.py apply staging/<batch-id> --plan-confirmed
```

This is the **only step that writes to `wiki/`**.

The writer:
1. Checks optimistic locks (aborts if files were edited since planning)
2. Writes source pages, concept/entity mutations
3. Updates `manifests/sources.yml` in one transaction
4. Appends one batch log entry to `wiki/log.md`
5. Rebuilds `wiki/index.md`

---

### Step 8: QA report and validation

After apply, run post-apply validation:

```bash
python3 scripts/validate_frontmatter.py
python3 scripts/validate_links.py
python3 scripts/find_orphans.py
```

Present any errors to the user.

Then suggest:
```
Consider running /wiki-lint for a full semantic health check.
```

---

## Resume workflow

If the process was interrupted, resume from where it stopped:

```bash
python3 scripts/batch_ingest.py resume staging/<batch-id>
```

`resume` auto-detects the next step and executes it.

---

## End-to-end shortcut (for small batches)

```bash
python3 scripts/batch_ingest.py run <directory>
```

Runs scan → submit → wait → collect → normalize → resolve → curate → plan.
Still pauses before `apply` for user confirmation.

---

## Safety invariants

- `raw/` is never modified
- `staging/` is gitignored — no intermediate artifacts in version control
- No git commits are made automatically
- The wiki is only modified by `apply` — never by extraction or curation
- Conflicts are never silently resolved
- Deferred resolutions never auto-create pages
- Existing claims are never removed by the batch

---

## Relevant CLI subcommands

| Subcommand | Purpose |
|------------|---------|
| `scan`      | Discover and classify sources |
| `submit`    | Run extraction |
| `status`    | Check async extraction status |
| `collect`   | Collect async extraction results |
| `normalize` | Normalize mentions |
| `resolve`   | Resolve mentions to wiki pages |
| `curate`    | Curate evidence into mutation plans |
| `plan`      | Dry-run: show update plan |
| `apply`     | Write to wiki (requires --plan-confirmed) |
| `resume`    | Auto-detect next step |
| `run`       | End-to-end (pauses before apply) |

