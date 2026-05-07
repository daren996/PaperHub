# MCP 计划

[English](../mcp.md) | [中文](mcp.md)

MCP 应成为 PaperHub 稳定的 agent interface。

## 为什么 MCP 优先

Codex plugins、Claude Code plugins 和 editor-specific integrations 可能变化。MCP 给 PaperHub 一个可复用的 agent surface，可以被多个环境调用。

## 候选 Tools

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

## 首批已实现 Tools

初始 MCP wrapper 暴露：

```text
list_papers
run_paperhub_doctor
```

运行方式：

```bash
paperhub mcp serve --vault /path/to/ObsidianVault
```

## 预期 Agent Tasks

- 导入一个 Zotero collection。
- 导入并规范化 Markdown research source 到 `Papers/` 和 `Guides/`，且不保留指向当前 vault 外本地文件的 links。
- 查找与某个 topic 相关的论文。
- 为一个研究目标构建 topic guide。
- 搜索缺失文献并 stage papers for Zotero。
- 比较多篇论文的方法。
- 为 survey 或 reading path 生成 main guide 加 section notes。
- 更新 Obsidian dashboards 和 guide backlinks。
- 为之后的 graph work 产出 typed relationships。
