---
name: wiki-lint
description: Runs a full knowledge health check on the wiki. Finds dead links, orphan pages, duplicate concepts, missing frontmatter, unresolved conflicts, status issues, and index gaps.
---

# Wiki Lint Skill

## Trigger
Use when the user wants to audit the health of the wiki, or after a batch ingestion. Run after every 3+ source ingest session.

## Protocol

### Checks to run

1. **Dead links**: wikilinks `[[...]]` pointing to non-existent files. Use `python3 scripts/validate_links.py` for a deterministic baseline, then supplement with semantic checks.

2. **Orphan pages**: pages with no inbound links from other wiki pages. Use `python3 scripts/find_orphans.py` for a deterministic baseline. Note: pages inside `wiki/data-dictionary/` that are linked from their domain `index.md` are NOT true orphans — the linter should cross-check this.

3. **Duplicate aliases**: same alias in two different files.

4. **Near-duplicate concepts**: pages with very similar names or content that should be merged. Do not merge automatically — flag and propose consolidation.

5. **Missing frontmatter fields**: any of `type`, `status`, `confidence`, `created`, `updated`, `sources`, `aliases`, `tags` absent. Use `python3 scripts/validate_frontmatter.py` for deterministic check.

6. **Pages without sources**: concept/entity pages with empty `sources: []`. These are ungrounded — flag as `needs-review`.

7. **Unresolved conflicts**: pages with `status: conflict`. Report age (days since `updated:`). Conflicts older than 14 days should be escalated.

8. **Stale needs-review**: pages with `status: needs-review` where `updated:` is more than 30 days ago.

9. **Index gaps**: pages in `wiki/` not listed in `wiki/index.md`. Run `python3 scripts/rebuild_index.py` to fix, or list gaps for manual review.

10. **Log gaps**: sources in `manifests/sources.yml` with no corresponding entry in `wiki/log.md`.

11. **Status never promoted** *(new)*: list all concept and entity pages that have `status: draft` AND have 2 or more entries in their `sources:` list. These are eligible for promotion to `active` but have not been reviewed. Report them as "promotion candidates" — do not change status automatically.

12. **Data-dictionary not in main index** *(new)*: verify that `wiki/data-dictionary/*/index.md` pages (domain-level hubs) appear in `wiki/index.md` under the "Data Dictionaries" section. Report any domain index that is missing from the main index.

### Output
- **ALWAYS** save the full report to `outputs/reports/wiki-lint-YYYY-MM-DD.md` — this is mandatory, not optional
- Print summary to terminal
- Do NOT auto-fix anything — only report

### Report structure

```markdown
# Wiki Lint Report — YYYY-MM-DD

## Summary

| Check | Issues |
|-------|--------|
| Dead links | N |
| Orphan pages | N |
| Duplicate aliases | N |
| Near-duplicate concepts | N |
| Missing frontmatter | N |
| Unsourced pages | N |
| Unresolved conflicts | N |
| Stale needs-review | N |
| Index gaps | N |
| Log gaps | N |
| Status promotion candidates | N |
| Data-dictionary index gaps | N |

## Dead Links
...

## Promotion Candidates
Pages eligible for draft → active (2+ sources, not yet reviewed):
- [[concept-slug]] — N sources

## Data-Dictionary Index Gaps
Domain indexes missing from wiki/index.md:
- wiki/data-dictionary/<domain>/index.md
```
