# TODO

[English](../../TODO.md) | [中文](TODO.md)

这份 roadmap 只跟踪未完成事项。设计规则放在：

- [../generated-vault.md](../generated-vault.md)：vault 输出规范。
- [../markdown-import-and-topic-guides.md](../markdown-import-and-topic-guides.md)：processed Markdown import 规范。
- [../../AGENTS.md](../../AGENTS.md)：持久 agent 项目规则。

## 近期 MVP

- [ ] 添加 CI workflow，运行 lint 和 tests。
- [ ] 决定 generated frontmatter 如何映射回 internal schemas。
- [ ] 定义 metadata merge strategy，覆盖 Zotero sync、Markdown import、agent enrichment 和用户手写内容。
- [ ] 建立 `sync -> normalize -> export` pipeline abstraction。
- [ ] 统一 staged imported paper 的 filename policy：canonical citation-key filename vs 临时 `IMPORTED-*` key。
- [ ] 移除或替换 Markdown import 中重复的 paper-note rendering。

## Zotero Sync

- [x] 支持 Zotero Web API account connection。
- [x] 将 papers、collections、tags、notes、attachment metadata、annotations、relations 和 sync versions 同步进 paper notes。
- [ ] 下载或管理 Zotero attachment metadata 之外的本地 PDF 文件。
- [ ] 增加 staged JSON export import 作为开发路径。
- [ ] 增加 collection 和 tag filtering。
- [ ] 增加 agent research 发现 missing papers 后的 staging helper workflow。

## Processed Markdown Import

- [x] 增加 preview-first `paperhub import markdown SOURCE --topic TOPIC`。
- [x] Discover、classify、reconcile，并将 imported content 写入 `Papers/` 和 `Guides/`。
- [x] 清理或重写指向当前 vault 外部本地文件的 generated links。
- [x] Emit `guide-section-cites-paper` relationship records。
- [ ] 从 imported paper digests 提取更完整 metadata：authors、year、venue、DOI、URL、Zotero key、citation text、BibTeX、summary、method、limitations、relevance。
- [ ] 验证每个 literature-backed guide section 都链接到一个或多个 `Papers/` notes。
- [ ] 改进 guide section planning：读取长 source guides，避免机械拆分。

## Obsidian Export

- [x] 生成 `Papers/`、`Guides/`、home、dashboard 和 paper index。
- [x] regeneration 时保留用户手写 note sections。
- [x] 使用短且稳定的 citation-key paper filenames，并为 collision 加 suffix。
- [x] 将 Zotero collections/tags/notes/attachments/annotations/relations 保留在 paper notes 内。
- [ ] 在 templates、linting、imported notes 和 docs 之间使用同一个 canonical paper-note section contract。
- [ ] 决定 dashboard rendering 使用 Jinja template 还是继续 code-generated。
- [ ] 为 guide files 增加 generated-region handling，而不是整文件重写。

## Agent And MCP

- [x] 定义 PaperHub skill workflow。
- [x] 实现初始 MCP tools：`list_papers`、`run_paperhub_doctor`。
- [ ] 增加 MCP tool `get_paper`。
- [ ] 增加 MCP tool `search_papers`。
- [ ] 增加 MCP tool `import_markdown`。
- [ ] 增加 MCP tool `create_topic_guide`。
- [ ] 增加 MCP tool `update_paper_note`。
- [ ] 增加 MCP tool `generate_synthesis`。
- [ ] 增加 MCP tool `emit_relationship_manifest`。
- [ ] 增加 prompt contract，要求新发现 papers 具备 citations 和 paper metadata。

## Doctor

- [x] Report vault/index existence。
- [x] Report duplicate titles、URLs、DOIs 和 citation keys。
- [x] Report missing abstracts、URLs、DOIs、PDF links、annotations 和 local PDF availability。
- [x] Report Zotero Desktop local API 与 Better BibTeX JSON-RPC availability。
- [ ] Report paper index generation。
- [ ] Report Zotero Web API credential status。
- [ ] Report Markdown import readiness。
- [ ] Report unknown imported files 和 ambiguous paper matches。
- [ ] Report broken guide-to-paper links。
- [ ] Report MCP configuration status。
- [ ] Report output compatibility。

## Later

```bash
paperhub paper fix --missing-summary
paperhub guide create --topic "LLMs as Judges" --deep-research
paperhub guide refresh --topic "LLMs as Judges"
paperhub survey outline --topic "LLM-as-Judge"
paperhub graph export --topic "LLM-as-Judge" --relationship guide-section-cites-paper
```
