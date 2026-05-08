# PaperHub Skill

Use this skill when the user wants Codex or Claude Code to manage a PaperHub research workspace.

PaperHub connects:

- Zotero account sync
- complete Zotero-derived paper notes
- Obsidian vault generation
- processed Markdown guide/digest import
- normalized `Papers/` and topic `Guides/`
- dashboards, indexes, and agent-accessible project state

## Preferred Commands

Initialize or connect an Obsidian vault:

```bash
paperhub init
paperhub obsidian connect
```

These commands default to `PAPERHUB_VAULT` from `.env`. Pass a path only when creating or switching to a different vault.

Connect Zotero:

```bash
paperhub zotero connect --user-id "$ZOTERO_USER_ID"
```

Sync Zotero account:

```bash
ZOTERO_API_KEY=... ZOTERO_USER_ID=... paperhub zotero sync
```

Import an existing Markdown research source:

```bash
paperhub import markdown /path/to/research-notes --topic "LLM-as-Judge"
paperhub import markdown /path/to/research-notes --topic "LLM-as-Judge" --goal "I need an agent benchmark reading path."
paperhub import markdown /path/to/research-notes --topic "LLM-as-Judge" --apply
```

Build a single-paper evidence bundle and note scaffold:

```bash
paperhub paper enrich smith2024attention --mode quick
paperhub paper enrich smith2024attention --mode deep
```

Review staged imported papers before creating Zotero items:

```bash
paperhub zotero push-staged
paperhub zotero push-staged --write
```

Run diagnostics:

```bash
paperhub doctor
```

Serve MCP tools:

```bash
paperhub mcp serve
```

## Agent Rules

- Treat Zotero as the source of paper-level information, including papers, collections, tags, notes, attachment metadata, annotations, relations, and sync versions.
- Write Zotero-derived information into the corresponding `Papers/` Markdown file for each synced paper.
- Keep paper-level digest, annotations, synthesis content, citation data, and user notes inside the corresponding `Papers/` note.
- Treat Obsidian as the Markdown and visualization surface.
- Use `paperhub import markdown` only as a processed import. It previews by default; use `--apply` only after reviewing the plan. Never copy an external Markdown tree directly into the vault.
- Use `--goal` for user question driven imports. Treat it as task-specific prompt input for Codex, Claude Code, MCP, or a future synthesis service; do not store it in `.env`.
- Never let Markdown import output reference files outside the current vault. Strip or rewrite local source links, absolute paths, repository images, attachments, and provenance paths; preserve web URLs.
- Write paper-like content to `Papers/` and translate guide-like content into the standard `Guides/<topic>/` format.
- Use `paperhub paper enrich` for evidence-first single-paper work. It only resolves indexed papers by Zotero key, Better BibTeX citation key, or paper-note stem; do not fall back to web search or arbitrary paths.
- Treat `.paperhub/evidence/*.json` as internal evidence bundles that support agent writing and linting; keep user-facing paper output under `Papers/`.
- `--mode quick` can be metadata-only. `--mode deep` must have PDF text or Zotero annotations and should fail rather than pretending a deep-reading note is complete.
- Stage imported paper digests that are not reconciled with Zotero as `Papers/IMPORTED-*.md`; only create Zotero items through the explicit `paperhub zotero push-staged --write` command.
- Treat `Guides/<topic>/` as the topic ownership and slugging boundary; do not create a separate `PaperHub/Topic/` path.
- Do not put Markdown source paths in `.env`; they are task inputs.
- Prefer updating generated regions and indexes rather than overwriting human-authored content.
- Do not describe simple Canvas, Mermaid, file-link, or paper-list views as knowledge graphs.
- Do not generate top-level `Collections/`, `Concepts/`, `Claims/`, `Reading Paths/`, or `Templates/` directories for the current MVP.

## Topic Guide Workflow

Use this shape for both processed Markdown imports and agent-generated topic guides:

```text
topic or Markdown source
  -> discover candidate papers and paper-like content
  -> read the main imported guide material and infer a section plan
  -> reconcile or stage missing papers
  -> resolve author/year metadata before choosing filenames
  -> update normalized Papers/<citation-key>.md notes
  -> create Guides/<topic>/<topic>.md as the main guide
  -> create Guides/<topic>/sections/*.md for substantial themes, methods, claims, benchmarks, paper clusters, or reading steps
  -> link every paper mentioned in a literature-backed section to a Papers/ note
  -> emit guide-section-cites-paper relationship data
  -> run diagnostics for ambiguous imports and broken guide links
```

The main guide is the synthesis and navigation layer. It should not be the only Markdown file for a substantial survey, reading list, benchmark review, or multi-paper research note. Do not split mechanically by every source file, paper digest, or heading; first decide the smallest useful set of sections that matches the source author's structure. Section paper lists must use wikilinks to `Papers/`; create staged citation-key `Papers/` notes for imported papers that are not yet reconciled with Zotero. Do not write `unknown` or `nd` filename parts; resolve missing author/year metadata first.
