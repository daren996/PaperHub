# Quickstart

[English](quickstart.md) | [中文](zh/quickstart.md)

This is the intended first-run experience.

## Goal

Connect Zotero, connect an Obsidian vault, and generate:

- paper index
- normalized `Papers/` notes for every synced Zotero paper
- topic guides under `Guides/`
- reading dashboard
- agent-accessible project state

## Planned Flow

```bash
cp .env.example .env
# Edit PAPERHUB_VAULT, ZOTERO_API_KEY, and ZOTERO_USER_ID in .env.
paperhub init
paperhub zotero connect
paperhub zotero sync
paperhub import markdown /path/to/research-notes --topic "LLM-as-Judge"
paperhub import markdown /path/to/research-notes --topic "LLM-as-Judge" --apply
paperhub paper enrich smith2024attention --mode quick
paperhub zotero push-staged
paperhub doctor
```

Most commands use `PAPERHUB_VAULT` from `.env`. Pass `--vault /path/to/ObsidianVault` only when you need to override the configured vault for one run.

Markdown import source paths stay on the command line. Do not add them to `.env`.

`paperhub import markdown` is preview-first: without `--apply`, it prints the import plan and writes nothing. Review the planned `Papers/`, `Guides/`, staged papers, ambiguous matches, guide sections, and broken links before applying.

Applied Markdown imports never create links to local files outside the configured vault. Source repository links, absolute paths, local images, and attachments are stripped, rewritten to vault-local `Papers/` or `Guides/` links when possible, or kept as plain text. Web URLs are preserved.

`paperhub paper enrich PAPER --mode quick|deep` builds a local evidence bundle for an indexed paper and refreshes that paper note's scaffold. `quick` can run from metadata; `deep` requires PDF text or Zotero annotations.

`paperhub zotero push-staged` previews imported `IMPORTED-*` papers that are not yet reconciled with Zotero. It is a dry run unless you pass `--write`; after a write, run `paperhub zotero sync` to refresh the official Zotero-backed paper notes.

## Expected Result

Your Obsidian vault should contain:

```text
PaperIndex.md

Papers/
Guides/
```

`Papers/` contains normalized paper notes. Every synced Zotero paper should have a corresponding note that organizes collections, tags, notes, attachment metadata, annotations, relations, sync versions, digest, and synthesis content. `Guides/` contains one folder per topic, each with a main guide Markdown file and section files or subfolders for substantial research structure. Main guides link to top-level sections; leaf or generated overview sections link back to `Papers/`.

## MVP Scope

The first version should work well for API-backed Zotero account sync, staged Zotero export, and processed Markdown guide/digest import. It should prefer clarity, deterministic output, and easy debugging over broad feature coverage.
