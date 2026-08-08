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

