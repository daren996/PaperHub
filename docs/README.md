# PaperHub Documentation

This directory keeps project documentation split by ownership so the same rule is not maintained in many places.

## Canonical Docs

- [Generated vault spec](generated-vault.md): the canonical `Papers/` and `Guides/` output contract.
- [Markdown import and topic guides](markdown-import-and-topic-guides.md): the canonical processed Markdown import contract.
- [Architecture](architecture.md): system layers, data flow, and integration boundaries.
- [Integration requirements](integration-requirements.md): external system requirements for Zotero, Markdown sources, Obsidian, and agents.
- [MCP plan](mcp.md): MCP surface and planned tools.
- [Redundancy audit](redundancy-audit.md): cleanup decisions and remaining duplication candidates.

## User Docs

- [Quickstart](quickstart.md): first-run workflow.
- [Product brief](product-brief.md): product intent and MVP shape.

## Maintenance Rule

When a rule belongs to one canonical doc, other docs should link to it instead of restating it. `README.md` should stay a short entrypoint, and `TODO.md` should track unfinished work rather than preserving completed design history.
