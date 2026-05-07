# CLAUDE.md

Guidance for Claude Code and Claude-based agents working in this repository.

## What This Project Is

PaperHub is a local-first literature knowledge manager for AI-assisted research.

It connects:

- Zotero as the source of papers, collections, tags, notes, attachment metadata, annotations, relations, and sync versions
- Obsidian as the human-readable research vault
- CLI commands for easy local operation
- MCP tools for agent access
- Codex / Claude Code plugins for workflow automation

## How Claude Code Should Think About PaperHub

Treat this repository as a research operating system kernel, not as a single editor extension.

The MVP user-visible vault contract should stay simple:

```text
Papers/
Guides/
```

Internally, PaperHub can model papers, topics, guide sections, annotations, synthesis content,
import plans, import reports, and future typed relationships. Those abstractions should support the
`Papers/` and `Guides/` output contract rather than becoming extra top-level vault folders.
Plugin-specific features should wrap the core, not replace it.

## Design Corrections To Preserve

Several early choices were corrected during project setup. Preserve these as standing rules:

- Do not hard-code personal absolute paths such as `/Users/<name>/...` into reusable defaults.
- Use `~` or `/path/to/...` in examples unless documenting a user-provided path.
- `.env` is for durable connection/config values, not normal task inputs.
- `PAPERHUB_VAULT` belongs in `.env` because it is the default local Obsidian vault write target.
- PaperHub supports processed Markdown import through `paperhub import markdown`.
- Markdown import must parse, normalize, deduplicate, and write into `Papers/` and `Guides/`; it must not copy an external directory tree directly.
- Generated Markdown import output must not reference files outside the current vault. Strip or rewrite local source links, absolute paths, repository images, attachments, and provenance paths; preserve web URLs.
- Substantial topic imports or generated topic guides must not collapse into one Markdown file. They should create a main guide plus graph-visible section notes that link back to `Papers/`.
- Imported guide structure requires judgment. Read the imported guide first, infer the author's intended section plan, and avoid mechanical splitting by every source file, paper digest, or heading.
- Paper notes should use citation-key filenames such as `smith2024attention.md`. Resolve author/year metadata before writing paper notes; do not generate `unknown` or `nd` filename parts.
- Markdown import source paths are task inputs. Do not put them into `.env`.
- Keep source and target separate: Zotero is the read source; Obsidian vault is the write target.
- Do not assume an official Obsidian cloud API key exists for operating on a named vault. The MVP uses local vault files.
- A first-party PaperHub Obsidian plugin is a future upgrade path, not a replacement for the current local-vault integration.
- When a user points out a conceptual mistake, update `AGENTS.md`, `CLAUDE.md`, README, skills, and CLI help if the correction changes project behavior.

## Environment Variables

Use `.env` for:

```text
ZOTERO_API_KEY
ZOTERO_USER_ID
ZOTERO_LIBRARY_TYPE
PAPERHUB_VAULT
```

Do not introduce a global Markdown source environment variable. Markdown import paths belong on the command line.

```bash
# Do not add this:
PAPERHUB_MARKDOWN_SOURCE=/some/research/repo
```

## Obsidian Integration

The current primary path is:

```text
PaperHub -> local Obsidian vault folder -> Obsidian app -> Obsidian Sync
```

PaperHub should write normal Markdown files into a local vault. It should not describe this as logging into Obsidian or directly controlling an Obsidian cloud account.

Do not describe a simple Canvas, Mermaid diagram, file-link view, or paper list as a knowledge graph.
Graph-like visualizations require explicit typed relationships between research objects and should stay
out of the MVP until those relationships exist.

The current generated vault should stay simple:

```text
Papers/
Guides/
```

Do not generate top-level `Collections/`, `Concepts/`, `Claims/`, `Reading Paths/`, or `Templates/`
folders unless a later design explicitly reintroduces them.

## Suggested Future Claude Code Commands

These are not implemented yet, but they describe the desired interaction model:

```text
/paperhub:init
/paperhub:doctor
/paperhub:import-zotero
/paperhub:import_markdown
/paperhub:sync
/paperhub:paper-note
/paperhub:topic-guide
/paperhub:deep-research
/paperhub:survey-outline
```

## Suggested Future Claude Code Workflows

### Sync Zotero Account

1. Check PaperHub config.
2. Check Zotero account connection.
3. Import all available paper metadata, collections, tags, notes, attachment metadata, annotations, relations, and sync versions.
4. Update the PaperHub index and paper index.
5. Generate or update the corresponding `Papers/` Markdown file for every synced Zotero paper.
6. Organize Zotero-derived collections, tags, notes, attachment metadata, annotations, relations, and sync versions inside each paper note.
7. Report missing metadata, PDFs, abstracts, or duplicate papers.

### Import Markdown

1. Read the source tree as task input.
2. Classify heterogeneous Markdown files as paper digests, topic guides, guide sections, supporting notes, or unknown files.
3. Read the main guide material and infer a small section plan that matches the author's structure.
4. Split substantial guide material into section nodes by H2/H3 headings, themes, methods, benchmark families, paper clusters, claims, or reading steps only when those boundaries are meaningful.
5. Extract paper metadata, citations, BibTeX, digests, and guide references.
6. Reconcile papers against Zotero by DOI, URL, title, and Zotero key when available.
7. Resolve missing author/year metadata from Zotero, source manifests, DOI/arXiv/OpenReview/ACL metadata, or another reviewable source.
8. Write normalized paper notes into `Papers/` using citation-key filenames.
9. Translate guide material into the standard `Guides/<topic>/` format: one main guide for navigation and synthesis, plus section files or subfolders for substantial research structure.
10. Strip or rewrite any generated references to local files outside the current vault.
11. Link literature-backed guide sections to `Papers/` notes and emit `guide-section-cites-paper` relationship data.
12. Report unmapped files or ambiguous paper matches instead of silently copying them.

### Generate Topic Guide

1. Ask for the user's topic if not provided.
2. Search the web and the existing PaperHub/Zotero library for relevant literature.
3. Add missing papers to Zotero or stage them for Zotero import, with explicit metadata.
4. Generate or update normalized paper notes in `Papers/`.
5. Create `Guides/<topic>/` with a main guide Markdown file that acts as the table of contents, reading path, and synthesis surface.
6. Create section notes under `Guides/<topic>/sections/` for substantial themes, methods, benchmark families, paper clusters, claims, or reading steps.
7. Link every literature-backed section back to the relevant `Papers/` notes.
8. Emit a `guide-section-cites-paper` relationship manifest for later graph work.
9. Run diagnostics for broken guide links, ambiguous imports, missing abstracts, and duplicate papers.

### Literature Synthesis

1. Select a paper set by topic, guide, Zotero collection metadata, or search result.
2. Extract common questions, methods, findings, and limitations.
3. Generate a main guide plus section notes, benchmark design note, or proposal draft.

## Claude Code Safety Rules

- Do not overwrite human-written notes without preserving their content.
- Keep generated sections clearly separated from user-authored sections.
- Prefer deterministic updates for indexes and dashboards.
- If a note contains a user section, preserve it.
- If metadata conflicts, report it instead of silently choosing one source.

## File Ownership Expectations

Generated Obsidian vault files should eventually mark generated regions explicitly. For example:

```markdown
<!-- paperhub:generated:start -->
...
<!-- paperhub:generated:end -->
```

Agents may rewrite generated regions. Agents should treat user sections as durable human input.

## Development Priority

For now, focus on:

1. Stable Markdown indexes and dashboards.
2. Schema and config design.
3. CLI command surface.
4. MCP tool surface.
5. MVP Zotero-account-to-Obsidian pipeline.
6. Processed Markdown import into `Papers/` and `Guides/`.
7. Agent topic-guide generation through Codex / Claude Code.
8. Typed relationship extraction between topics, guides, guide sections, papers, citations, and Zotero records.

Do not prematurely build Claude-specific behavior before the core workflow exists.
