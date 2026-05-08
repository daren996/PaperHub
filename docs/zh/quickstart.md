# 快速开始

[English](../quickstart.md) | [中文](quickstart.md)

这是首次运行体验。

## 目标

连接 Zotero，连接 Obsidian vault，并生成：

- paper index
- 为每个同步到的 Zotero paper 生成规范化 `Papers/` notes
- `Guides/` 下的 topic guides
- reading dashboard
- agent 可访问的项目状态

## 计划流程

```bash
cp .env.example .env
# 在 .env 中填写 PAPERHUB_VAULT、ZOTERO_API_KEY 和 ZOTERO_USER_ID。
paperhub init
paperhub zotero connect
paperhub zotero sync
paperhub import markdown /path/to/research-notes --topic "LLM-as-Judge"
paperhub import markdown /path/to/research-notes --topic "LLM-as-Judge" --apply
paperhub paper enrich smith2024attention --mode quick
paperhub zotero push-staged
paperhub doctor
```

大多数命令会读取 `.env` 里的 `PAPERHUB_VAULT`。只有临时覆盖或切换 vault 时，才需要传 `--vault /path/to/ObsidianVault`。

Markdown import source path 应留在命令行，不要写进 `.env`。

`paperhub import markdown` 默认先预览：不加 `--apply` 时只输出 import plan，不写文件。应用前应检查 planned `Papers/`、`Guides/`、staged papers、ambiguous matches、guide sections 和 broken links。

应用 Markdown import 后，生成内容不得链接到当前 vault 外的本地文件。Source repository links、绝对路径、本地图片和附件会被移除、尽可能改写成 vault 内 `Papers/` 或 `Guides/` 链接，或保留为纯文本；Web URL 会保留。

`paperhub paper enrich PAPER --mode quick|deep` 会为已进入 index 的论文构建本地 evidence bundle，并刷新该 paper note 的 scaffold。`quick` 可以只基于 metadata；`deep` 必须有 PDF text 或 Zotero annotations。

`paperhub zotero push-staged` 会预览 imported `IMPORTED-*` papers，默认不写 Zotero。只有加 `--write` 时才会创建 Zotero items；写入后再运行 `paperhub zotero sync` 刷新 official Zotero-backed paper notes。

## 预期结果

你的 Obsidian vault 应包含：

```text
PaperIndex.md

Papers/
Guides/
```

`Papers/` 存放规范化 paper notes。每个同步到的 Zotero paper 都应有对应 note，用来组织 collections、tags、notes、attachments metadata、annotations、relations、sync versions、digest 和 synthesis content。`Guides/` 每个文件夹对应一个 topic，包含主 guide Markdown file，并用 section files 或子文件夹承载实质研究结构。Main guide 链接一级 sections；leaf 或 generated overview sections 回链到 `Papers/`。

## MVP 范围

第一个版本应能很好地处理 API-backed Zotero account sync、staged Zotero export 和 processed Markdown guide / digest import。它应该优先追求清晰、确定性输出和易调试，而不是宽泛的 feature coverage。
