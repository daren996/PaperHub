# PaperHub Product Brief

[English](product-brief.md) | [中文](zh/product-brief.md)

PaperHub is not essentially an Obsidian plugin, a Zotero plugin, or a single skill. It is an agent-native literature knowledge manager built around Zotero, a local Obsidian vault, CLI commands, MCP tools, and reusable agent workflows.

## One-Line Project

Build an agent system for researchers' paper knowledge management: it connects a Zotero account, syncs papers, collections, tags, notes, attachment metadata, annotations, relations, and sync versions, processes external Markdown research guides/digests into a stable vault structure, writes structured Markdown into a local Obsidian vault, and gives Codex / Claude Code / MCP stable ways to organize, extend, and synthesize literature.

Processed Markdown guide/digest import is supported through `paperhub import markdown`. It is not a copy command: it must classify files, extract paper metadata and guide structure, reconcile papers with Zotero when possible, and write the result into `Papers/` and `Guides/`. Generated import output must not reference local files outside the current vault; web URLs are fine, but source repository files, absolute paths, local images, and attachments should be stripped, rewritten to vault-local links, or represented as plain text.

## Core Vault Surfaces

```text
Papers/        Normalized paper notes, including digest, annotations, synthesis, and Zotero metadata
Guides/        Topic folders with a main Markdown guide and paper-backed sections
```

The detailed output contract lives in [generated-vault.md](generated-vault.md).

## Core Workflow

```text
Zotero account
  ↓
Import papers / collections / tags / notes / attachment metadata / annotations / relations / sync versions
  ↓
Normalize the PaperHub paper index
  ↓
Process Markdown guide/digest sources
  ↓
Write complete paper notes into Papers/
  ↓
Write a main guide plus section notes into Guides/<topic>/
  ↓
Link guide sections back to papers
  ↓
Emit guide-section-cites-paper relationship data
  ↓
Codex / Claude Code continuously maintain it
```

## Target Experience In Obsidian

After opening Obsidian, the user should see a research cockpit rather than a pile of files:

```text
00 Home.md
01 Reading Dashboard.md
02 Paper Index.md

Papers/
Guides/
```

`Papers/` stores normalized paper notes. `Guides/` stores one folder per topic, with a main guide plus meaningful section notes when the topic is substantial. The guide is the user-facing reading or survey artifact, and its literature-backed sections should link back to `Papers/`.

## MVP

```text
1. Connect a Zotero account, or import from staged export first.
2. Connect an Obsidian vault.
3. Sync all papers in Zotero, with collection filtering as an optional feature.
4. Write every synced Zotero paper into a corresponding normalized Markdown file under Papers/.
5. Organize all Zotero-derived paper information in that file, including collections, tags, notes, attachment metadata, annotations, relations, and sync versions.
6. Support processed Markdown import into Papers/ and Guides/.
7. Support agent topic-guide generation: the user provides a topic, the agent searches broadly, adds missing papers to Zotero or a staged queue, creates normalized Papers/ notes, writes a main guide plus section notes in Guides/<topic>/, and emits section-to-paper relationship data.
8. Provide MCP / CLI / skills so Codex and Claude Code can continue operating.
```

Graph-like visualization is not part of the first implementation. Future graph output must be backed by explicit typed relationships; the current relationship boundary is described in [generated-vault.md](generated-vault.md#relationship-manifest).

## Usability Principle

README and CLI should stay focused on the shortest useful path. Command details live in [quickstart.md](quickstart.md), and unfinished diagnostics work lives in [../TODO.md](../TODO.md).
