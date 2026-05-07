# Architecture

[English](architecture.md) | [中文](zh/architecture.md)

PaperHub should be built as a Python-first reusable local research core with multiple interfaces.

## Layers

```text
src/paperhub/models.py and related core modules
  schemas that support Papers/, Guides/, imports, and future relationships

src/paperhub/zotero.py
  Zotero account, metadata, collections, tags, notes, attachment metadata, annotations, relations, sync versions

src/paperhub/importers/markdown.py
  processed Markdown guide/digest import

src/paperhub/evidence.py and src/paperhub/enrichment_lint.py
  single-paper evidence bundle construction and generated-note quality checks

src/paperhub/obsidian.py
  Papers/, Guides/, dashboards, indexes

src/paperhub/cli.py
  simple commands for researchers

src/paperhub/mcp_server.py
  tools for Codex, Claude Code, Cursor, and other agents

paperhub-agent-plugins
  Codex and Claude Code workflow wrappers
```

## Key Rule

The plugin layer should call core capabilities. It should not own the paper model, sync pipeline, Markdown importer, or Obsidian generation logic.

## Data Flow

```text
Zotero account
  -> normalized Paper / Annotation records
  -> local PaperHub index
  -> complete Papers/<citation-key>.md notes

External Markdown source tree
  -> classification: paper digest / guide / guide section / support note / unknown
  -> guide splitting: themes / methods / benchmarks / paper clusters / reading steps
  -> extraction: metadata / citation / BibTeX / digest / guide outline
  -> reconciliation with Zotero and PaperHub index

PaperHub index + imported content
  -> Papers/
  -> Guides/<topic>/<topic>.md
  -> Guides/<topic>/sections/*.md
  -> .paperhub/relationships/guide-section-cites-paper.json
  -> MCP tools
  -> CLI / skills / agent workflows

Single paper enrichment
  -> indexed Zotero/PaperHub paper identity
  -> metadata / BibTeX / attachments / annotations / optional PDF text
  -> .paperhub/evidence/<paper-stem>.json
  -> refreshed Papers/<paper-stem>.md scaffold
  -> lint before saving deep-reading scaffolds
```

## Markdown Import Boundary

`paperhub import markdown` is a processed import, not a file copy. The architecture boundary is that import logic must classify, normalize, reconcile, and write through PaperHub models instead of leaking source directory layout into the vault. The detailed import contract lives in [markdown-import-and-topic-guides.md](markdown-import-and-topic-guides.md).

## Agent Topic Guide Boundary

Codex / Claude Code workflows may create topic guides. The core logic still belongs in `src/paperhub`:

```text
user topic
  -> deep research / web search by agent
  -> candidate bibliography
  -> Zotero add or staged Zotero import for missing papers
  -> normalized Papers/ notes
  -> Guides/<topic>/<topic>.md main guide
  -> Guides/<topic>/sections/*.md research nodes
  -> guide-section-cites-paper relationship manifest
```

The main guide is the synthesis and navigation layer. Section notes are the graph-visible topic nodes that carry focused literature-backed content. The agent can perform research and drafting, but PaperHub core should own validation, deduplication, vault layout, and deterministic updates.

## Relationship Boundary

The initial semantic graph should display only one relationship type:

```text
guide-section-cites-paper
```

This relation connects a generated or imported guide section to a normalized paper note. The manifest contract lives in [generated-vault.md](generated-vault.md#relationship-manifest). Broader relationship types should be added only after their extraction and validation rules are explicit.

## Filename Boundary

Paper note filenames should use citation-key stems such as `Papers/smith2024attention.md`, built from first-author last name, year, and the first meaningful title word. Full titles stay in the note body, frontmatter, and link aliases. This keeps Obsidian graph labels and exported semantic graphs readable while preserving human-friendly titles where users read them.

## Integration Boundaries

Zotero integration should support account-level sync through the Zotero API, with local export import as a fallback for early development and debugging.

Obsidian integration should begin with a local vault path. If the user uses Obsidian Sync, PaperHub writes to the local synced vault and lets Obsidian handle account synchronization.

This is the current primary path:

```text
PaperHub
  -> local Obsidian vault folder
  -> Obsidian app
  -> Obsidian Sync, if enabled
```

PaperHub should not depend on an Obsidian cloud API for the MVP.

Later, PaperHub can add a first-party Obsidian plugin. That plugin should run inside the selected vault, use Obsidian's Vault API for native file operations, and call the PaperHub Python CLI, local service, or MCP tools for core logic.

## Generated File Safety

Generated Markdown should use stable regions where possible:

```markdown
<!-- paperhub:generated:start -->
...
<!-- paperhub:generated:end -->
```

Human-authored content should be preserved.
