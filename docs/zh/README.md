# PaperHub

[English](../../README.md) | [中文](README.md)

PaperHub 是面向 agent 的文献知识管理器，用于把 Zotero、Obsidian 本地 vault、CLI、MCP 和 agent workflow 连成一个可维护的研究工作区。

## 状态

当前仓库处于 MVP 初始化阶段。现有 Python-first core 可以：

- 连接本地 Obsidian vault path；
- 同步 Zotero account；
- 将 Zotero paper 写入规范化的 `Papers/` notes；
- 将外部 Markdown research guides 或 digests 处理进 `Papers/` 与 topic `Guides/`；
- 通过 CLI、MCP 和 PaperHub skill 暴露能力。

生成 vault 的唯一规范见 [../generated-vault.md](../generated-vault.md)。Markdown import 的唯一规范见 [../markdown-import-and-topic-guides.md](../markdown-import-and-topic-guides.md)。

## Quickstart

```bash
cp .env.example .env
# 在 .env 中填写 PAPERHUB_VAULT、ZOTERO_API_KEY 和 ZOTERO_USER_ID。
paperhub init
paperhub zotero connect
paperhub zotero sync
paperhub import markdown /path/to/research-notes --topic "LLM-as-Judge"
paperhub import markdown /path/to/research-notes --topic "LLM-as-Judge" --goal "我需要为 agent benchmark 制定阅读路线。"
paperhub import markdown /path/to/research-notes --topic "LLM-as-Judge" --apply
paperhub paper enrich smith2024attention --mode quick
paperhub zotero push-staged
paperhub doctor
```

多数命令默认读取 `.env` 中的 `PAPERHUB_VAULT`。只有首次设置 vault、切换 vault，或临时覆盖当前 vault 时，才需要显式传入 vault path 或 `--vault`。

Markdown import 的 source path 是一次性任务输入，应留在命令行里，不要写入 `.env`。

## 安装

```bash
python -m venv .venv
.venv/bin/pip install -e '.[dev]'
```

可选 extras：

```bash
.venv/bin/pip install -e '.[mcp]'
.venv/bin/pip install -e '.[pdf]'
```

## 命令一览

```bash
paperhub init                         # 初始化 Papers/ 和 Guides/
paperhub obsidian connect             # 记录本地 vault path
paperhub zotero connect               # 保存 Zotero 设置
paperhub zotero sync                  # 同步 Zotero 到 Papers/
paperhub import markdown SOURCE       # 预览 processed import
paperhub import markdown SOURCE --goal "research task prompt"
paperhub import markdown SOURCE --apply
paperhub paper enrich PAPER --mode quick
paperhub zotero push-staged           # 预览 staged imports 的 Zotero 创建
paperhub doctor
paperhub mcp serve
```

`paperhub import markdown` 默认只预览，只有传 `--apply` 才写入。`paperhub zotero push-staged` 默认也是 dry run，只有传 `--write` 才写 Zotero。

当 import 需要携带用户研究任务或问题时，使用 `--goal`。PaperHub 会把这个 prompt 写入 import plan 和 guide，供 Codex、Claude Code、MCP client 或未来 local synthesis service 做 task-aware synthesis；确定性 import 仍可不调用模型。

## 生成的 Vault 形状

```text
PaperIndex.md
README.md

Papers/
Guides/
```

## 文档

- [Documentation index](../README.md)
- [Quickstart](../quickstart.md)
- [Product brief](../product-brief.md)
- [Architecture](../architecture.md)
- [Generated vault spec](../generated-vault.md)
- [Integration requirements](../integration-requirements.md)
- [Markdown import and topic guides](../markdown-import-and-topic-guides.md)
- [MCP plan](../mcp.md)
- [Redundancy audit](../redundancy-audit.md)
- [Roadmap](../../TODO.md)

## 仓库结构

```text
src/paperhub/          Python core, CLI, Zotero sync, Obsidian export, MCP
templates/obsidian/   Markdown templates for generated vault files
skills/               Agent workflows and PaperHub skill instructions
examples/             Sample vaults and import fixtures
docs/                 User and developer documentation
tests/                Unit and integration tests
```

## License

MIT. See [../../LICENSE](../../LICENSE).
