# MCP Plan

[English](mcp.md) | [中文](zh/mcp.md)

MCP should become the stable agent interface for PaperHub.

## Why MCP First

Codex plugins, Claude Code plugins, and editor-specific integrations may change. MCP gives PaperHub one reusable agent surface that can be called from several environments.

## Candidate Tools

```text
list_papers
run_paperhub_doctor
search_papers
get_paper
import_markdown
create_topic_guide
update_paper_note
generate_synthesis
emit_relationship_manifest
```

## First Implemented Tools

The initial MCP wrapper exposes:

```text
list_papers
run_paperhub_doctor
```

Run it with:

```bash
paperhub mcp serve --vault /path/to/ObsidianVault
```

Example MCP client configuration:

```json
{
  "mcpServers": {
    "paperhub": {
      "command": "paperhub",
      "args": ["mcp", "serve", "--vault", "/path/to/ObsidianVault"]
    }
  }
}
```

## Expected Agent Tasks

- Import a Zotero collection.
- Import and normalize a Markdown research source into `Papers/` and `Guides/`, without preserving links to local files outside the current vault.
- Find papers relevant to a topic.
- Build a topic guide for a research goal.
- Search for missing literature and stage papers for Zotero.
- Compare methods across papers.
- Generate a main guide plus section notes for a survey or reading path.
- Update Obsidian dashboards and guide backlinks.
- Emit typed relationships for later graph work.
