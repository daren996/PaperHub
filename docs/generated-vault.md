# Generated Vault Spec

[English](generated-vault.md) | [中文](zh/generated-vault.md)

This document describes the intended Obsidian output.

## Root Files

```text
PaperIndex.md
README.md
```

`PaperIndex.md` is the single generated root entry for PaperHub. It combines the former home summary, reading dashboard, topic guide links, and the human-readable mapping from citation-key paper note filenames to real paper titles. The generated paper table should show the `Papers/<citation-key>.md` file, the full paper title, year, and Zotero key. Citation-key filenames keep graph labels readable; the index restores the title mapping for browsing and lookup.

`README.md` is a lightweight compatibility entrypoint. Processed Markdown imports should update its generated `Topic Guides` section with a link to the current topic's main guide and to `[[PaperIndex]]`, while preserving user notes.

## Directories

```text
Papers/
Guides/
```

These are the only user-visible generated vault surfaces for the current MVP. Do not generate top-level `Collections/`, `Concepts/`, `Claims/`, `Reading Paths/`, or `Templates/` directories for now. Zotero collections remain source metadata and filtering inputs, and should be organized inside the corresponding `Papers/` notes.

## Paper Note Contract

Paper notes live in `Papers/`. Every synced Zotero paper should have a corresponding Markdown file. The file stem should use a citation-key form: first-author last name, year, and the first meaningful title word, such as `smith2024attention`. Long human-readable titles belong in frontmatter, the H1 heading, and wikilink aliases. This keeps Obsidian's graph labels readable while preserving full titles inside the note.

When imported paper material lacks author or year metadata, PaperHub should resolve that metadata
from Zotero, source manifests, DOI/arXiv/OpenReview/ACL metadata, or another reviewable source
before writing the final paper note. Do not generate `unknown` or `nd` filename parts.

All information extracted from Zotero for that paper should be organized in this file, including but not limited to papers, collections, tags, notes, attachment metadata, annotations, relations, and sync versions. Paper-level digest, synthesis content, citation data, BibTeX, and user-authored notes also belong here.

Required sections:

- Metadata
- Zotero Sync
- Citation
- BibTeX
- Zotero Collections
- Zotero Tags
- Zotero Notes
- Attachments
- Relations
- Evidence Bundle
- Digest
- Summary
- Method
- Key Findings
- Limitations
- Relevance
- Zotero Annotations
- Key Figures
- Related Papers
- User Notes

The `Evidence Bundle` section should point to `.paperhub/evidence/<paper-stem>.json`, an internal model-facing artifact. `Key Figures` should use stable placeholder callouts when reliable image extraction is unavailable. The `User Notes` section should be preserved across regeneration.

## Guide Contract

Guide notes live in `Guides/<topic>/`. The topic folder is the topic ownership and slugging boundary; do not create a separate `PaperHub/Topic/` output path.

Each topic folder should contain a main Markdown file, such as:

```text
Guides/llm-as-judge/llm-as-judge.md
```

The main guide owns the logical structure for what the user wants to read or understand about the topic. Section files and subfolders are allowed for detailed sections, appendices, tables, or benchmark notes, but guide content should eventually return to `Papers/` by linking to normalized paper notes.

Guide files should include:

- topic title;
- purpose and scope;
- learning or reading structure;
- paper-backed sections;
- links to `Papers/`;
- open questions;
- generated-region markers where PaperHub may rewrite content.

A substantial topic import should not produce only one Markdown file. When source material contains
separable themes, claims, methods, benchmark families, paper clusters, or reading steps, PaperHub
should write a main guide plus graph-visible section notes under `Guides/<topic>/sections/` or an
equivalent topic subfolder. The main guide should act as the table of contents and synthesis layer;
section notes should carry focused imported or generated material and link back to normalized
`Papers/` notes.

For long single-file research catalogs, section notes should use folder-note style so both the
filesystem and Obsidian graph reveal the hierarchy, such as
`Guides/<topic>/sections/1-functionality/1-functionality.md` and nested child folders below it.
The main guide should link only to top-level section notes. Parent section notes should link to
their immediate child sections rather than directly to papers. When a parent section also contains
its own paper bullets, PaperHub should create a generated `overview/overview.md` child note for
those papers so the visible graph stays `main guide -> sections -> subsections -> papers`.

## Markdown Import Contract

`paperhub import markdown` should transform heterogeneous source content into the same output structure:

```text
source paper digest -> Papers/<citation-key>.md
source guide file   -> Guides/<topic>/<main-or-section>.md
source section       -> Guides/<topic>/sections/<section>/<section>.md
source subfolder    -> Guides/<topic>/sections/<section>/
```

The importer should report files it cannot classify or reconcile. It should never copy a source tree directly into the vault or preserve arbitrary source structure outside the normalized `Guides/<topic>/` contract. Generated import output must not link to files outside the current vault. Local source links, absolute paths, repository images, attachments, and provenance paths should be stripped, rewritten to vault-local `Papers/` or `Guides/` links, or represented as non-link text. Web URLs may remain links.

For a single long Markdown source, the importer should still look inside the file for section
boundaries instead of treating the whole source as one graph node. H2/H3 sections, paper clusters,
explicit citation blocks, benchmark groups, or other stable structural markers can become section
notes when they are meaningful to browse independently.

## Relationship Manifest

The first graph-worthy relationship is deliberately narrow:

```text
guide-section-cites-paper
```

When PaperHub resolves a guide section to one or more normalized paper notes, it should emit a JSON manifest under:

```text
.paperhub/relationships/guide-section-cites-paper.json
```

The manifest should contain only this typed edge for now. It is intended for Neo4j, RDF tooling, a future PaperHub graph command, or an Obsidian Canvas/export step that displays section-to-paper citations without mixing in unrelated vault links.

## Visualization Boundary

The first implementation should not treat Obsidian's global file-link graph as a semantic knowledge graph. PaperHub should first model and validate explicit relationships. Generated guide wikilinks should still avoid hub-and-spoke noise: main guides link to top-level sections, parent sections link to children, and only leaf or generated overview sections link to paper notes. The initial semantic graph should show only `guide-section-cites-paper` edges; broader relationships such as `topic-contains-paper`, `paper-cites-paper`, and `zotero-item-backs-paper` can come later after they are modeled and validated.
