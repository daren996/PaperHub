# PaperHub 产品简报

[English](../product-brief.md) | [中文](product-brief.md)

PaperHub 本质上不是 Obsidian 插件、Zotero 插件或单个 skill。它是围绕 Zotero、本地 Obsidian vault、CLI、MCP tools 和可复用 agent workflow 构建的 agent-native 文献知识管理器。

## 一句话项目

构建一个面向研究者的论文知识管理 agent 系统：连接 Zotero 账户，同步 papers、collections、tags、notes、attachments metadata、annotations、relations 和 sync versions，把外部 Markdown research guide / digest 处理成稳定 vault 结构，把结构化 Markdown 写入本地 Obsidian vault，并给 Codex / Claude Code / MCP 稳定入口来整理、扩展和综合文献。

Processed Markdown guide / digest import 通过 `paperhub import markdown` 支持。它不是复制命令：必须分类文件，提取 paper metadata 和 guide structure，尽可能与 Zotero 对齐，并把结果写入 `Papers/` 和 `Guides/`。生成的 import 输出不得引用当前 vault 外的本地文件；Web URL 可以保留，但 source repository files、绝对路径、本地图片和附件应被移除、改写成 vault-local links，或转成纯文本。

## 核心 Vault Surfaces

```text
Papers/        规范化 paper notes，包含 digest、annotations、synthesis 和 Zotero metadata
Guides/        课题文件夹，包含 main Markdown guide 和 paper-backed sections
```

详细输出规范见 [../generated-vault.md](../generated-vault.md)。

## 核心工作流

```text
Zotero 账户
  ↓
导入 papers / collections / tags / notes / attachments metadata / annotations / relations / sync versions
  ↓
规范化 PaperHub paper index
  ↓
处理 Markdown guide / digest sources
  ↓
把完整 paper notes 写进 Papers/
  ↓
把 main guide 加 section notes 写进 Guides/<topic>/
  ↓
让 guide sections 回链到 papers
  ↓
产出 guide-section-cites-paper relationship data
  ↓
Codex / Claude Code 持续维护
```

## Obsidian 中的目标体验

用户打开 Obsidian 后，应看到研究驾驶舱，而不是一堆文件：

```text
00 Home.md
01 Reading Dashboard.md
02 Paper Index.md

Papers/
Guides/
```

`Papers/` 存放规范化 paper notes。`Guides/` 每个文件夹对应一个课题；substantial topic 应有 main guide 和有意义的 section notes。Guide 是用户真正阅读的 reading/survey artifact，literature-backed sections 应回链到 `Papers/`。

## MVP

```text
1. 连接 Zotero 账户，或先支持 staged export。
2. 连接 Obsidian vault。
3. 同步 Zotero 中全部 papers，并可选支持 collection filtering。
4. 将每个同步到的 Zotero paper 写入 Papers/ 下对应的规范化 Markdown 文件。
5. 在该文件中组织所有 Zotero-derived paper information，包括 collections、tags、notes、attachments metadata、annotations、relations 和 sync versions。
6. 支持 processed Markdown import，把内容写入 Papers/ 和 Guides/。
7. 支持 agent topic-guide generation：用户提供课题，agent 全网搜索，把缺失 paper 加进 Zotero 或 staged queue，创建规范化 Papers/ notes，在 Guides/<topic>/ 写入 main guide 加 section notes，并产出 section-to-paper relationship data。
8. 提供 MCP / CLI / skills，让 Codex 和 Claude Code 可以继续操作。
```

Graph-like visualization 不属于第一阶段实现。未来 graph 必须由明确 typed relationships 支撑；当前 relationship boundary 见 [../generated-vault.md](../generated-vault.md#relationship-manifest)。

## 易用性原则

README 和 CLI 应围绕 shortest useful path 设计。命令细节见 [../quickstart.md](../quickstart.md)，未完成 diagnostics work 见 [../../TODO.md](../../TODO.md)。
