# 生成 Vault 规范

[English](../generated-vault.md) | [中文](generated-vault.md)

本文档描述预期的 Obsidian output。

## Root Files

```text
PaperIndex.md
README.md
```

`PaperIndex.md` 是 PaperHub 在 vault 根目录生成的单一入口文件。它合并原来的 home summary、reading dashboard、topic guide links，以及从 citation-key paper note filename 到真实 paper title 的人类可读映射。生成的 paper table 应展示 `Papers/<citation-key>.md` file、完整 paper title、year 和 Zotero key。Citation-key 文件名让 graph labels 更可读；index 负责恢复浏览和查找时需要的 title mapping。

`README.md` 是轻量兼容入口。Processed Markdown import 应更新其中 generated `Topic Guides` section，把当前 topic 的 main guide 链接和 `[[PaperIndex]]` 写进去，同时保留用户笔记。

当 imported paper material 缺少 author 或 year metadata 时，PaperHub 应先从 Zotero、source manifests、DOI/arXiv/OpenReview/ACL metadata 或其他可复核来源补齐 metadata，再写入最终 paper note。不要生成带 `unknown` 或 `nd` 的 filename parts。

## Directories

```text
Papers/
Guides/
```

这是当前 MVP 仅有的 user-visible generated vault surfaces。暂时不生成顶层 `Collections/`、`Concepts/`、`Claims/`、`Reading Paths/` 或 `Templates/` 目录。Zotero collections 作为 source metadata 和 filtering input 保留，并应组织写入对应的 `Papers/` notes。

## Paper Note Contract

Paper notes 位于 `Papers/`。每个同步到的 Zotero paper 都应有对应 Markdown 文件。文件名 stem 应使用稳定的 paper key，而不是完整 title slug。长的人类可读标题应放在 frontmatter、H1 heading 和 wikilink alias 中。这样 Obsidian graph 的节点标签会更短，同时 note 内部仍保留完整标题。

Zotero 为该 paper 提取出的所有信息都应组织写入这个文件，包括但不限于 papers、collections、tags、notes、attachments metadata、annotations、relations 和 sync versions。Paper-level digest、synthesis content、citation data、BibTeX 和用户笔记也属于这里。

Required sections：

- Metadata
- Zotero Sync
- Citation
- BibTeX
- Zotero Collections
- Zotero Tags
- Zotero Notes
- Attachments
- Relations
- Evidence Bundle
- Digest
- Summary
- Method
- Key Findings
- Limitations
- Relevance
- Zotero Annotations
- Key Figures
- Related Papers
- User Notes

`Evidence Bundle` section 应指向 `.paperhub/evidence/<paper-stem>.json` 这个内部 model-facing artifact。`Key Figures` 应在可靠图片抽取不可用时使用稳定 placeholder callouts。`User Notes` section 应在重新生成时被保留。

## Guide Contract

Guide notes 位于 `Guides/<topic>/`。Topic folder 就是 topic ownership 和 slugging boundary；不要新增单独的 `PaperHub/Topic/` output path。

每个 topic folder 应包含一个主 Markdown 文件，例如：

```text
Guides/llm-as-judge/llm-as-judge.md
```

主 guide 负责管理用户想阅读或理解的课题逻辑结构。可以使用 section files 或子文件夹存放详细章节、appendix、tables 或 benchmark notes，但 guide 内容最后应该通过链接回到 `Papers/` 中的规范化 paper notes。

Guide files 应包含：

- topic title；
- purpose and scope；
- learning or reading structure；
- paper-backed sections；
- links to `Papers/`；
- open questions；
- PaperHub 可重写内容的 generated-region markers。

一个有实质内容的主题导入不应该只生成一个 Markdown 文件。当来源材料包含可分离的主题、论点、方法、benchmark 家族、paper cluster 或阅读步骤时，PaperHub 应该写入一个 main guide，再在 `Guides/<topic>/sections/` 或等价的主题子目录下写入 graph-visible 的 section notes。main guide 负责目录、综述和导航；section notes 负责承载聚焦内容，并链接回规范化的 `Papers/` notes。

对于单文件的长篇 research catalog，section notes 应使用 folder-note 形式，让文件系统和 Obsidian graph 都能展示层级，例如 `Guides/<topic>/sections/1-functionality/1-functionality.md`，并在其下继续嵌套子 section 文件夹。
Main guide 只应链接一级 section notes。父 section notes 应链接直属 child sections，而不是直接链接 papers。若父 section 自身也包含 paper bullets，PaperHub 应生成 `overview/overview.md` 子节点承载这些 papers，让可见图保持 `main guide -> sections -> subsections -> papers` 的层级。

## Markdown Import Contract

`paperhub import markdown` 应把异构 source content 转换成同一套 output structure：

```text
source paper digest -> Papers/<citation-key>.md
source guide file   -> Guides/<topic>/<main-or-section>.md
source section       -> Guides/<topic>/sections/<section>/<section>.md
source subfolder    -> Guides/<topic>/sections/<section>/
```

Importer 应报告无法分类或无法对齐的文件。它绝不能把 source tree 直接复制进 vault，也不能在标准 `Guides/<topic>/` contract 之外保留任意 source structure。生成的 import 输出不得链接到当前 vault 外的文件。本地 source links、绝对路径、repository images、attachments 和 provenance paths 应被移除、改写成 vault 内 `Papers/` 或 `Guides/` 链接，或转成非链接文本；Web URL 可以保留。

对于单个很长的 Markdown 来源，importer 也应该检查文件内部的结构边界，而不是把整篇来源当成一个 graph node。H2/H3 sections、paper clusters、显式 citation blocks、benchmark groups 或其他稳定结构标记，只要适合独立浏览，就可以成为 section notes。

## Relationship Manifest

第一条值得进入 graph 的关系先刻意收窄为：

```text
guide-section-cites-paper
```

当 PaperHub 将 guide section 解析到一个或多个规范化 paper notes 时，应将 JSON manifest 写入：

```text
.paperhub/relationships/guide-section-cites-paper.json
```

这个 manifest 目前只包含这一种 typed edge。它面向 Neo4j、RDF tooling、未来的 PaperHub graph command，或只展示 section-to-paper citations 的 Obsidian Canvas/export step，而不是混入 vault 里的无关 wikilinks。

## Visualization Boundary

第一阶段不应把 Obsidian global file-link graph 当成语义知识图谱。PaperHub 应先建模并验证明确 relationships。生成的 guide wikilinks 也应避免中心节点直连大量 paper：main guide 链接一级 sections，父 sections 链接子 sections，只有 leaf section 或 generated overview section 链接 paper notes。初始语义 graph 应只显示 `guide-section-cites-paper` edges；`topic-contains-paper`、`paper-cites-paper` 和 `zotero-item-backs-paper` 可以等建模和验证完成后再扩展。
