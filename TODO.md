# TODO

[English](TODO.md) | [中文](docs/zh/TODO.md)

This roadmap tracks unfinished work only. Design rules live in:

- [docs/generated-vault.md](docs/generated-vault.md) for the vault contract.
- [docs/markdown-import-and-topic-guides.md](docs/markdown-import-and-topic-guides.md) for processed Markdown import.
- [AGENTS.md](AGENTS.md) for persistent agent guidance.

## Near-Term MVP

- [ ] Add CI workflow for lint and tests.
- [ ] Decide how generated frontmatter maps back to internal schemas.
- [ ] Define a metadata merge strategy for Zotero sync, imported Markdown, agent enrichment, and user-authored sections.
- [ ] Create a pipeline abstraction for `sync -> normalize -> export`.
- [ ] Reconcile staged imported paper filename policy: canonical citation-key filenames vs temporary `IMPORTED-*` keys.
- [ ] Remove or replace the remaining duplicated paper-note rendering used by Markdown import.

## Zotero Sync

- [x] Support Zotero Web API account connection.
- [x] Sync papers, collections, tags, notes, attachment metadata, annotations, relations, and sync versions into paper notes.
- [ ] Download or manage local PDF files beyond Zotero attachment metadata.
- [ ] Add staged JSON export import as a development path.
- [ ] Add collection and tag filtering as source filters.
- [ ] Add helper workflow for staging missing papers discovered by agent research.

## Processed Markdown Import

- [x] Add preview-first `paperhub import markdown SOURCE --topic TOPIC`.
- [x] Discover, classify, reconcile, and write imported content into `Papers/` and `Guides/`.
- [x] Strip or rewrite generated links to local files outside the current vault.
- [x] Emit `guide-section-cites-paper` relationship records.
- [ ] Extract richer metadata from imported paper digests: authors, year, venue, DOI, URL, Zotero key, citation text, BibTeX, summary, method, limitations, and relevance.
- [ ] Validate that every literature-backed guide section links to one or more `Papers/` notes.
- [ ] Improve guide section planning so it reads long source guides and avoids mechanical splitting.

## Obsidian Export

- [x] Generate `Papers/`, `Guides/`, home, dashboard, and paper index.
- [x] Preserve user-authored note sections across regeneration.
- [x] Use short, stable citation-key paper filenames with collision suffixes.
- [x] Keep Zotero collections/tags/notes/attachments/annotations/relations inside paper notes.
- [ ] Use one canonical paper-note section contract across templates, linting, imported notes, and docs.
- [ ] Decide whether dashboard rendering should use Jinja templates or stay code-generated.
- [ ] Add generated-region handling for guide files, not only whole-file rewrites.

## Agent And MCP

- [x] Define the PaperHub skill workflow.
- [x] Implement initial MCP tools: `list_papers`, `run_paperhub_doctor`.
- [ ] Add MCP tool `get_paper`.
- [ ] Add MCP tool `search_papers`.
- [ ] Add MCP tool `import_markdown`.
- [ ] Add MCP tool `create_topic_guide`.
- [ ] Add MCP tool `update_paper_note`.
- [ ] Add MCP tool `generate_synthesis`.
- [ ] Add MCP tool `emit_relationship_manifest`.
- [ ] Add prompt contract requiring citations and paper metadata for newly discovered papers.

## Doctor

- [x] Report vault/index existence.
- [x] Report duplicate titles, URLs, DOIs, and citation keys.
- [x] Report missing abstracts, URLs, DOIs, PDF links, annotations, and local PDF availability.
- [x] Report Zotero Desktop local API and Better BibTeX JSON-RPC availability.
- [ ] Report paper index generation.
- [ ] Report Zotero Web API credential status.
- [ ] Report Markdown import readiness.
- [ ] Report unknown imported files and ambiguous paper matches.
- [ ] Report broken guide-to-paper links.
- [ ] Report MCP configuration status.
- [ ] Report output compatibility.

## Later

```bash
paperhub paper fix --missing-summary
paperhub guide create --topic "LLMs as Judges" --deep-research
paperhub guide refresh --topic "LLMs as Judges"
paperhub survey outline --topic "LLM-as-Judge"
paperhub graph export --topic "LLM-as-Judge" --relationship guide-section-cites-paper
```
