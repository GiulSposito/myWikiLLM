# Wiki Review

Triggered by: `/wiki-review <caminho-ou-tópico>`

## Purpose

Supervised ingestion for strategic, sensitive, or high-stakes documents — RFPs, proposals, confidential materials, partner documents, or any source where automated ingestion without human review would be inappropriate. Every destructive step requires explicit user approval before proceeding.

## Core Constraint

This is a supervised, step-by-step workflow with mandatory pause points. NEVER apply changes to the wiki without explicit user confirmation at each approval gate. If the user does not confirm, stop and wait. Do not proceed to the next phase without a clear "yes" or equivalent affirmative response.

## Workflow

---

### Step 1 — Read the document

Read the document at the specified path. If it is a URL, fetch it. Do not process the content yet — only load it.

Confirm to the user: "Document loaded: `<title or filename>`, `<word count>` words. Proceeding to extraction."

---

### Step 2 — Factual extraction via source-reader

Invoke the `source-reader` subagent with the document content. The subagent must return:
- A factual summary of the document.
- A structured list of factual claims.
- **Entities found**: names, types (company/person/product/tool/organization), brief description.
- **Concepts found**: names, types (framework/method/pattern/idea), brief description.
- **Relations proposed**: `<entity/concept A>` → `<relation>` → `<entity/concept B>`.
- **Projects, decisions, standards** found (if any).

Do NOT write any files yet.

---

### Step 3 — Show extraction to user

Present the extraction results to the user in a readable format:

```
## Entities found (<N>)
- <Name> (type: <type>) — <one-line description>
- ...

## Concepts found (<N>)
- <Name> (type: <type>) — <one-line description>
- ...

## Relations proposed (<N>)
- [[<A>]] → <relation> → [[<B>]]
- ...

## Projects / Decisions / Standards (<N>)
- <Name> — <brief description>
- ...
```

---

### GATE 1 — Approval to proceed with extraction

Ask the user explicitly:

"Posso prosseguir com esta extração? (sim/não)"

Wait for response. If the user says no or asks for changes: adjust the extraction list according to their instructions and re-present. Only continue when the user explicitly confirms.

---

### Step 4 — Compute diff

For each entity, concept, project, decision, or standard approved:
- Check if the corresponding wiki page already exists.
- If it exists: compute a diff showing exactly what lines/sections would be added or changed.
- If it does not exist: show the full content of the new page that would be created.

Also compute:
- The new entry that would be added to `wiki/index.md`.
- The new log entry that would be appended to `wiki/log.md`.
- The new entry that would be added to `manifests/sources.yml`.

Present the complete diff to the user, organized by file:

```
## Diff Preview

### NEW: wiki/sources/<slug>.md
<full content of new file>

### MODIFIED: wiki/concepts/<existing-concept>.md
+ <lines to be added>
- <lines to be removed (if any)>

### NEW: wiki/entities/<entity-slug>.md
<full content of new file>

... (all files)

### MODIFIED: wiki/index.md
+ <lines to be added>

### MODIFIED: wiki/log.md
+ <new log entry>

### MODIFIED: manifests/sources.yml
+ <new entry>
```

---

### GATE 2 — Approval to apply changes

Ask the user explicitly:

"Posso aplicar estas alterações? (sim/não)"

Wait for response. If the user says no or requests modifications: adjust according to their instructions and re-present the diff. Only proceed when the user explicitly confirms.

---

### Step 5 — Apply changes

Apply all approved changes:
- Create new wiki pages.
- Update existing wiki pages (append only — do not overwrite existing content unless the user explicitly approved a specific overwrite in Gate 2).
- Update `wiki/index.md`.
- Append to `wiki/log.md`.
- Update `manifests/sources.yml`.

Ensure all created/updated pages include:
- Complete frontmatter.
- Wikilinks `[[...]]` for all referenced entities and concepts.

---

### Step 6 — Validation

Run the following validation scripts:

```
python scripts/validate_frontmatter.py
python scripts/validate_links.py
```

If either script reports errors: show the errors to the user and explain what needs to be fixed. Do NOT silently ignore validation failures.

---

### Step 7 — Final report

Display a summary:

```
Wiki Review complete — <slug>

Pages created:   N
Pages updated:   M
Validation:      PASSED / FAILED (<error count> errors)

Created: <list of new pages>
Updated: <list of updated pages>

Suggested commit message:
  wiki: ingest <title> — <N> pages created, <M> updated

Run `git diff` to review before committing.
```

Do NOT run git commands. Only suggest the commit message.
