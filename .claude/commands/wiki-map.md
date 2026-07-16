# Wiki Map

Triggered by: `/wiki-map <tópico>`

## Purpose

Generate a visual map of a domain, concept, or set of wiki pages. Choose the output format based on the nature of the request, then save the map to the appropriate directory and link it from the relevant wiki page.

## Phase 1 — Discover relevant pages

Search `wiki/` for all pages related to the topic:
- Check `wiki/index.md` for pages listed under the topic's domain.
- Search page filenames and aliases for matches to the topic keyword(s).
- Read `wiki/concepts/` and `wiki/entities/` pages that match the topic.
- Follow wikilinks from matching pages to find closely related pages (one hop).

Build a candidate set of pages. Read each candidate page in full to understand:
- Its relationships to other pages (from wikilinks and `## Relationships` or `## Related Concepts` sections).
- Its type (`concept`, `entity`, `project`, `source`, etc.).
- Its status and confidence level.

---

## Phase 2 — Choose output format

Evaluate the nature of the request and choose ONE format:

### Canvas (`.canvas` file) — use when:
- The goal is knowledge navigation or exploration of the vault.
- The nodes should link directly to real wiki pages the user can open.
- The structure is organic (clusters, relations) rather than strictly hierarchical.
- The user wants to browse and navigate within Obsidian.

Output directory: `maps/canvas/`
Skill to use: `json-canvas`

### Mermaid (block inside `.md` file) — use when:
- The goal is to show architecture, sequence, dependencies, or formal structure.
- The relationships have clear directionality or process order.
- The map will be shared, exported, or embedded in documentation.
- The structure is hierarchical or flow-based (flowchart, sequence, class diagram).

Output directory: `maps/mermaid/`
Skill to use: `mermaid-visualizer`

### Excalidraw (`.excalidraw.md` file) — use when:
- The goal is visual communication, narrative, or presentation.
- The map will be shown to an audience unfamiliar with the vault structure.
- A hand-drawn, informal visual style is appropriate.
- Annotations, callouts, or freeform layout are needed.

Output directory: `maps/excalidraw/`
Skill to use: `excalidraw-diagram`

If the user explicitly requests a specific format in their message, use that format regardless of the above heuristics.

---

## Phase 3 — Generate the map

Invoke the appropriate skill with the full set of pages, relationships, and topic context gathered in Phase 1.

### Canvas rules:
- Each node must correspond to a real wiki page.
- The `file` field in each node must be the relative path from the vault root to the wiki page (e.g., `wiki/concepts/transformer.md`).
- Group nodes by type: concepts in one cluster, entities in another, sources in a third.
- Edges must represent actual wikilinks between pages (not inferred relationships).
- Color-code node groups: use distinct colors for concept/entity/source/project types.
- The canvas must be valid JSON conforming to the Obsidian Canvas spec.

### Mermaid rules:
- Choose the appropriate diagram type: `graph TD` for dependencies/hierarchy, `sequenceDiagram` for processes, `classDiagram` for structural relationships.
- Node labels must use the page's display title (from frontmatter `title:` or the page heading), not the filename slug.
- Include only relationships that are explicitly stated in wiki pages — do not infer edges.
- Add a brief title comment at the top of the diagram block.

### Excalidraw rules:
- Use clear, readable labels. Prefer full titles over slugs.
- Group related nodes visually with bounding boxes or color regions.
- Use arrows to show directionality of relationships.
- Include a legend if more than two node types are present.
- The output must be a valid `.excalidraw.md` file (Markdown file containing the Excalidraw JSON in a fenced block).

---

## Phase 4 — Save the map

Derive a filename from the topic: lowercase, hyphens only. Example: `transformer-architecture` or `openai-ecosystem`.

Save to the appropriate directory:
- Canvas: `maps/canvas/<topic-slug>.canvas`
- Mermaid: `maps/mermaid/<topic-slug>.md`
- Excalidraw: `maps/excalidraw/<topic-slug>.excalidraw.md`

Create the target directory if it does not exist.

---

## Phase 5 — Link the map from the wiki

Update the wiki to reference the generated map:
- If a `wiki/concepts/<topic-slug>.md` or `wiki/entities/<topic-slug>.md` page exists for the topic: add a `## Maps` section (or append to it if it exists) with a link to the generated file.
- If no single wiki page owns the topic: add the map reference to `wiki/index.md` under the appropriate section.
- Use a readable link format: `[<Topic> Map](<relative path to map file>)`.

---

## Phase 6 — Report to user

Display a summary:

```
Wiki Map generated — <topic>

Format:   <Canvas|Mermaid|Excalidraw>
Pages included: N
Edges (relationships): M
Saved to: <full path to map file>
Linked from: <wiki page where the map was added>
```

If the map was saved as a Canvas file, remind the user: "Open this file in Obsidian to navigate interactively."
If the map was saved as a Mermaid file, remind the user: "Render with any Mermaid-compatible viewer or in Obsidian with the Mermaid plugin."
If the map was saved as an Excalidraw file, remind the user: "Open in Obsidian with the Excalidraw plugin, or at excalidraw.com."
