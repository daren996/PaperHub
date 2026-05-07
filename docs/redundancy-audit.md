# Redundancy Audit

This audit lists current documentation, code, and test duplication found during the May 2026 project
cleanup. It is intentionally concrete: each item names the files that should be consolidated or kept
as intentional duplication.

## Summary

Highest-value cleanup targets:

- Extract one canonical paper-note section contract.
- Route staged imported paper-note rendering through the same renderer/template as Zotero-backed
  paper notes.
- Reduce repeated first-run command examples to README + quickstart + skill only.
- Decide the unresolved-paper filename policy: citation-key filenames vs temporary `IMPORTED-*`
  filenames.
- Share diagnostics between dashboard rendering and `paperhub doctor`.
- Move repeated test setup into fixtures.

## Documentation Redundancy

### README And Quickstart

- `README.md` and `docs/quickstart.md` both include the same first-run command path.
  This is mostly acceptable, but README should stay minimal and quickstart should own explanations.
- `README.md` has both a quickstart block and a command map. The command map is useful, but it
  partly duplicates `docs/quickstart.md` and CLI help.
- `README.md` and `docs/quickstart.md` both repeat the rule that Markdown source paths belong on
  the command line, not in `.env`.

### Repeated Command Examples

The exact command below appears across README, docs, Chinese docs, agent guidance, and the PaperHub
skill:

```bash
paperhub import markdown /path/to/research-notes --topic "LLM-as-Judge"
paperhub import markdown /path/to/research-notes --topic "LLM-as-Judge" --apply
```

Current duplicate owners:

- `README.md`
- `docs/quickstart.md`
- `docs/integration-requirements.md`
- `docs/markdown-import-and-topic-guides.md`
- `docs/zh/README.md`
- `docs/zh/quickstart.md`
- `docs/zh/integration-requirements.md`
- `docs/zh/markdown-import-and-topic-guides.md`
- `AGENTS.md`
- `skills/paperhub/SKILL.md`

Recommended ownership:

- README: shortest happy path only.
- `docs/quickstart.md`: user-facing command walkthrough.
- `docs/markdown-import-and-topic-guides.md`: import-specific variants and flags.
- `skills/paperhub/SKILL.md`: agent-operational commands.
- Other docs: link to the owning doc instead of restating full command blocks.

### Repeated Product Rules

These rules are repeated in several places and should have one canonical owner:

- `PAPERHUB_VAULT` is persistent configuration, while Markdown source paths are one-off command
  inputs.
- Markdown import is processed import, not raw copy.
- Generated import output must not link to local files outside the current vault.
- MVP generated vault surfaces are only `Papers/` and `Guides/`.
- Do not create top-level `Collections/`, `Concepts/`, `Claims/`, `Reading Paths/`, or `Templates/`
  directories.
- Do not call ordinary Obsidian file links, Canvas, Mermaid diagrams, or paper lists a knowledge
  graph.
- Graph output requires explicit typed relationships, starting with `guide-section-cites-paper`.

Current repeat locations:

- `AGENTS.md`
- `CLAUDE.md`
- `skills/paperhub/SKILL.md`
- `docs/generated-vault.md`
- `docs/markdown-import-and-topic-guides.md`
- `docs/architecture.md`
- `docs/integration-requirements.md`
- `docs/product-brief.md`
- Chinese mirrors under `docs/zh/`

Recommended ownership:

- `AGENTS.md`: persistent agent source of truth.
- `docs/generated-vault.md`: vault surface and paper/guide contracts.
- `docs/markdown-import-and-topic-guides.md`: import pipeline and import flags.
- `docs/architecture.md`: boundaries and data flow only.
- `CLAUDE.md` and `skills/paperhub/SKILL.md`: shorter operational summaries that defer to
  `AGENTS.md` and canonical docs.

### English And Chinese Mirrors

- `docs/zh/*` intentionally mirrors the English docs. This is duplication by design, but it creates
  maintenance cost.
- Some Chinese docs link back to English parent docs for details. That is fine, but future edits
  should either update both languages or mark English as canonical in the Chinese file header.
- `docs/zh/README.md` and `docs/zh/TODO.md` are full mirrors of `README.md` and `TODO.md`. Keep only
  if Chinese user-facing docs are a deliberate project surface.

### TODO Duplication

- `TODO.md` and `docs/zh/TODO.md` are mirrored. This is acceptable only if both are kept in sync.
- `TODO.md` contains several items already explained in `docs/redundancy-audit.md`, especially
  canonical paper-note sections, guide generated-region handling, and staged filename policy.
  TODO should stay a short action list; this audit should own the redundancy rationale.

### Stale Audit Wording

- The previous version of this file said two one-line forwarding helpers were removed from
  `src/paperhub/importers/markdown.py`, but `_paper_filename_for_index()` still exists as a thin
  wrapper around `paper_filename_map()`. The audit should not claim that cleanup is complete until
  the code matches it.

## Code Redundancy

### Paper Note Contract Is Duplicated

The paper-note section list is maintained in multiple places:

- `templates/obsidian/paper-note.md`
- `src/paperhub/importers/markdown.py` in `_render_imported_paper_note()`
- `src/paperhub/enrichment_lint.py` in `REQUIRED_PAPER_NOTE_SECTIONS`
- `docs/generated-vault.md`
- `tests/test_obsidian_export.py`

Problem:

- Adding, removing, or renaming a paper-note section requires synchronized edits across template,
  importer, linter, docs, and tests.
- The imported staged paper renderer omits `Synthesis`, while the main template includes it. That
  makes staged notes drift from the normalized paper-note contract.

Recommended fix:

- Create a single paper-note contract module, for example `src/paperhub/paper_note_contract.py`,
  that exposes section names and generated/user marker constants.
- Make the Jinja template, importer renderer, lint rules, docs tests, and section assertions use
  that contract.

### Staged Imported Paper Rendering Duplicates Obsidian Rendering

`src/paperhub/importers/markdown.py::_render_imported_paper_note()` hard-codes a full Markdown paper
note instead of using `ObsidianExporter.render_paper_note()` or the same Jinja template.

Duplicated content includes:

- frontmatter shape;
- generated-region markers;
- `Metadata`, `Zotero Sync`, `Citation`, `BibTeX`, `Evidence Bundle`, `Digest`, `Summary`, `Method`,
  `Key Findings`, `Limitations`, `Relevance`, `Zotero Annotations`, `Key Figures`, `Related Papers`,
  and `User Notes` sections;
- repeated placeholder strings such as `_Pending review._`.

Recommended fix:

- Convert staged imports into `Paper` models with explicit staged metadata, then render through the
  canonical paper-note renderer.
- Keep imported digest material as a field/section input instead of a separate full note template.

### Generated Markers Are Partly Centralized And Partly Repeated

`src/paperhub/text.py` defines:

```python
GENERATED_START = "<!-- paperhub:generated:start -->"
USER_NOTES_MARKER = "\n## User Notes\n"
```

But raw marker strings still appear in:

- `src/paperhub/obsidian.py`
- `src/paperhub/importers/markdown.py`
- `templates/obsidian/paper-note.md`
- tests and docs

There is no `GENERATED_END` constant even though the end marker is repeated many times.

Recommended fix:

- Add `GENERATED_END`.
- Add a helper for wrapping generated regions.
- Keep template-visible marker names centralized.

### Dashboard Diagnostics Duplicate Doctor Logic

`src/paperhub/obsidian.py::_dashboard()` recalculates:

- missing abstracts;
- missing DOI values;
- missing URL values;
- duplicate DOI groups;
- duplicate URL groups;
- duplicate title groups.

`src/paperhub/doctor.py::run_doctor()` calculates overlapping diagnostics.

Recommended fix:

- Create a shared diagnostics summary object used by both the dashboard and doctor command.
- Let dashboard render counts; let doctor render detailed check statuses.

### CLI Vault Resolution Repeats Across Commands

Most CLI commands follow the same shape:

```python
vault = resolve_vault(vault)
config = load_config(vault=vault)
index = load_index(vault)
```

This repetition is currently readable, but it can grow noisy as commands expand.

Recommended fix:

- Leave it for now unless more commands are added.
- If command count grows, introduce a small command context helper instead of hiding behavior too
  early.

### Thin Wrapper In Markdown Importer

`src/paperhub/importers/markdown.py::_paper_filename_for_index()` is a one-line wrapper:

```python
return paper_filename_map(papers).get(paper.key, paper_filename(paper))
```

Recommended fix:

- Inline it or move filename lookup into a small shared helper if several call sites need it.

### Future-Facing Model Fields Are Not MVP Surfaces

The models include future-facing fields/classes:

- `Paper.concepts`
- `Paper.claims`
- `ReadingPath`
- `PaperHubIndex.reading_paths`

These are not exposed as current generated vault surfaces, and the project explicitly avoids
top-level `Concepts/`, `Claims/`, and `Reading Paths/` folders.

Recommended fix:

- Either document them as internal/future schema fields, or remove them until typed relationships
  need them.

### Staged Filename Policy Conflicts With Docs

Docs say paper-note filenames should use citation-key stems and should not generate `unknown` or
`nd` filename parts. The current implementation stages unresolved imports as:

```text
Papers/IMPORTED-*.md
```

This is also documented as an acceptance criterion in
`docs/markdown-import-and-topic-guides.md`, so the project currently has a product-level compromise:
canonical final filenames vs temporary staged filenames.

Recommended fix:

- Decide and document one lifecycle:
  `IMPORTED-*` as a temporary staging key is allowed, but final Zotero-backed notes must migrate to
  citation-key filenames after reconciliation.

## Test Redundancy

### Repeated CLI Setup

`tests/test_cli.py` and `tests/test_enrichment.py` repeatedly do:

- create `vault = tmp_path / "ResearchVault"`;
- set `PAPERHUB_VAULT`;
- create `CliRunner()`;
- call `paperhub init`;
- build small `PaperHubIndex` fixtures.

Recommended fix:

- Add fixtures for `vault`, `runner`, `initialized_vault`, and common indexed papers.

### Repeated Negative Surface Assertions

Tests repeatedly assert that PaperHub does not generate:

- `Collections`;
- `Maps`;
- `02 Collection Index.md`;
- `02 Digest Index.md`;
- `02 Guide Index.md`;
- `PaperHub`.

Recommended fix:

- Add a test helper such as `assert_mvp_surfaces_only(vault)`.
- Keep one or two explicit assertions near behavior-specific tests, but avoid repeating the whole
  forbidden surface list in every test.

### Repeated Paper Note Section Assertions

`tests/test_obsidian_export.py` hard-codes the required paper-note section list. This duplicates the
template, linter, docs, and imported-note renderer.

Recommended fix:

- Import the canonical section contract in tests once that contract exists.

## Intentional Duplication To Keep

- English and Chinese docs may remain duplicated if bilingual documentation is a product goal.
- `AGENTS.md`, `CLAUDE.md`, and `skills/paperhub/SKILL.md` need some overlap because different
  agents load different files. Keep them concise and make `AGENTS.md` the source of truth.
- README and quickstart should both mention the happy path, but README should stay compressed.
- CLI help repeating `PAPERHUB_VAULT` is acceptable while users are learning the vault model.

## Suggested Cleanup Order

1. Introduce a paper-note contract module and update template, linter, tests, docs references, and
   staged import rendering.
2. Add `GENERATED_END` and generated-region helpers.
3. Consolidate dashboard and doctor diagnostics.
4. Add test fixtures/helpers for CLI setup and MVP surface assertions.
5. Thin `CLAUDE.md` and `skills/paperhub/SKILL.md` so they defer more explicitly to `AGENTS.md`.
6. Reduce repeated import command examples outside README, quickstart, import docs, and skill docs.
7. Resolve and document the staged `IMPORTED-*` filename lifecycle.
