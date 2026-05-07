# Markdown Import 与 Topic Guide 实现方案

[English](../markdown-import-and-topic-guides.md) | [中文](markdown-import-and-topic-guides.md)

本文档描述新的 MVP 方向：PaperHub 需要支持 `paperhub import markdown`，但它只能是 processed import，把外部 research material 规范化成 agent 生成 topic guide 时使用的同一套 Obsidian 结构。

## Output Contract

Vault output 应为：

```text
Papers/
Guides/
```

`Papers/` 存放 paper Markdown files。每个同步到的 Zotero paper 都应有对应文件。一个 paper file 应聚合该 paper 的基础 metadata、Zotero collections、tags、notes、attachments metadata、annotations、relations、sync versions、citation 信息、BibTeX、digest material 和 synthesis sections。

`Guides/` 每个文件夹对应一个 topic。每个 topic folder 有一个主 Markdown guide，用来组织用户想阅读或理解的内容。可以有 section files 和子文件夹，但 guide 最后必须回链到 `Papers/` 中的 paper notes。

暂时不要生成顶层 `Claims/`、`Collections/`、`Reading Paths/`、`Templates/` 或 `Concepts/` 文件夹。

有实质内容的导入不应该只生成一个 topic Markdown 文件。长篇 survey、reading list、benchmark review 或多 paper 研究笔记，应该变成一个 main guide 加多个 graph-visible section notes。main guide 是综述和导航面；section notes 是稳定的 topic-level nodes，并且可以引用一个或多个规范化的 `Papers/` notes。

Importer 或 agent workflow 不能机械地按每个 source file、paper digest 或 heading 拆分。它应该先阅读导入的 guide material，理解作者本来的结构意图，再选择最小且有用的一组 sections。一个有 5 个真正顶层阅读章节的 guide，通常就应该生成 5 个 section notes，而不是每篇 paper 一个 note。

Guide section 里提到的每篇 paper 都应该解析到 `Papers/` 下的 Markdown note。已经在 Zotero-backed index 里的 paper 应链接到 `Papers/<citation-key>.md`。导入来源中出现、但尚未进入 Zotero 的 paper，应先 stage 成 citation-key 形式的 `Papers/*.md`，并写入足够 metadata 和 digest material，方便之后与 Zotero 对齐。

## Command Design

```bash
paperhub import markdown /path/to/research-notes --topic "LLM-as-Judge"
paperhub import markdown /path/to/research-notes --topic "LLM-as-Judge" --dry-run
paperhub import markdown /path/to/research-notes --topic "LLM-as-Judge" --apply
paperhub import markdown /path/to/research-notes --topic "LLM-as-Judge" --on-missing-paper stage
paperhub zotero push-staged
paperhub zotero push-staged --write
```

初始 flags：

- `SOURCE`：必填的一次性 source path。
- `--topic`：先设为必填；topic inference 以后再做。
- 默认行为：只输出 import plan 和 report，不写文件。
- `--dry-run`：保留为默认 preview 行为的兼容别名。
- `--apply`：把复核后的 import plan 写入 vault。
- `--on-missing-paper`：支持 `report` 或 `stage`；默认是 `stage`，让 imported paper digests 先成为本地 `IMPORTED-*` paper notes。
- `--vault`：临时覆盖 `PAPERHUB_VAULT` 的 one-run override。

`paperhub zotero push-staged` 默认只列出 staged imported papers，不写 Zotero。`--write` 才会通过 Zotero Web API 创建 items，之后应运行 `paperhub zotero sync`。

不要添加 `PAPERHUB_MARKDOWN_SOURCE` 或类似持久配置。

## Import Pipeline

1. 发现 `SOURCE` 下的 Markdown files。
2. 分类每个文件：
   - paper digest；
   - topic guide；
   - guide section；
   - guide support note；
   - unknown。
3. 从导入的 guide material 推断 topic section plan：
   - 先读 main guide，而不是只扫 filenames；
   - 识别作者本来的 top-level structure；
   - 选择少量稳定 section；
   - 避免把每个 paper digest 都拆成 guide section。
4. 将有实质内容的 guide source 拆成 topic sections：
   - H2/H3 headings；
   - explicit paper clusters；
   - benchmark or method families；
   - claim/theme groups；
   - reading-path steps。
5. 提取结构化数据：
   - title、authors、year、venue；
   - DOI、URL、arXiv ID、Zotero key；
   - citation text；
   - BibTeX；
   - digest、summary、method、limitations、relevance；
   - outgoing paper references。
6. 对齐 papers：
   - exact Zotero key；
   - DOI；
   - URL/arXiv；
   - normalized title plus author/year；
   - ambiguous 时进入人工 review。
7. 构建能处理异构 source formats 的 import plan：
   - paper note writes；
   - guide writes；
   - 为 unresolved imported papers 写入 staged citation-key `Papers/` notes；
   - staged Zotero additions；
   - `guide-section-cites-paper` relationship records；
   - warnings、boundary cases 和 review items。
8. 写入确定性 output：
   - paper-like content 写入 `Papers/<citation-key>.md`；
   - guide-like content translate 成标准 `Guides/<topic>/` 格式；
   - 为 topic 创建 main guide file；
   - section paper lists 使用指向 `Papers/` 的 wikilinks；
   - 不生成指向当前 vault 外本地文件的 links；
   - 子文件夹只能在 topic folder 下。
9. 可选地把 staged imported papers 推到 Zotero：
   - 用 `paperhub zotero push-staged` 预览；
   - 只有 `paperhub zotero push-staged --write` 才创建 Zotero items；
   - 之后运行 `paperhub zotero sync` 刷新 canonical Zotero-backed notes。
10. 验证 output：
   - 没有 raw source tree copy；
   - 没有指向 vault 外的 source repository links、绝对本地路径、本地图片、附件或 provenance paths；
   - 没有 orphan guide paper references；
   - generated regions 保留 user content；
   - 报告 unresolved files and links。

## Agent Topic Guide Workflow

Codex / Claude Code 可以通过如下 workflow 为用户课题创建知识：

```text
user topic
  -> deep research across the web and current Zotero library
  -> candidate bibliography
  -> add missing papers to Zotero or staged import
  -> complete normalized Papers/ notes
  -> Guides/<topic>/ main guide and section files
  -> relationship manifest for later graph work
```

生成的 guide 应更像结构化 reading guide 或 survey，而不是松散 note dump。每个有文献依据的 section 都应链接到一个或多个规范化 paper notes。

## Knowledge Graph Path

PaperHub 之后可以支持 graph output，但 graph 应由明确 relationships 构成，而不是只依赖 file links。

先从一条真正有用的关系开始：

```text
guide-section-cites-paper
```

第一阶段应先在 `.paperhub/relationships/guide-section-cites-paper.json` 产出 JSON manifest。这个 manifest 只包含已解析的 guide-section-to-paper citations。等这个窄关系被验证后，再渲染 Obsidian Canvas、Mermaid diagram、Neo4j import 或 RDF export。

`topic-contains-paper`、`paper-cites-paper` 和 `zotero-item-backs-paper` 等更宽的关系先作为 future work，等 PaperHub 能明确建模和验证后再加入。

## Filename Policy

生成的 paper filenames 应短且稳定：

```text
Papers/<citation-key>.md
```

不要把完整 paper title 放进文件名。长标题应出现在 frontmatter、H1 headings、paper indexes 和 wikilink aliases 中。这样 Obsidian Graph View 和外部 graph exports 都更可读。

## Acceptance Criteria

- 运行 `paperhub import markdown SOURCE --topic TOPIC` 会输出清楚的 import plan，且不写文件。
- 加 `--apply` 时，只写入 `Papers/`、`Guides/` 和 root dashboard/index files。
- 不在 Zotero 中的 imported paper digests 会写入 `Papers/IMPORTED-*.md`，并可由 `paperhub zotero push-staged` 列出。
- Zotero 写入必须显式执行 `paperhub zotero push-staged --write`。
- Importer 不直接复制 source directory。
- 生成输出不得引用当前 vault 外的文件。Web URL 可以保留；本地 source files、图片、附件、绝对路径和 provenance paths 不得成为 vault links。
- Paper notes 包含 Zotero-derived collections、tags、notes、attachments metadata、annotations、relations、sync versions，以及 citation、BibTeX、digest 和可保留的 user sections。
- Topic guide 有 main Markdown file，并回链到 `Papers/`。
- 已解析的 guide sections 会产出 `guide-section-cites-paper` relationship records。
- Paper note filenames 使用 citation-key stems，而不是 Zotero keys 或 title-length slugs。
- Missing 或 ambiguous papers 会被报告。
- Existing user-authored sections 会被保留。
- Doctor 会报告 broken guide links 和 ambiguous imports。
