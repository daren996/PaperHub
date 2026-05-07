# Integration Requirements

[English](integration-requirements.md) | [中文](zh/integration-requirements.md)

PaperHub currently supports three real-world entry points:

```text
Zotero account
External Markdown research source
Obsidian vault
```

Markdown import is supported only as a processed import through `paperhub import markdown`. Do not add raw copy behavior or a persistent Markdown source path to configuration.

## Zotero Account

PaperHub should connect to a user's Zotero account and manage all paper-level information available from Zotero, including but not limited to papers, collections, tags, notes, attachment metadata, annotations, relations, and sync versions.

Required support:

- Full-library sync.
- Collection filtering as source filtering, not generated `Collections/` output.
- Tag filtering.
- Incremental updates.
- Paper note generation for every synced Zotero paper under `Papers/`.
- Organized paper-note sections for collections, tags, notes, attachment metadata, annotations, relations, and sync versions.
- Missing PDF / missing abstract / duplicate paper checks.
- Stable preservation of Zotero item keys.

## Markdown Import

PaperHub should accept one-off Markdown source paths:

```text
paperhub import markdown /path/to/research-notes --topic "LLM-as-Judge"
paperhub import markdown /path/to/research-notes --topic "LLM-as-Judge" --apply
```

The command previews by default. It writes only when `--apply` is present.

Required support:

- Source paths are task-specific inputs, not persistent config.
- The importer must classify, normalize, reconcile, and report ambiguity before writing.
- Applied output must stay inside `Papers/`, `Guides/`, generated root files, and internal `.paperhub/` state.
- Staged Zotero writes require the explicit `paperhub zotero push-staged --write` step.

The detailed import pipeline and acceptance criteria live in [markdown-import-and-topic-guides.md](markdown-import-and-topic-guides.md).

## Obsidian

PaperHub should write to a local Obsidian vault path:

```text
paperhub init
paperhub obsidian connect
```

Both commands default to `PAPERHUB_VAULT` from `.env`. Pass a path only when creating or switching to a different local vault.

If the user uses Obsidian Sync, PaperHub writes to the local synced vault and Obsidian handles account synchronization.

PaperHub should generate these inside the vault:

```text
Papers/
Guides/
```

It should also generate dashboards and indexes. The detailed vault contract lives in [generated-vault.md](generated-vault.md).

## Agent Customization

Codex / Claude Code should be able to help with Zotero-backed paper notes, processed Markdown import, topic guide generation, and paper-note enrichment:

```text
Import and normalize an existing Markdown research repository.
Generate a topic guide from a user-provided topic.
Search broadly for missing literature.
Stage missing papers locally, then create Zotero items only through explicit user-approved writes.
Update generated paper-note sections.
Build `.paperhub/evidence/<paper-stem>.json` evidence bundles before single-paper writing.
Generate a main guide plus graph-visible section notes from a guide or paper set.
Emit relationship data for later graph work.
```

Human-written content is preserved by default. Agent-written content goes into generated regions, and updates should rewrite only generated regions unless the user explicitly asks otherwise. Single-paper deep enrichment should fail when no PDF text or Zotero annotations are available.
