# 架构

[English](../architecture.md) | [中文](architecture.md)

PaperHub 应该构建为一个 Python-first、可复用的本地研究 core，并提供多个 interface。

## 分层

```text
src/paperhub/models.py and related core modules
  支撑 Papers/、Guides/、imports 和未来 relationships 的 schemas

src/paperhub/zotero.py
  Zotero account、metadata、collections、tags、notes、attachments metadata、annotations、relations、sync versions

src/paperhub/importers/markdown.py
  processed Markdown guide / digest import

src/paperhub/evidence.py and src/paperhub/enrichment_lint.py
  single-paper evidence bundle construction and generated-note quality checks

src/paperhub/obsidian.py
  Papers/、Guides/、dashboards、indexes

src/paperhub/cli.py
  simple commands for researchers

src/paperhub/mcp_server.py
  tools for Codex、Claude Code、Cursor and other agents

paperhub-agent-plugins
  Codex and Claude Code workflow wrappers
```

## 关键规则

Plugin layer 应该调用 core capabilities。它不应该拥有 paper model、sync pipeline、Markdown importer 或 Obsidian generation logic。

## 数据流

```text
Zotero account
  -> normalized Paper / Annotation records
  -> local PaperHub index
  -> complete Papers/<citation-key>.md notes

External Markdown source tree
  -> classification: paper digest / guide / guide section / support note / unknown
  -> guide splitting: themes / methods / benchmarks / paper clusters / reading steps
  -> extraction: metadata / citation / BibTeX / digest / guide outline
  -> reconciliation with Zotero and PaperHub index

PaperHub index + imported content
  -> Papers/
  -> Guides/<topic>/<topic>.md
  -> Guides/<topic>/sections/*.md
  -> .paperhub/relationships/guide-section-cites-paper.json
  -> MCP tools
  -> CLI / skills / agent workflows

Single paper enrichment
  -> indexed Zotero/PaperHub paper identity
  -> metadata / BibTeX / attachments / annotations / optional PDF text
  -> .paperhub/evidence/<paper-stem>.json
  -> refreshed Papers/<paper-stem>.md scaffold
  -> lint before saving deep-reading scaffolds
```

## Markdown Import 边界

`paperhub import markdown` 是 processed import，不是 file copy。架构边界是：import logic 必须通过 PaperHub models 做 classify、normalize、reconcile 和 write，不能让 source directory layout 直接漏进 vault。详细 import contract 见 [../markdown-import-and-topic-guides.md](../markdown-import-and-topic-guides.md)。

## Agent Topic Guide 边界

Codex / Claude Code workflow 可以创建 topic guides。但 core logic 仍属于 `src/paperhub`：

```text
user topic
  -> deep research / web search by agent
  -> candidate bibliography
  -> Zotero add or staged Zotero import for missing papers
  -> normalized Papers/ notes
  -> Guides/<topic>/<topic>.md main guide
  -> Guides/<topic>/sections/*.md research nodes
  -> guide-section-cites-paper relationship manifest
```

Main guide 是 synthesis 和 navigation layer。Section notes 是 graph-visible topic nodes，用来承载聚焦的 literature-backed content。Agent 可以负责 research 和 drafting，但 PaperHub core 应拥有 validation、deduplication、vault layout 和 deterministic updates。

## Relationship 边界

初始 semantic graph 只应展示一种关系：

```text
guide-section-cites-paper
```

这条关系连接 generated/imported guide section 和规范化 paper note。Manifest contract 见 [../generated-vault.md](../generated-vault.md#relationship-manifest)。更宽的关系类型只有在抽取和验证规则明确后再加入。

## Filename 边界

Paper note filenames 应使用 citation-key stem，例如 `Papers/smith2024attention.md`，由第一作者姓氏、年份和标题第一个有意义的词组成。完整标题保留在 note body、frontmatter 和 link aliases 中。这样 Obsidian graph labels 与导出的 semantic graphs 更可读，同时用户阅读 note 时仍能看到完整人类友好的标题。

## 集成边界

Zotero integration 应支持通过 Zotero API 进行 account-level sync，并保留 local export import 作为早期开发和调试 fallback。

Obsidian integration 应从 local vault path 开始。如果用户使用 Obsidian Sync，PaperHub 写入本地已同步 vault，并让 Obsidian 负责 account synchronization。

当前主路径是：

```text
PaperHub
  -> local Obsidian vault folder
  -> Obsidian app
  -> Obsidian Sync, if enabled
```

PaperHub 的 MVP 不应该依赖 Obsidian cloud API。

之后，PaperHub 可以增加第一方 Obsidian plugin。这个 plugin 应该在选定 vault 内运行，使用 Obsidian 的 Vault API 进行原生 file operations，并调用 PaperHub Python CLI、local service 或 MCP tools 执行 core logic。

## 生成文件安全

生成的 Markdown 应尽可能使用 stable regions：

```markdown
<!-- paperhub:generated:start -->
...
<!-- paperhub:generated:end -->
```

Human-authored content 应该被保留。
