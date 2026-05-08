# Markdown Import And Topic Guide Implementation Plan

[English](markdown-import-and-topic-guides.md) | [中文](zh/markdown-import-and-topic-guides.md)

This plan describes the revised MVP direction: PaperHub should support `paperhub import markdown`, but only as a processed import that normalizes external research material into the same Obsidian structure used by agent-generated topic guides.

The MVP should keep two related but distinct modes:

- deterministic import: parse and sanitize source Markdown, reconcile papers, and write vault-local `Papers/` and `Guides/` output without requiring an LLM call;
- prompt-driven synthesis: use the imported source material plus a user task prompt to generate a new task-aware reading guide through Codex, Claude Code, an MCP client, or a future local service.

For example, importing an awesome-list README can preserve a source-derived PaperHub guide as a baseline, while an agent workflow can also produce a separate guide for a prompt such as: "I am an agent engineer working with hundreds of millions of users and need an efficient benchmark for training and tuning agents. Where should I start reading?"

## Output Contract

The vault output should be:

```text
Papers/
Guides/
```

`Papers/` contains paper Markdown files. Every synced Zotero paper should have a corresponding file. A paper file should collect the paper's basic metadata, Zotero collections, tags, notes, attachment metadata, annotations, relations, sync versions, citation information, BibTeX, digest material, and synthesis sections.

`Guides/` contains one folder per topic. Each topic folder has a main Markdown guide that manages what the user wants to read or understand. Section files and subfolders are allowed, but the guide must eventually link back to paper notes in `Papers/`.

For now, do not generate top-level `Claims/`, `Collections/`, `Reading Paths/`, `Templates/`, or `Concepts/` folders.

Substantial imports should create more than a single topic Markdown file. A long survey, reading
list, benchmark review, or multi-paper research note should become a main guide plus graph-visible
section notes. The main guide is the synthesis and navigation surface; section notes are the durable
topic-level nodes that can cite one or more normalized `Papers/` notes.
In the generated wikilink graph, the main guide should link only to top-level sections. Parent
sections should link to immediate child sections, and paper links should live on leaf sections or on
generated `overview/overview.md` children when a parent section has its own paper bullets.

The importer or agent workflow must not mechanically split by every source file, paper digest, or
heading. It should first read the imported guide material, infer the author's intended structure, and
choose the smallest useful set of sections. A guide with five meaningful top-level reading sections
should normally produce five section notes, not one note per paper.

Every paper named in a guide section should resolve to a `Papers/` Markdown note. Existing
Zotero-backed papers should link to `Papers/<citation-key>.md`. Papers that appear in the imported
source but are not yet in Zotero should be staged as citation-key `Papers/` notes with enough metadata and
digest material for later Zotero reconciliation.

## Command Design

```bash
paperhub import markdown /path/to/research-notes --topic "LLM-as-Judge"
paperhub import markdown /path/to/research-notes --topic "LLM-as-Judge" --goal "I am an agent engineer building large-scale benchmarks; where should I start reading?"
paperhub import markdown /path/to/research-notes --topic "LLM-as-Judge" --dry-run
paperhub import markdown /path/to/research-notes --topic "LLM-as-Judge" --apply
paperhub import markdown /path/to/research-notes --topic "LLM-as-Judge" --on-missing-paper stage
paperhub zotero push-staged
paperhub zotero push-staged --write
```

Initial flags:

- `SOURCE`: required one-off source path.
- `--topic`: required at first; topic inference can come later.
- `--goal`: optional user task prompt. PaperHub stores it in the import plan and guide as an agent-ready synthesis brief; deterministic import still runs without a model call.
- default behavior: produce an import plan and report without writing.
- `--dry-run`: legacy alias for the default preview behavior.
- `--apply`: write the reviewed import plan to the vault.
- `--on-missing-paper`: `report` or `stage`; default is `stage` so imported paper digests become local `IMPORTED-*` paper notes.
- `--vault`: optional one-run override for `PAPERHUB_VAULT`.

`paperhub zotero push-staged` lists staged imported papers without writing by default. `--write`
creates them in Zotero through the Web API and should be followed by `paperhub zotero sync`.

Do not add `PAPERHUB_MARKDOWN_SOURCE` or equivalent persistent config.

## Import Pipeline

1. Discover Markdown files under `SOURCE`.
2. Classify each file:
   - paper digest;
   - topic guide;
   - guide section;
   - guide support note;
   - unknown.
3. Infer a topic section plan from the imported guide material:
   - read the main guide rather than only scanning filenames;
   - identify the author's intended top-level structure;
   - choose a small number of durable sections;
   - avoid splitting every paper digest into its own guide section.
4. Split substantial guide sources into topic sections:
   - H2/H3 headings;
   - explicit paper clusters;
   - benchmark or method families;
   - claim/theme groups;
   - reading-path steps.
5. Extract structured data:
   - title, authors, year, venue;
   - DOI, URL, arXiv ID, Zotero key;
   - citation text;
   - BibTeX;
   - digest, summary, method, limitations, relevance;
   - outgoing paper references.
6. Reconcile papers:
   - exact Zotero key;
   - DOI;
   - URL/arXiv;
   - normalized title plus author/year;
   - manual review when ambiguous.
7. Build an import plan that accepts heterogeneous source formats:
   - paper note writes;
   - guide writes;
   - staged citation-key `Papers/` writes for unresolved imported papers;
   - staged Zotero additions;
   - `guide-section-cites-paper` relationship records;
   - warnings, boundary cases, and review items.
8. Write deterministic output:
   - paper-like content to `Papers/<citation-key>.md`;
   - guide-like content translated into the standard `Guides/<topic>/` format;
   - a main guide file for the topic;
   - section paper lists with wikilinks to `Papers/`;
   - no generated links to local files outside the current vault;
   - subfolders only under the topic folder.
9. Optionally push staged imported papers to Zotero:
   - preview with `paperhub zotero push-staged`;
   - create Zotero items only with `paperhub zotero push-staged --write`;
   - run `paperhub zotero sync` afterward to refresh canonical Zotero-backed notes.
10. Validate output:
   - no raw source tree copy;
   - no source repository links, absolute local paths, local images, attachments, or provenance paths that point outside the vault;
   - no orphan guide paper references;
   - generated regions preserve user content;
   - report unresolved files and links.

## Agent Topic Guide Workflow

Codex / Claude Code can create knowledge for a user topic through a workflow like:

```text
source Markdown + user task prompt
  -> PaperHub parses source papers, sections, links, and metadata
  -> agent reads the structured source context and the user's goal
  -> optional deep research across the web and current Zotero library
  -> candidate bibliography
  -> add missing papers to Zotero or staged import
  -> complete normalized Papers/ notes
  -> Guides/<topic>/ main guide and section files
  -> relationship manifest for later graph work
```

The generated guide should be more like a structured reading guide or survey than a loose note dump. It should be newly organized around the user's task, role, constraints, and desired output artifacts rather than mechanically preserving the source Markdown order. Every literature-backed section should link to one or more normalized paper notes.

PaperHub core should not own the open-ended reasoning step directly. Its job is to provide reliable ingredients and guardrails: source extraction, paper reconciliation, import plans, prompt/context packages, deterministic vault writes, and validation. Codex / Claude Code or another agent can own the synthesis prose and reading-order decisions.

## Knowledge Graph Path

PaperHub can later support graph output, but the graph should be built from explicit relationships rather than file links alone.

Start with one useful relation:

```text
guide-section-cites-paper
```

The first implementation should emit relationship data as a JSON manifest at `.paperhub/relationships/guide-section-cites-paper.json`. That manifest should contain only resolved guide-section-to-paper citations. Rendering an Obsidian Canvas, Mermaid diagram, Neo4j import, or RDF export can come after this narrow relationship is validated.

Broader relationships such as `topic-contains-paper`, `paper-cites-paper`, and `zotero-item-backs-paper` should remain future work until PaperHub can model and validate them explicitly.

## Filename Policy

Generated paper filenames should be short and stable:

```text
Papers/<citation-key>.md
```

Do not include full paper titles in filenames. Long titles should appear in frontmatter, H1 headings, paper indexes, and wikilink aliases. This keeps Obsidian Graph View and external graph exports legible.

## Acceptance Criteria

- Running `paperhub import markdown SOURCE --topic TOPIC` prints a clear import plan and writes nothing.
- Running with `--apply` writes only under `Papers/`, `Guides/`, and root dashboard/index files.
- Deterministic import remains usable without any model call.
- A prompt-driven agent workflow can take imported source context plus a user prompt and produce a new task-aware guide, while still writing through PaperHub's `Papers/` and `Guides/` contracts.
- Imported paper digests that are not in Zotero are written to `Papers/IMPORTED-*.md` and listed by `paperhub zotero push-staged`.
- Zotero writes require the explicit `paperhub zotero push-staged --write` command.
- The importer does not copy the source directory directly.
- Generated output does not reference files outside the current vault. Web URLs may remain; local source files, images, attachments, absolute paths, and provenance paths must not become vault links.
- Paper notes include Zotero-derived collections, tags, notes, attachment metadata, annotations, relations, sync versions, plus citation, BibTeX, digest, and user-preserved sections.
- The topic guide has a main Markdown file that links to top-level sections, not directly to every paper.
- Resolved leaf or overview guide sections emit `guide-section-cites-paper` relationship records.
- Paper note filenames use citation-key stems rather than Zotero keys or title-length slugs.
- Missing or ambiguous papers are reported.
- Existing user-authored sections are preserved.
- Doctor reports broken guide links and ambiguous imports.
