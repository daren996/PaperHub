# 集成要求

[English](../integration-requirements.md) | [中文](integration-requirements.md)

PaperHub 当前支持三个真实世界入口：

```text
Zotero 账户
External Markdown research source
Obsidian vault
```

Markdown import 只通过 `paperhub import markdown` 作为 processed import 支持。不要加入 raw copy 行为，也不要把 Markdown source path 写进持久配置。

## Zotero 账户

PaperHub 应连接用户的 Zotero 账户，并管理 Zotero 可提供的所有 paper-level information，包括但不限于 papers、collections、tags、notes、attachments metadata、annotations、relations 和 sync versions。

需要支持：

- 全库同步。
- collection filtering 作为 source filtering，而不是 generated `Collections/` output。
- tag filtering。
- 增量更新。
- 为每个同步到的 Zotero paper 在 `Papers/` 下生成 paper note。
- 在 paper note 中有组织地写入 collections、tags、notes、attachments metadata、annotations、relations 和 sync versions。
- 缺 PDF / 缺 abstract / 重复论文检查。
- Zotero item key 的稳定保存。

## Markdown Import

PaperHub 应接受一次性的 Markdown source path：

```text
paperhub import markdown /path/to/research-notes --topic "LLM-as-Judge"
paperhub import markdown /path/to/research-notes --topic "LLM-as-Judge" --apply
```

该命令默认只预览。只有加 `--apply` 时才写入。

需要支持：

- Source paths 是 task-specific inputs，不是 persistent config。
- Importer 必须先 classify、normalize、reconcile 并报告 ambiguity，再写入。
- Applied output 必须留在 `Papers/`、`Guides/`、generated root files 和 internal `.paperhub/` state 内。
- Staged Zotero writes 必须通过显式的 `paperhub zotero push-staged --write`。

详细 import pipeline 和 acceptance criteria 见 [../markdown-import-and-topic-guides.md](../markdown-import-and-topic-guides.md)。

## Obsidian

PaperHub 应写入本地 Obsidian vault 路径：

```text
paperhub init
paperhub obsidian connect
```

这两个命令默认读取 `.env` 中的 `PAPERHUB_VAULT`。只有创建或切换到另一个本地 vault 时才显式传路径。

如果用户使用 Obsidian Sync，PaperHub 只负责写入本地已同步 vault，账号同步交给 Obsidian。

PaperHub 应在 vault 里生成：

```text
Papers/
Guides/
```

并生成 dashboard 和 index。详细 vault contract 见 [../generated-vault.md](../generated-vault.md)。

## Agent Customization

Codex / Claude Code 应帮助处理 Zotero-backed paper notes、processed Markdown import、topic guide generation 和 paper-note enrichment：

```text
导入并规范化已有 Markdown research repository。
根据用户给出的课题生成 topic guide。
全网搜索补齐缺失文献。
先把缺失 papers 本地 stage，再在用户明确批准后创建 Zotero items。
更新 paper note 的 generated sections。
在单篇论文写作前构建 `.paperhub/evidence/<paper-stem>.json` evidence bundles。
基于 guide 或 paper set 生成 main guide 加 graph-visible section notes。
为之后的 graph work 产出 relationship data。
```

人写的内容默认保留。agent 写的内容放进 generated regions；除非用户明确要求，否则更新时只重写 generated regions。单篇论文 deep enrichment 在没有 PDF text 或 Zotero annotations 时应失败。
