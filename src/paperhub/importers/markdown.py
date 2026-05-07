from __future__ import annotations

import re
from pathlib import Path

from paperhub.models import (
    Guide,
    GuideSection,
    MarkdownImportPlan,
    MarkdownImportReport,
    MarkdownImportReviewItem,
    MarkdownSourceFile,
    MissingPaperAction,
    Paper,
    PaperHubIndex,
    PlannedMarkdownWrite,
    Topic,
)
from paperhub.obsidian import paper_filename, paper_filename_map
from paperhub.relationships import write_guide_section_cites_paper_manifest
from paperhub.text import (
    GENERATED_START,
    USER_NOTES_MARKER,
    extract_headings,
    extract_user_notes,
    normalize_doi_value,
    normalize_title,
    short_hash,
    title_from_markdown,
)


def build_markdown_import_plan(
    source: Path,
    topic_name: str,
    index: PaperHubIndex,
    *,
    dry_run: bool = True,
    on_missing_paper: MissingPaperAction = "report",
) -> MarkdownImportPlan:
    source = source.expanduser().resolve()
    if not source.exists():
        raise FileNotFoundError(f"Markdown source does not exist: {source}")
    if source.is_file() and source.suffix.lower() != ".md":
        raise ValueError("Markdown import source must be a Markdown file or directory.")

    topic = Topic(name=topic_name)
    markdown_files = _markdown_files_for_source(source)
    discovered_files: list[MarkdownSourceFile] = []
    planned_writes: list[PlannedMarkdownWrite] = []
    review_items: list[MarkdownImportReviewItem] = []
    sections: list[GuideSection] = []
    main_guide_sources: list[str] = []
    paper_keys: list[str] = []
    staged_papers: list[Paper] = []

    for file_path in markdown_files:
        if _is_hidden_path(file_path, source):
            continue
        content = file_path.read_text(encoding="utf-8")
        relative_path = _relative_source_path(file_path, source)
        title = title_from_markdown(content, file_path.stem)
        headings = extract_headings(content)
        candidate_paper_keys = _candidate_paper_keys(content, title, index.papers)
        classification = _classify_markdown(
            content,
            headings,
            file_path,
            relative_path,
            has_candidate_paper=bool(candidate_paper_keys),
        )
        if _has_paper_markers(content) and _has_guide_markers(content, file_path):
            review_items.append(
                MarkdownImportReviewItem(
                    category="ambiguous-classification",
                    source_path=relative_path,
                    message=(
                        "File contains both paper-digest markers and guide markers; "
                        f"classified as {classification} for now."
                    ),
                )
            )
        candidate_paper_paths = _paper_paths_for_keys(index.papers, candidate_paper_keys)
        discovered_files.append(
            MarkdownSourceFile(
                source_path=relative_path,
                classification=classification,
                title=title,
                headings=headings,
                candidate_paper_keys=candidate_paper_keys,
                confidence=_classification_confidence(classification, candidate_paper_keys),
            )
        )

        if candidate_paper_keys:
            paper_keys.extend(candidate_paper_keys)

        if classification == "topic-guide":
            main_guide_sources.append(relative_path)
            planned_writes.append(
                PlannedMarkdownWrite(
                    target_surface="Guides",
                    target_path=f"{topic.guide_folder}/{topic.slug}.md",
                    kind="main-guide",
                    source_paths=[relative_path],
                    paper_keys=candidate_paper_keys,
                    paper_paths=candidate_paper_paths,
                )
            )
        elif classification in {"guide-section", "guide-support-note"}:
            section = GuideSection(
                title=title,
                kind="paper-backed" if candidate_paper_keys else "support-note",
                paper_keys=candidate_paper_keys,
            )
            section_target_path = f"{topic.guide_folder}/sections/{section.filename}"
            if _planned_target_exists(planned_writes, section_target_path):
                section.slug = f"{section.slug}-{short_hash(relative_path)}"
                section_target_path = f"{topic.guide_folder}/sections/{section.filename}"
            sections.append(section)
            planned_writes.append(
                PlannedMarkdownWrite(
                    target_surface="Guides",
                    target_path=section_target_path,
                    kind="guide-section",
                    source_paths=[relative_path],
                    paper_keys=candidate_paper_keys,
                    paper_paths=candidate_paper_paths,
                    review_required=not candidate_paper_keys,
                )
            )
            if not candidate_paper_keys:
                review_items.append(
                    MarkdownImportReviewItem(
                        category="broken-link",
                        source_path=relative_path,
                        message=(
                            "Guide section has no resolved link to a paper in Papers/. "
                            "Add Zotero keys, DOI values, or exact paper titles."
                        ),
                    )
                )
        elif classification == "paper-digest":
            _plan_paper_digest_write(
                file_path=file_path,
                source_path=relative_path,
                title=title,
                candidate_paper_keys=candidate_paper_keys,
                index=index,
                topic=topic,
                on_missing_paper=on_missing_paper,
                planned_writes=planned_writes,
                review_items=review_items,
                staged_papers=staged_papers,
            )
        else:
            review_items.append(
                MarkdownImportReviewItem(
                    category="unknown-file",
                    source_path=relative_path,
                    message="Could not classify Markdown file as guide or paper content.",
                )
            )

    if not any(write.kind == "main-guide" for write in planned_writes):
        planned_writes.insert(
            0,
            PlannedMarkdownWrite(
                target_surface="Guides",
                target_path=f"{topic.guide_folder}/{topic.slug}.md",
                kind="main-guide",
                source_paths=main_guide_sources,
                paper_keys=sorted(set(paper_keys)),
                paper_paths=_paper_paths_for_keys(index.papers, sorted(set(paper_keys))),
                review_required=not discovered_files,
            ),
        )

    if not discovered_files:
        review_items.append(
            MarkdownImportReviewItem(
                category="unknown-file",
                source_path=str(source),
                message="No Markdown files were discovered in the source.",
            )
        )

    guide = Guide(
        topic=topic,
        sections=sections,
        paper_keys=sorted(set(paper_keys)),
    )
    return MarkdownImportPlan(
        source_path=str(source),
        topic=topic,
        dry_run=dry_run,
        on_missing_paper=on_missing_paper,
        discovered_files=discovered_files,
        planned_writes=_merge_duplicate_writes(planned_writes),
        review_items=_merge_duplicate_review_items(review_items),
        staged_papers=_dedupe_staged_papers(staged_papers),
        guide=guide,
    )


def execute_markdown_import(vault: Path, plan: MarkdownImportPlan) -> MarkdownImportReport:
    written_paths: list[str] = []
    skipped_paths: list[str] = []
    source_root = Path(plan.source_path)
    vault = vault.expanduser().resolve()

    if not plan.dry_run:
        _remove_stale_generated_sections(vault, plan)

    for write in plan.planned_writes:
        target = vault / write.target_path
        if plan.dry_run:
            skipped_paths.append(write.target_path)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        if write.kind == "main-guide":
            target.write_text(_render_main_guide(plan), encoding="utf-8")
        elif write.kind in {"guide-section", "guide-support-note"}:
            target.write_text(
                _render_guide_section(source_root, write, plan),
                encoding="utf-8",
            )
        elif write.kind == "paper-note":
            _write_imported_paper_note(target, source_root, write, plan.topic)
        written_paths.append(write.target_path)

    if not plan.dry_run:
        write_guide_section_cites_paper_manifest(vault, plan)
        _write_root_readme(vault, plan)
        written_paths.append("README.md")

    status = "planned" if plan.dry_run else "completed"
    if plan.review_items and not plan.dry_run:
        status = "completed-with-review"
    return MarkdownImportReport(
        source_path=plan.source_path,
        topic=plan.topic,
        status=status,
        planned_write_count=len(plan.planned_writes),
        completed_write_count=len(written_paths),
        written_paths=written_paths,
        skipped_paths=skipped_paths,
        review_items=plan.review_items,
    )


def _plan_paper_digest_write(
    *,
    file_path: Path,
    source_path: str,
    title: str,
    candidate_paper_keys: list[str],
    index: PaperHubIndex,
    topic: Topic,
    on_missing_paper: MissingPaperAction,
    planned_writes: list[PlannedMarkdownWrite],
    review_items: list[MarkdownImportReviewItem],
    staged_papers: list[Paper],
) -> None:
    if len(candidate_paper_keys) == 1:
        paper = next(
            (paper for paper in index.papers if paper.key == candidate_paper_keys[0]),
            None,
        )
        if paper:
            target = f"Papers/{_paper_filename_for_index(index.papers, paper)}.md"
            planned_writes.append(
                PlannedMarkdownWrite(
                    target_surface="Papers",
                    target_path=target,
                    kind="paper-note",
                    source_paths=[source_path],
                    paper_keys=[paper.key],
                    paper_paths=[target],
                )
            )
            return
    if len(candidate_paper_keys) > 1:
        review_items.append(
            MarkdownImportReviewItem(
                category="ambiguous-paper-match",
                source_path=source_path,
                message="Paper digest matched multiple existing papers.",
                candidate_targets=candidate_paper_keys,
            )
        )
        return

    if on_missing_paper == "report":
        review_items.append(
            MarkdownImportReviewItem(
                category="ambiguous-paper-match",
                source_path=source_path,
                message=(
                    "Paper digest did not match an existing paper; rerun with "
                    "--on-missing-paper stage to stage it."
                ),
            )
        )
        return

    key = _staged_paper_key(title, file_path)
    staged_paper = Paper(key=key, title=title, topics=[topic.name])
    staged_papers.append(staged_paper)
    target = f"Papers/{paper_filename(staged_paper)}.md"
    planned_writes.append(
        PlannedMarkdownWrite(
            target_surface="Papers",
            target_path=target,
            kind="paper-note",
            source_paths=[source_path],
            paper_keys=[key],
            paper_paths=[target],
            review_required=True,
        )
    )
    review_items.append(
        MarkdownImportReviewItem(
            category="ambiguous-paper-match",
            source_path=source_path,
            message=(
                f"Paper digest was staged under {target}; reconcile it with Zotero "
                "before treating it as a canonical paper."
            ),
            candidate_targets=[target, topic.guide_folder],
        )
    )


def _classify_markdown(
    content: str,
    headings: list[str],
    path: Path,
    relative_path: str = "",
    *,
    has_candidate_paper: bool = False,
) -> str:
    name = path.stem.lower()
    has_paper_markers = _has_paper_markers(content)
    has_guide_markers = _has_guide_markers(content, path)
    if _is_paper_catalog_source(relative_path):
        return "paper-digest" if content.strip() else "unknown"
    if has_paper_markers and not has_guide_markers:
        return "paper-digest"
    if has_guide_markers or "guide" in name or "survey" in name:
        return "topic-guide"
    if _is_top_level_source(relative_path) and len(headings) >= 2 and not has_candidate_paper:
        return "topic-guide"
    if len(headings) >= 2:
        return "guide-section"
    if content.strip():
        return "guide-support-note"
    return "unknown"


def _has_paper_markers(content: str) -> bool:
    lower = content.lower()
    return any(
        marker in lower
        for marker in [
            "doi:",
            "bibtex",
            "@article",
            "@inproceedings",
            "abstract:",
            "## method",
            "## limitations",
        ]
    )


def _has_guide_markers(content: str, path: Path) -> bool:
    lower = content.lower()
    name = path.stem.lower()
    return (
        any(
            marker in lower
            for marker in ["reading path", "survey", "## overview", "## open questions"]
        )
        or "guide" in name
        or "survey" in name
    )


def _candidate_paper_keys(content: str, title: str, papers: list[Paper]) -> list[str]:
    normalized_source_title = normalize_title(title)
    doi = _extract_doi(content)
    candidates: list[str] = []
    for paper in papers:
        if paper.key and re.search(rf"\b{re.escape(paper.key)}\b", content):
            candidates.append(paper.key)
            continue
        if doi and paper.doi and normalize_doi_value(doi) == normalize_doi_value(paper.doi):
            candidates.append(paper.key)
            continue
        if normalized_source_title and normalize_title(paper.title) == normalized_source_title:
            candidates.append(paper.key)
    return sorted(set(candidates))


def _paper_paths_for_keys(papers: list[Paper], paper_keys: list[str]) -> list[str]:
    paths = []
    filenames_by_key = paper_filename_map(papers)
    for key in paper_keys:
        paper = next((candidate for candidate in papers if candidate.key == key), None)
        if paper:
            filename = filenames_by_key.get(paper.key, paper_filename(paper))
            paths.append(f"Papers/{filename}.md")
    return paths


def _paper_filename_for_index(papers: list[Paper], paper: Paper) -> str:
    return paper_filename_map(papers).get(paper.key, paper_filename(paper))


def _extract_doi(content: str) -> str:
    match = re.search(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", content, flags=re.IGNORECASE)
    return match.group(0).rstrip(".,);") if match else ""


def _staged_paper_key(title: str, file_path: Path) -> str:
    normalized = normalize_title(title)
    identity = normalized or str(file_path)
    return f"IMPORTED-{short_hash(identity)}"


def _classification_confidence(classification: str, candidate_paper_keys: list[str]) -> float:
    if classification == "unknown":
        return 0.0
    if classification == "paper-digest" and candidate_paper_keys:
        return 0.9
    if classification in {"topic-guide", "guide-section"}:
        return 0.75
    return 0.5


def _planned_target_exists(writes: list[PlannedMarkdownWrite], target_path: str) -> bool:
    return any(write.target_path == target_path for write in writes)


def _merge_duplicate_writes(writes: list[PlannedMarkdownWrite]) -> list[PlannedMarkdownWrite]:
    output: list[PlannedMarkdownWrite] = []
    for write in writes:
        existing = next(
            (
                candidate
                for candidate in output
                if candidate.target_path == write.target_path and candidate.kind == write.kind
            ),
            None,
        )
        if existing:
            existing.source_paths = sorted(set(existing.source_paths + write.source_paths))
            existing.paper_keys = sorted(set(existing.paper_keys + write.paper_keys))
            existing.paper_paths = sorted(set(existing.paper_paths + write.paper_paths))
            existing.review_required = existing.review_required or write.review_required
            continue
        output.append(write)
    return output


def _merge_duplicate_review_items(
    items: list[MarkdownImportReviewItem],
) -> list[MarkdownImportReviewItem]:
    output: list[MarkdownImportReviewItem] = []
    for item in items:
        existing = next(
            (
                candidate
                for candidate in output
                if candidate.category == item.category
                and candidate.message == item.message
                and candidate.candidate_targets == item.candidate_targets
                and candidate.severity == item.severity
            ),
            None,
        )
        if existing:
            source_paths = sorted(set(existing.source_path.split(", ") + [item.source_path]))
            existing.source_path = ", ".join(source_paths)
            continue
        output.append(item)
    return output


def _dedupe_staged_papers(papers: list[Paper]) -> list[Paper]:
    output: list[Paper] = []
    seen: set[str] = set()
    for paper in papers:
        if paper.key in seen:
            continue
        seen.add(paper.key)
        output.append(paper)
    return output


def _is_hidden_path(path: Path, root: Path) -> bool:
    try:
        relative = path.relative_to(root if root.is_dir() else root.parent)
    except ValueError:
        relative = path
    return any(part.startswith(".") for part in relative.parts)


def _relative_source_path(path: Path, root: Path) -> str:
    base = root if root.is_dir() else root.parent
    return path.relative_to(base).as_posix()


def _markdown_files_for_source(source: Path) -> list[Path]:
    if source.is_dir():
        return sorted(source.rglob("*.md"))
    discovered: list[Path] = []
    seen: set[Path] = set()
    queue = [source]
    base = source.parent
    while queue:
        path = queue.pop(0).resolve()
        if path in seen or path.suffix.lower() != ".md" or not path.exists():
            continue
        seen.add(path)
        discovered.append(path)
        for linked_path in _local_markdown_links(path):
            target = (path.parent / linked_path).resolve()
            try:
                target.relative_to(base)
            except ValueError:
                continue
            if target not in seen:
                queue.append(target)
    return sorted(discovered)


def _local_markdown_links(path: Path) -> list[str]:
    content = path.read_text(encoding="utf-8")
    links = []
    for match in re.finditer(r"\[[^\]]+\]\(([^)]+\.md)(?:#[^)]+)?\)", content):
        link = match.group(1).strip()
        if "://" in link or link.startswith("#") or link.startswith("/"):
            continue
        links.append(link)
    return links


def _is_paper_catalog_source(relative_path: str) -> bool:
    parts = Path(relative_path).parts
    return bool(parts) and parts[0].lower() in {"paper", "papers", "paper-notes"}


def _is_top_level_source(relative_path: str) -> bool:
    return len(Path(relative_path).parts) == 1


def _remove_stale_generated_sections(vault: Path, plan: MarkdownImportPlan) -> None:
    planned_section_paths = {
        write.target_path
        for write in plan.planned_writes
        if write.kind in {"guide-section", "guide-support-note"}
    }
    section_dir = vault / plan.topic.guide_folder / "sections"
    if not section_dir.exists():
        return
    for path in section_dir.glob("*.md"):
        relative_path = path.relative_to(vault).as_posix()
        if relative_path in planned_section_paths:
            continue
        if _is_generated_markdown_without_user_notes(path):
            path.unlink()
    try:
        section_dir.rmdir()
    except OSError:
        pass


def _is_generated_markdown_without_user_notes(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    if GENERATED_START not in text:
        return False
    if USER_NOTES_MARKER not in text:
        return True
    return not text.split(USER_NOTES_MARKER, 1)[1].strip()


def _write_root_readme(vault: Path, plan: MarkdownImportPlan) -> None:
    path = vault / "README.md"
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    user_notes = extract_user_notes(existing)
    entries = _topic_guide_entries(vault, plan)
    entry_lines = "\n".join(
        f"- [[{entry_path.removesuffix('.md')}|{title}]]" for title, entry_path in entries
    )
    content = f"""# PaperHub Vault

<!-- paperhub:generated:start -->

## Topic Guides

{entry_lines or "_No topic guides imported yet._"}

## Indexes

- [[00 Home]]
- [[01 Reading Dashboard]]
- [[02 Paper Index]]

<!-- paperhub:generated:end -->

## User Notes

{user_notes}
"""
    path.write_text(content, encoding="utf-8")

def _topic_guide_entries(vault: Path, plan: MarkdownImportPlan) -> list[tuple[str, str]]:
    entries: dict[str, tuple[str, str]] = {}
    guide_root = vault / "Guides"
    if guide_root.exists():
        for topic_dir in sorted(path for path in guide_root.iterdir() if path.is_dir()):
            guide_path = topic_dir / f"{topic_dir.name}.md"
            if not guide_path.exists():
                continue
            relative_path = guide_path.relative_to(vault).as_posix()
            title = title_from_markdown(guide_path.read_text(encoding="utf-8"), topic_dir.name)
            entries[topic_dir.name] = (title, relative_path)
    current_path = f"{plan.topic.guide_folder}/{plan.topic.slug}.md"
    entries[plan.topic.slug] = (plan.topic.name, current_path)
    return sorted(entries.values(), key=lambda entry: entry[0].lower())


def _source_text(source_root: Path, source_path: str) -> str:
    base = source_root.parent if source_root.is_file() else source_root
    return (base / source_path).read_text(encoding="utf-8")


def _source_title(source_root: Path, source_path: str) -> str:
    return title_from_markdown(_source_text(source_root, source_path), Path(source_path).stem)


def _render_main_guide(plan: MarkdownImportPlan) -> str:
    guide = plan.guide or Guide(topic=plan.topic)
    section_lines = []
    for write in plan.planned_writes:
        if write.kind == "guide-section":
            title = Path(write.target_path).stem.replace("-", " ").title()
            section_lines.append(f"- [[{write.target_path.removesuffix('.md')}|{title}]]")
    paper_lines = _paper_link_lines(plan.planned_writes, guide.paper_keys)
    review_lines = [
        f"- {item.severity}: {item.category} - {item.message}" for item in plan.review_items
    ]
    imported_guide_material = _imported_main_guide_material(Path(plan.source_path), plan)
    return f"""---
type: guide
topic: {plan.topic.name}
topic_slug: {plan.topic.slug}
paper_keys: {guide.paper_keys}
---

# {guide.title}

<!-- paperhub:generated:start -->

## Purpose And Scope

{guide.purpose or "_Imported guide scaffold. Review and refine scope._"}

## Imported Guide Material

{imported_guide_material}

## Reading Structure

{chr(10).join(section_lines) or "_No guide sections imported yet._"}

## Paper Links

{chr(10).join(paper_lines) or "_No paper links resolved yet._"}

## Open Questions

{chr(10).join(review_lines) or "_None recorded during import._"}

<!-- paperhub:generated:end -->

## User Notes
"""


def _imported_main_guide_material(source_root: Path, plan: MarkdownImportPlan) -> str:
    blocks = []
    source_number = 0
    for write in plan.planned_writes:
        if write.kind != "main-guide":
            continue
        for source_path in write.source_paths:
            source_number += 1
            content = _source_text(source_root, source_path)
            content = _rewrite_local_markdown_links_to_papers(
                content, source_path, source_root, plan
            )
            content = _remove_non_vault_file_references(content)
            content = content.strip()
            if content:
                blocks.append(f"### Imported Source {source_number}\n\n{content}")
    return "\n\n".join(blocks) if blocks else "_No source guide material imported yet._"


def _render_guide_section(
    source_root: Path, write: PlannedMarkdownWrite, plan: MarkdownImportPlan
) -> str:
    source_path = write.source_paths[0] if write.source_paths else ""
    title = _source_title(source_root, source_path) if source_path else Path(write.target_path).stem
    content = _source_text(source_root, source_path) if source_path else ""
    content = _rewrite_local_markdown_links_to_papers(content, source_path, source_root, plan)
    content = _remove_non_vault_file_references(content)
    paper_lines = _write_paper_link_lines(write)
    return f"""---
type: guide-section
topic: {plan.topic.name}
topic_slug: {plan.topic.slug}
paper_keys: {write.paper_keys}
---

# {title}

<!-- paperhub:generated:start -->

## Paper Links

{chr(10).join(paper_lines) or "_No paper links resolved yet._"}

## Imported Material

{content.strip() or "_No imported content._"}

<!-- paperhub:generated:end -->

## User Notes
"""


def _render_imported_paper_note(
    source_root: Path, write: PlannedMarkdownWrite, topic: Topic
) -> str:
    source_path = write.source_paths[0] if write.source_paths else ""
    title = _source_title(source_root, source_path) if source_path else Path(write.target_path).stem
    key = write.paper_keys[0] if write.paper_keys else ""
    digest = _imported_paper_digest_blocks(source_root, write.source_paths)
    return f"""---
type: paper
title: {title}
zotero_key: {key}
topics:
- {topic.name}
---

# {title}

<!-- paperhub:generated:start -->

## Metadata

- Source: Markdown import
- Staged Paper Key: `{key}`

## Zotero Sync

_Not reconciled with Zotero yet._

## Citation

_Review imported material and reconcile citation metadata._

## BibTeX

_No BibTeX imported yet._

## Zotero Collections

_None yet._

## Zotero Tags

_None yet._

## Zotero Notes

_None yet._

## Attachments

_No PDF link imported yet._

## Relations

_No Zotero relations imported yet._

## Evidence Bundle

_No evidence bundle generated yet. Run `paperhub paper enrich` after Zotero reconciliation._

## Digest

{digest or "_No imported digest content._"}

## Summary

_Pending review._

## Method

_Pending review._

## Key Findings

_Pending review._

## Limitations

_Pending review._

## Relevance

_Pending review._

## Zotero Annotations

_No annotations imported yet._

## Key Figures

_No figure placeholders generated yet._

## Related Papers

_Pending review._

<!-- paperhub:generated:end -->

## User Notes
"""


def _paper_link_lines(writes: list[PlannedMarkdownWrite], fallback_keys: list[str]) -> list[str]:
    lines: list[str] = []
    seen: set[str] = set()
    seen_keys: set[str] = set()
    for write in writes:
        for key in write.paper_keys:
            seen_keys.add(key)
        for line in _write_paper_link_lines(write):
            if line not in seen:
                lines.append(line)
                seen.add(line)
    for key in fallback_keys:
        if key in seen_keys:
            continue
        line = f"- Zotero/PaperHub paper key: `{key}`"
        if line not in seen:
            lines.append(line)
            seen.add(line)
            seen_keys.add(key)
    return lines


def _write_paper_link_lines(write: PlannedMarkdownWrite) -> list[str]:
    lines = []
    for index, key in enumerate(write.paper_keys):
        paper_path = write.paper_paths[index] if index < len(write.paper_paths) else ""
        if paper_path:
            lines.append(f"- [[{paper_path.removesuffix('.md')}|{key}]]")
        else:
            lines.append(f"- Zotero/PaperHub paper key: `{key}`")
    return lines


def _rewrite_local_markdown_links_to_papers(
    content: str, source_path: str, source_root: Path, plan: MarkdownImportPlan
) -> str:
    paper_paths_by_source = _paper_paths_by_source(plan)
    base = source_root.parent if source_root.is_file() else source_root
    current_file = base / source_path

    def replace(match: re.Match[str]) -> str:
        label = match.group(1)
        link = match.group(2).strip()
        if "://" in link or link.startswith("#") or link.startswith("/"):
            return match.group(0)
        link_path, anchor = _split_markdown_link(link)
        if not link_path.endswith(".md"):
            return match.group(0)
        resolved = (current_file.parent / link_path).resolve()
        try:
            linked_source = resolved.relative_to(base).as_posix()
        except ValueError:
            return match.group(0)
        paper_path = paper_paths_by_source.get(linked_source)
        if not paper_path:
            return match.group(0)
        target = paper_path.removesuffix(".md")
        if anchor:
            target = f"{target}#{anchor}"
        return f"[[{target}|{label}]]"

    return re.sub(r"(?<!!)\[([^\]]+)\]\(([^)]+)\)", replace, content)


def _remove_non_vault_file_references(content: str) -> str:
    content = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", _replace_markdown_image, content)
    content = re.sub(r"(?<!!)\[([^\]]+)\]\(([^)]+)\)", _replace_markdown_link, content)
    content = re.sub(
        r"\b(href|src)=(['\"])([^'\"]+)(['\"])",
        _replace_html_file_attribute,
        content,
        flags=re.IGNORECASE,
    )
    return re.sub(
        r"(?<![`<])(?:~|/Users|/Volumes|/tmp|/var/folders)/[^\s)>\"]+",
        "[local file reference removed]",
        content,
    )


def _replace_markdown_image(match: re.Match[str]) -> str:
    alt = match.group(1).strip()
    link = match.group(2).strip()
    if _is_allowed_import_link(link):
        return match.group(0)
    return alt or "[local image reference removed]"


def _replace_markdown_link(match: re.Match[str]) -> str:
    label = match.group(1)
    link = match.group(2).strip()
    if _is_allowed_import_link(link):
        return match.group(0)
    return label


def _replace_html_file_attribute(match: re.Match[str]) -> str:
    attr = match.group(1)
    quote = match.group(2)
    link = match.group(3).strip()
    if _is_allowed_import_link(link):
        return match.group(0)
    return f"{attr}={quote}#paperhub-removed-local-file-reference{quote}"


def _is_allowed_import_link(link: str) -> bool:
    if not link or link.startswith("#") or link.startswith("[["):
        return True
    link_path, _anchor = _split_markdown_link(link)
    if _has_non_file_uri_scheme(link_path):
        return True
    if link_path.startswith("file:"):
        return False
    normalized = link_path.lstrip("./")
    return normalized.startswith("Papers/") or normalized.startswith("Guides/")


def _has_non_file_uri_scheme(link: str) -> bool:
    match = re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", link)
    return bool(match and match.group(0).lower() != "file:")


def _paper_paths_by_source(plan: MarkdownImportPlan) -> dict[str, str]:
    output: dict[str, str] = {}
    for write in plan.planned_writes:
        if write.kind != "paper-note" or not write.paper_paths:
            continue
        for source_path in write.source_paths:
            output[source_path] = write.paper_paths[0]
    return output


def _split_markdown_link(link: str) -> tuple[str, str]:
    if "#" not in link:
        return link, ""
    path, anchor = link.split("#", 1)
    return path, anchor


def _write_imported_paper_note(
    target: Path, source_root: Path, write: PlannedMarkdownWrite, topic: Topic
) -> None:
    if target.exists():
        existing = target.read_text(encoding="utf-8")
        if _is_staged_import_write(write):
            rendered = _render_imported_paper_note(source_root, write, topic)
            target.write_text(_preserve_user_notes(rendered, existing), encoding="utf-8")
            return
        for source_path in write.source_paths:
            content = _source_text(source_root, source_path)
            existing = _merge_imported_digest(existing, source_path, content)
        target.write_text(existing, encoding="utf-8")
        return
    target.write_text(_render_imported_paper_note(source_root, write, topic), encoding="utf-8")


def _is_staged_import_write(write: PlannedMarkdownWrite) -> bool:
    return bool(write.paper_keys and write.paper_keys[0].startswith("IMPORTED-"))


def _preserve_user_notes(rendered: str, existing: str) -> str:
    if USER_NOTES_MARKER not in existing:
        return rendered
    user_notes = existing.split(USER_NOTES_MARKER, 1)[1]
    if not user_notes.strip():
        return rendered
    return f"{rendered.rstrip()}\n{user_notes}"


def _imported_paper_digest_blocks(source_root: Path, source_paths: list[str]) -> str:
    blocks = []
    source_number = 0
    for source_path in source_paths:
        content = _source_text(source_root, source_path).strip()
        content = _remove_non_vault_file_references(content)
        if content:
            source_number += 1
            blocks.append(f"### Imported Source {source_number}\n\n{content}")
    return "\n\n".join(blocks)


def _merge_imported_digest(existing: str, source_path: str, content: str) -> str:
    source_id = short_hash(source_path)
    start = f"<!-- paperhub:markdown-import:start {source_id} -->"
    end = f"<!-- paperhub:markdown-import:end {source_id} -->"
    content = _remove_non_vault_file_references(content)
    block = f"""{start}

## Imported Markdown Digest

{content.strip() or "_No imported digest content._"}

{end}"""
    pattern = re.compile(re.escape(start) + r".*?" + re.escape(end), flags=re.DOTALL)
    if pattern.search(existing):
        return pattern.sub(block, existing)
    if USER_NOTES_MARKER in existing:
        head, tail = existing.split(USER_NOTES_MARKER, 1)
        return f"{head.rstrip()}\n\n{block}\n{USER_NOTES_MARKER}{tail}"
    return f"{existing.rstrip()}\n\n{block}\n"
