# AGENTS.md

This file gives coding agents the project context needed to work on PaperHub.

## Project Identity

PaperHub is an agent-native literature knowledge manager.

It is not primarily an Obsidian plugin, a Zotero plugin, or a single prompt pack. It is a local-first research knowledge system with multiple entry points:

```text
CLI + Core Library + MCP Server + Agent Skills + Obsidian Templates
```

The design goal is extreme ease of use for researchers:

```text
Connect Zotero account.
Connect Obsidian vault.
Generate and maintain an Obsidian research workspace.
Let Codex / Claude Code keep it organized.
```

## Product Principle

Prefer user-visible simplicity over internal cleverness. A user should not need to understand the full architecture before seeing value.

Avoid command sprawl. Do not expose every internal pipeline stage as a separate top-level user command unless the user clearly benefits from controlling that stage directly. Prefer a few plain commands with good defaults, diagnostics, and explicit flags for advanced behavior.

Be especially careful about the boundary between persistent configuration and task-specific input. Do not promote a one-off source path, user request, generated file path, or test fixture into a global environment variable or default config unless the user explicitly asks for that.

The first-run experience should eventually feel like:

```bash
cp .env.example .env
paperhub init
paperhub zotero connect
paperhub zotero sync
paperhub import markdown /path/to/research-notes --topic "LLM-as-Judge" --goal "I need an agent benchmark reading path."
paperhub doctor
```

Do not call a simple Obsidian Canvas, Mermaid diagram, or list of paper files a knowledge graph.
A graph-like visualization is only acceptable when it is backed by explicit typed relationships
between domain objects, such as guide-section-cites-paper, paper-cites-paper, or topic-contains-paper.
Until those relationships are modeled and validated, PaperHub should generate notes, dashboards,
indexes, and guide-to-paper backlinks rather than pseudo-knowledge-graph artifacts.

Ordinary Zotero sync should create or update the corresponding normalized paper Markdown files in
`Papers/`. Everything extracted from Zotero at the paper level, including papers, collections, tags,
notes, attachment metadata, annotations, relations, and sync versions, should be organized inside the
matching paper note. Markdown import and agent-generated topic guides may enrich the same paper notes
with digest, citation, BibTeX, and synthesis content.

## Architectural Rule

Do not put core research logic inside a Codex plugin, Claude Code plugin, or Obsidian-only integration.

Core logic belongs in `src/paperhub` and should be reusable from:

- CLI
- MCP server
- Codex plugin
- Claude Code plugin
- local service
- future UI

## Hard-Won Design Constraints

The following points came from early design corrections and should be treated as project rules:

- Do not hard-code personal absolute paths such as `/Users/<name>/...` in reusable defaults, examples, or generated config. Prefer `~`, `/path/to/...`, or explicit user-provided arguments.
- `PAPERHUB_VAULT` is persistent configuration because it names the local Obsidian vault that PaperHub writes to.
- PaperHub supports processed Markdown import through `paperhub import markdown`. This must never be a raw copy. It must parse, normalize, deduplicate, and write into PaperHub's vault structure.
- Markdown import may accept a task-specific `--goal` prompt describing the user's role, constraints, and research question. This prompt is one-off task input, not persistent config. PaperHub core should store it in the import plan/guide and expose it to Codex, Claude Code, MCP clients, or future synthesis services; open-ended task-aware synthesis should not be buried as opaque core logic.
- Keep deterministic Markdown import as a baseline capability even when agent-generated synthesis is added. A user should be able to import source Markdown into a sanitized, vault-local PaperHub guide without requiring Codex, Claude Code, or another model call.
- Prompt-driven research synthesis is a separate agent-assisted workflow layered on top of import. The user may provide a task prompt such as their role, goal, data scale, benchmark need, or reading question; Codex / Claude Code should use PaperHub's parsed source material, paper index, and vault-writing contracts to generate a new task-aware guide rather than merely copying the imported Markdown.
- Do not make PaperHub core depend on one proprietary model or editor. Core should expose structured source extraction, paper reconciliation, guide write plans, prompt/context packages, and validation; Codex, Claude Code, MCP clients, or future local services can perform the open-ended synthesis step.
- Do not add Markdown source paths to `.env`; Markdown import sources are task-specific inputs passed to the command or agent workflow.
- Generated output from Markdown import must not reference files outside the current Obsidian vault. Local source links, absolute paths, images, attachments, and provenance paths that point outside the vault should be stripped, rewritten to vault-local `Papers/` or `Guides/` links, or represented as non-link text. Web URLs are acceptable, but local file references are not.
- Imported paper content belongs in `Papers/`. Imported or generated teaching/survey/guide content belongs in `Guides/<topic>/`, with backlinks to the normalized paper notes in `Papers/`.
- A topic import must not collapse a substantial research corpus into a single guide Markdown file. A useful import should create a main guide plus paper-backed section notes when the source contains separable claims, themes, paper clusters, benchmark families, methods, or reading steps. The Obsidian graph should show navigable research structure, not one isolated topic node.
- Do not mechanically split imported guides by every source file, paper digest, or heading. The agent workflow must first read the imported guide material, infer the author's intended structure, and choose a small set of meaningful top-level sections. For example, a reading guide with five `###` sections should usually become one main guide plus five section notes, not dozens of per-paper notes.
- Every paper mentioned in a guide section should link to a corresponding `Papers/` Markdown note. If the paper is already in the Zotero-backed index, link to that normalized paper note. If it is not yet in Zotero but the import source contains enough paper material, stage a citation-key paper note under `Papers/` and mark it for Zotero reconciliation.
- Paper note filenames must use citation-key stems: first-author last name, year, and first meaningful title word, with a short suffix only for collisions. Resolve author/year metadata before writing the note. Do not generate `unknown` or `nd` filename parts.
- Zotero-derived paper information belongs in the corresponding `Papers/` Markdown file. Do not hide collections, tags, notes, attachment metadata, annotations, relations, or sync versions only in an internal index.
- Keep the source/target distinction clear: Zotero is the read input; the Obsidian vault is the write target.
- Do not assume Obsidian has a cloud API key that lets PaperHub operate on a named vault. The MVP writes to a local vault folder; Obsidian Sync, if enabled, syncs those files.
- A first-party Obsidian plugin is a future upgrade path, not the MVP integration path.
- Do not silently transform a real research repository path into a global default just because it is useful for testing.
- When a user challenges a design choice, update persistent project guidance if the correction reveals a reusable rule.

## Configuration

Use `.env` for durable connection settings:

```text
ZOTERO_API_KEY
ZOTERO_USER_ID
ZOTERO_LIBRARY_TYPE
PAPERHUB_VAULT
```

Do not add Markdown source paths to `.env`; they are one-off command inputs.

## Obsidian Integration Rule

The MVP integration mode is local vault path:

```text
PaperHub writes Markdown files into PAPERHUB_VAULT.
Obsidian opens that folder as a vault.
Obsidian Sync handles account/device sync if the user enables it.
```

Do not describe this as logging into an Obsidian account.
Do not require users to create a new vault if they already have a suitable vault.
Do not depend on an Obsidian cloud API for the MVP.

Future paths may include:

- optional Obsidian Local REST API integration
- first-party PaperHub Obsidian plugin

Both should still call PaperHub core logic rather than duplicating it.

## MVP Vault Surfaces

For the current MVP, keep the user-visible generated vault surface focused on:

- `PaperIndex.md`
- `Papers/`
- `Guides/`

`PaperIndex.md` is the single generated root entry that combines the home summary, reading dashboard,
topic guide links, and paper filename-to-title index. Do not generate separate `00 Home.md`,
`01 Reading Dashboard.md`, or `02 Paper Index.md` root entry files.

`Papers/` owns normalized paper notes. Paper-level digest, annotations, synthesis sections, citation
data, BibTeX, Zotero collections, tags, notes, attachment metadata, relations, sync versions, and
user-authored paper notes should live inside the corresponding paper note.

`Guides/` owns user-facing topic folders. Each `Guides/<topic>/` folder should contain a main
Markdown guide for the topic, section files or subfolders for substantial imported or generated
research structure, and backlinks to the relevant `Papers/` notes. Tiny topics may have only a main
guide, but imports like a survey, reading list, benchmark review, or multi-paper research note
should be decomposed into graph-visible section notes. Topic ownership and slugging should be
represented by the guide folder itself; do not create a separate `PaperHub/Topic/` output path.

PaperHub may still use internal schemas for papers, topics, guide sections, annotations, synthesis
content, import plans, import reports, and future typed relationships. Those schemas should support
the two-surface vault contract rather than becoming additional top-level generated folders.

Zotero collections may remain source metadata and filtering inputs, but generated vault output should
not expose top-level `Collections/`, `Concepts/`, `Claims/`, `Reading Paths/`, or `Templates/` folders
for now.

Avoid reducing everything to generic notes or files. The point of PaperHub is that the agent can reason about research objects, not only folders.

## Expected Repository Shape

```text
src/paperhub/
  models.py
  cli.py
  zotero.py
  obsidian.py
  mcp_server.py
  doctor.py
templates/obsidian/
skills/
examples/
docs/
tests/
```

## Implementation Priorities

1. Make the CLI MVP work before building plugin-specific polish.
2. Make Obsidian output stable and readable before adding complex automation.
3. Add processed Markdown import after the `Papers/` and `Guides/` contracts are coherent.
4. Add MCP tools after schemas and vault output are coherent.
5. Add Codex / Claude Code plugin wrappers after the CLI and MCP surfaces are useful.

## UX Requirements

The project should always include diagnostics and recovery paths:

```text
paperhub doctor
```

The doctor command should eventually report:

```text
Zotero connection status
Obsidian vault path
PDF availability
annotation import status
missing abstracts
duplicate papers
MCP configuration status
Markdown import ambiguity
broken guide-to-paper links
output compatibility
```

## Generated Obsidian Content

Generated Markdown should be useful to both humans and agents. It should have predictable frontmatter, stable section names, and clean links.

Every synced Zotero paper should have a corresponding paper note. Paper notes should include at minimum:

- title
- authors
- year
- venue
- DOI / URL / Zotero key
- Zotero collections
- Zotero tags
- Zotero notes
- attachment metadata
- Zotero annotations
- Zotero relations
- Zotero sync versions
- topics
- citation information
- BibTeX
- digest
- summary
- method
- limitations
- relevance
- annotations
- related papers

Guide notes should live under `Guides/<topic>/`. Each topic folder should have a main Markdown file
that owns the guide structure, can use subfolders for detailed sections, and must eventually link
back to the normalized paper notes in `Papers/`.

## Development Style

- Prefer small, composable modules.
- Prefer structured metadata over ad hoc string parsing.
- Keep generated files deterministic where practical.
- Add tests around schema conversion, Zotero sync behavior, and Markdown generation.
- Keep templates understandable to a researcher who opens them directly.
- Before implementing a user-facing change, identify which README, docs, examples, skills, templates, or help text will need to change, and keep them in sync before finishing the task.
- When changing user-visible behavior, CLI commands, configuration, generated vault output, schemas, or integration workflows, update the relevant documentation in the same change.
- After changing CLI semantics, update `--help`, README, skills, and project docs together.
- If examples need a concrete path, use placeholder paths or `~` unless the path is intentionally documenting a user-provided source.

## Non-Goals For The First MVP

- Do not build a full Obsidian plugin first.
- Do not require cloud sync.
- Do not require users to abandon Zotero.
- Do not require users to abandon Obsidian.
- Do not make the agent workflow depend on one proprietary model or editor.

## Current Phase

The repository is in initialization phase. Work should focus on:

- documentation
- file structure
- schemas
- template contracts
- Zotero account sync design
- Obsidian vault connection design
- import/export pipeline design
- CLI command design
- MCP tool design
- MVP task breakdown
