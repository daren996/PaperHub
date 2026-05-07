# PaperHub

[English](README.md) | [中文](docs/zh/README.md)

PaperHub is an agent-native literature knowledge manager for AI-assisted research.

It connects Zotero, a local Obsidian vault, CLI commands, MCP tools, and reusable agent workflows so a research library can become a stable workspace that both humans and coding agents can maintain.

## Status

This repository is in the MVP initialization phase. The current Python-first core can:

- connect a local Obsidian vault path;
- sync a Zotero account;
- sync Zotero papers into normalized `Papers/` notes;
- process external Markdown research guides or digests into `Papers/` and topic `Guides/`;
- expose the library through CLI, MCP, and PaperHub skills.

The canonical generated-vault contract is documented in [docs/generated-vault.md](docs/generated-vault.md). The canonical Markdown import contract is documented in [docs/markdown-import-and-topic-guides.md](docs/markdown-import-and-topic-guides.md).

## Quickstart

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

Most commands use `PAPERHUB_VAULT` from `.env`. Pass a vault path or `--vault` only when setting the vault for the first time, switching vaults, or overriding the configured vault for one run.

Markdown import source paths stay on the command line. Do not add them to `.env`.

## Install

```bash
python -m venv .venv
.venv/bin/pip install -e '.[dev]'
```

Optional extras:

```bash
.venv/bin/pip install -e '.[mcp]'
.venv/bin/pip install -e '.[pdf]'
```

## Command Map

```bash
paperhub init                         # initialize Papers/ and Guides/
paperhub obsidian connect             # record a local vault path
paperhub zotero connect               # save Zotero settings
paperhub zotero sync                  # sync Zotero into Papers/
paperhub import markdown SOURCE       # preview a processed import
paperhub import markdown SOURCE --apply
paperhub paper enrich PAPER --mode quick
paperhub zotero push-staged           # dry-run Zotero creation for staged imports
paperhub doctor
paperhub mcp serve
```

`paperhub import markdown` previews by default and writes only with `--apply`. `paperhub zotero push-staged` is also a dry run unless `--write` is passed.

## Generated Vault Shape

```text
00 Home.md
01 Reading Dashboard.md
02 Paper Index.md
README.md

Papers/
Guides/
```

## Documentation

- [Documentation index](docs/README.md)
- [Quickstart](docs/quickstart.md)
- [Product brief](docs/product-brief.md)
- [Architecture](docs/architecture.md)
- [Generated vault spec](docs/generated-vault.md)
- [Integration requirements](docs/integration-requirements.md)
- [Markdown import and topic guides](docs/markdown-import-and-topic-guides.md)
- [MCP plan](docs/mcp.md)
- [Redundancy audit](docs/redundancy-audit.md)
- [Roadmap](TODO.md)

## Repository Layout

```text
src/paperhub/          Python core, CLI, Zotero sync, Obsidian export, MCP
templates/obsidian/   Markdown templates for generated vault files
skills/               Agent workflows and PaperHub skill instructions
examples/             Sample vaults and import fixtures
docs/                 User and developer documentation
tests/                Unit and integration tests
```

## License

MIT. See [LICENSE](LICENSE).
