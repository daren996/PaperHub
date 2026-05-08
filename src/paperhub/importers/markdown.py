from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
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
    normalize_url_value,
    short_hash,
    slugify,
    title_from_markdown,
)


@dataclass
class _MarkdownHeading:
    level: int
    title: str
    line_index: int


@dataclass
class _SplitGuideSection:
    title: str
    slug: str
    level: int
    body: str
    source_path: str
    paper_keys: list[str] = field(default_factory=list)
    paper_paths: list[str] = field(default_factory=list)
    target_path: str = ""
    parent_path: str = ""
    child_paths: list[str] = field(default_factory=list)


@dataclass
class _PaperBullet:
    title: str
    body: str
    url: str = ""
    year: int | None = None


def build_markdown_import_plan(
    source: Path,
    topic_name: str,
    index: PaperHubIndex,
    *,
    goal: str = "",
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
            split_sections, main_guide_body = _split_topic_guide_taxonomy(
                content=content,
                source_path=relative_path,
                topic=topic,
                index=index,
                on_missing_paper=on_missing_paper,
                planned_writes=planned_writes,
                review_items=review_items,
                staged_papers=staged_papers,
            )
            for split_section in split_sections:
                paper_keys.extend(split_section.paper_keys)
                sections.append(
                    GuideSection(
                        title=split_section.title,
                        slug=split_section.slug,
                        kind="paper-backed" if split_section.paper_keys else "support-note",
                        paper_keys=split_section.paper_keys,
                        body=split_section.body,
                        review_required=not split_section.paper_keys
                        and not split_section.child_paths,
                    )
                )
                planned_writes.append(
                    PlannedMarkdownWrite(
                        target_surface="Guides",
                        target_path=split_section.target_path,
                        kind="guide-section",
                        source_paths=[relative_path],
                        paper_keys=split_section.paper_keys,
                        paper_paths=split_section.paper_paths,
                        review_required=not split_section.paper_keys
                        and not split_section.child_paths,
                        title=split_section.title,
                        body=split_section.body,
                        section_level=split_section.level,
                        parent_path=split_section.parent_path,
                        child_paths=split_section.child_paths,
                    )
                )
            planned_writes.append(
                PlannedMarkdownWrite(
                    target_surface="Guides",
                    target_path=f"{topic.guide_folder}/{topic.slug}.md",
                    kind="main-guide",
                    source_paths=[relative_path],
                    paper_keys=candidate_paper_keys,
                    paper_paths=candidate_paper_paths,
                    title=title,
                    body=main_guide_body,
                )
            )
        elif classification in {"guide-section", "guide-support-note"}:
            section = GuideSection(
                title=title,
                kind="paper-backed" if candidate_paper_keys else "support-note",
                paper_keys=candidate_paper_keys,
            )
            section_target_path = (
                f"{topic.guide_folder}/sections/{section.slug}/{section.filename}"
            )
            if _planned_target_exists(planned_writes, section_target_path):
                section.slug = f"{section.slug}-{short_hash(relative_path)}"
                section_target_path = (
                    f"{topic.guide_folder}/sections/{section.slug}/{section.filename}"
                )
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
                    title=title,
                    body=content,
                    section_level=1,
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
        purpose=(
            f"Source-derived baseline for the user research goal: {goal}"
            if goal
            else ""
        ),
        sections=sections,
        paper_keys=sorted(set(paper_keys)),
    )
    return MarkdownImportPlan(
        source_path=str(source),
        topic=topic,
        goal=goal,
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


def _split_topic_guide_taxonomy(
    *,
    content: str,
    source_path: str,
    topic: Topic,
    index: PaperHubIndex,
    on_missing_paper: MissingPaperAction,
    planned_writes: list[PlannedMarkdownWrite],
    review_items: list[MarkdownImportReviewItem],
    staged_papers: list[Paper],
) -> tuple[list[_SplitGuideSection], str]:
    lines = content.splitlines()
    headings = _markdown_headings(lines)
    paperlist_heading = next(
        (
            heading
            for heading in headings
            if "paperlist" in normalize_title(heading.title).replace(" ", "")
        ),
        None,
    )
    if not paperlist_heading:
        return [], ""

    taxonomy_headings = [
        heading
        for heading in headings
        if heading.line_index > paperlist_heading.line_index
        and _numbered_taxonomy_title(heading.title)
    ]
    if not taxonomy_headings:
        return [], ""

    first_heading = taxonomy_headings[0]
    taxonomy_end = len(lines)
    for heading in headings:
        if heading.line_index <= first_heading.line_index:
            continue
        if heading.level == 1 and not _numbered_taxonomy_title(heading.title):
            taxonomy_end = heading.line_index
            break

    taxonomy_headings = [
        heading for heading in taxonomy_headings if heading.line_index < taxonomy_end
    ]
    main_guide_body = "\n".join(
        lines[: paperlist_heading.line_index] + lines[taxonomy_end:]
    ).strip()
    sections = _build_split_guide_sections(
        lines=lines,
        taxonomy_headings=taxonomy_headings,
        taxonomy_end=taxonomy_end,
        source_path=source_path,
        topic=topic,
        index=index,
        on_missing_paper=on_missing_paper,
        planned_writes=planned_writes,
        review_items=review_items,
        staged_papers=staged_papers,
    )
    return _move_parent_paper_links_to_overview(sections), main_guide_body


def _build_split_guide_sections(
    *,
    lines: list[str],
    taxonomy_headings: list[_MarkdownHeading],
    taxonomy_end: int,
    source_path: str,
    topic: Topic,
    index: PaperHubIndex,
    on_missing_paper: MissingPaperAction,
    planned_writes: list[PlannedMarkdownWrite],
    review_items: list[MarkdownImportReviewItem],
    staged_papers: list[Paper],
) -> list[_SplitGuideSection]:
    sections: list[_SplitGuideSection] = []
    stack: list[_SplitGuideSection] = []
    sibling_slugs_by_parent: dict[str, set[str]] = {}

    for position, heading in enumerate(taxonomy_headings):
        next_heading_line = (
            taxonomy_headings[position + 1].line_index
            if position + 1 < len(taxonomy_headings)
            else taxonomy_end
        )
        body = "\n".join(lines[heading.line_index + 1 : next_heading_line]).strip()
        level = _taxonomy_depth(heading.title)
        base_slug = slugify(_clean_heading_title(heading.title))

        while stack and stack[-1].level >= level:
            stack.pop()
        parent = stack[-1] if stack else None
        parent_path = parent.target_path if parent else ""
        parent_folder = (
            Path(parent.target_path).parent if parent else Path(topic.guide_folder) / "sections"
        )
        slug = _unique_section_slug(base_slug, parent_path, sibling_slugs_by_parent)
        target_path = (parent_folder / slug / f"{slug}.md").as_posix()

        paper_keys: list[str] = []
        paper_paths: list[str] = []
        for bullet in _paper_bullets_from_section(body):
            bullet_keys, bullet_paths = _resolve_or_stage_paper_bullet(
                bullet=bullet,
                source_path=source_path,
                index=index,
                topic=topic,
                on_missing_paper=on_missing_paper,
                planned_writes=planned_writes,
                review_items=review_items,
                staged_papers=staged_papers,
            )
            paper_keys.extend(bullet_keys)
            paper_paths.extend(bullet_paths)

        section = _SplitGuideSection(
            title=_clean_heading_title(heading.title),
            slug=slug,
            level=level,
            body=body,
            source_path=source_path,
            paper_keys=_dedupe_preserving_order(paper_keys),
            paper_paths=_dedupe_preserving_order(paper_paths),
            target_path=target_path,
            parent_path=parent_path,
        )
        if parent:
            parent.child_paths.append(target_path)
        sections.append(section)
        stack.append(section)

    return sections


def _move_parent_paper_links_to_overview(
    sections: list[_SplitGuideSection],
) -> list[_SplitGuideSection]:
    output: list[_SplitGuideSection] = []
    for section in sections:
        output.append(section)
        if not section.child_paths or not section.paper_keys:
            continue
        overview_path = (Path(section.target_path).parent / "overview" / "overview.md").as_posix()
        overview = _SplitGuideSection(
            title=f"{section.title} Overview",
            slug="overview",
            level=section.level + 1,
            body=section.body,
            source_path=section.source_path,
            paper_keys=section.paper_keys,
            paper_paths=section.paper_paths,
            target_path=overview_path,
            parent_path=section.target_path,
        )
        section.child_paths = [overview_path, *section.child_paths]
        section.paper_keys = []
        section.paper_paths = []
        section.body = ""
        output.append(overview)
    return output


def _resolve_or_stage_paper_bullet(
    *,
    bullet: _PaperBullet,
    source_path: str,
    index: PaperHubIndex,
    topic: Topic,
    on_missing_paper: MissingPaperAction,
    planned_writes: list[PlannedMarkdownWrite],
    review_items: list[MarkdownImportReviewItem],
    staged_papers: list[Paper],
) -> tuple[list[str], list[str]]:
    candidate_paper_keys = _candidate_paper_keys_for_bullet(bullet, index.papers)
    if len(candidate_paper_keys) == 1:
        paper = next(
            (paper for paper in index.papers if paper.key == candidate_paper_keys[0]),
            None,
        )
        if paper:
            return [paper.key], [f"Papers/{_paper_filename_for_index(index.papers, paper)}.md"]
    if len(candidate_paper_keys) > 1:
        review_items.append(
            MarkdownImportReviewItem(
                category="ambiguous-paper-match",
                source_path=source_path,
                message=f"Paper bullet `{bullet.title}` matched multiple existing papers.",
                candidate_targets=candidate_paper_keys,
            )
        )
        return candidate_paper_keys, _paper_paths_for_keys(index.papers, candidate_paper_keys)

    if on_missing_paper == "report":
        review_items.append(
            MarkdownImportReviewItem(
                category="ambiguous-paper-match",
                source_path=source_path,
                message=(
                    f"Paper bullet `{bullet.title}` did not match an existing paper; "
                    "rerun with --on-missing-paper stage to stage it."
                ),
            )
        )
        return [], []

    key = _staged_paper_key_for_bullet(bullet)
    staged_paper = Paper(
        key=key,
        title=bullet.title,
        url=bullet.url,
        topics=[topic.name],
    )
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
            title=bullet.title,
            body=bullet.body,
        )
    )
    review_items.append(
        MarkdownImportReviewItem(
            category="ambiguous-paper-match",
            source_path=source_path,
            message=(
                f"Paper bullet `{bullet.title}` was staged under {target}; reconcile it "
                "with Zotero before treating it as a canonical paper."
            ),
            candidate_targets=[target, topic.guide_folder],
        )
    )
    return [key], [target]


def _markdown_headings(lines: list[str]) -> list[_MarkdownHeading]:
    headings: list[_MarkdownHeading] = []
    for index, line in enumerate(lines):
        match = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if match:
            headings.append(
                _MarkdownHeading(
                    level=len(match.group(1)),
                    title=match.group(2).strip(),
                    line_index=index,
                )
            )
    return headings


def _numbered_taxonomy_title(title: str) -> bool:
    return bool(re.match(r"^\s*\d+(?:\.\d+)*\.?\s+\S+", _clean_heading_title(title)))


def _taxonomy_depth(title: str) -> int:
    match = re.match(r"^\s*(\d+(?:\.\d+)*)", _clean_heading_title(title))
    if not match:
        return 1
    return len(match.group(1).split("."))


def _clean_heading_title(title: str) -> str:
    return re.sub(r"^[^\w\d]+", "", title).strip()


def _unique_section_slug(
    base_slug: str, parent_path: str, sibling_slugs_by_parent: dict[str, set[str]]
) -> str:
    siblings = sibling_slugs_by_parent.setdefault(parent_path, set())
    slug = base_slug or "section"
    if slug in siblings:
        slug = f"{slug}-{short_hash(parent_path + '/' + base_slug)}"
    siblings.add(slug)
    return slug


def _paper_bullets_from_section(body: str) -> list[_PaperBullet]:
    lines = body.splitlines()
    bullets: list[_PaperBullet] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        match = re.match(r"^\s*[-*]\s+\*\*(.+?)\*\*", line)
        if not match:
            index += 1
            continue
        block_lines = [line]
        index += 1
        while index < len(lines):
            candidate = lines[index]
            if re.match(r"^\s*[-*]\s+\*\*", candidate) or re.match(r"^#{1,6}\s+", candidate):
                break
            block_lines.append(candidate)
            index += 1
        block = "\n".join(block_lines).strip()
        title = re.sub(r"\s+", " ", match.group(1)).strip()
        bullets.append(
            _PaperBullet(
                title=title,
                body=block,
                url=_extract_paper_url(block),
                year=_extract_year(block),
            )
        )
    return bullets


def _candidate_paper_keys_for_bullet(bullet: _PaperBullet, papers: list[Paper]) -> list[str]:
    content = f"{bullet.title}\n{bullet.body}\n{bullet.url}"
    key_matches = [
        paper.key
        for paper in papers
        if paper.key and re.search(rf"\b{re.escape(paper.key)}\b", content)
    ]
    if key_matches:
        return sorted(set(key_matches))

    doi = _extract_doi(content)
    doi_matches = [
        paper.key
        for paper in papers
        if doi and paper.doi and normalize_doi_value(doi) == normalize_doi_value(paper.doi)
    ]
    if doi_matches:
        return sorted(set(doi_matches))

    normalized_url = normalize_url_value(bullet.url)
    url_matches = [
        paper.key
        for paper in papers
        if normalized_url
        and paper.url
        and normalize_url_value(paper.url) == normalized_url
    ]
    if url_matches:
        return sorted(set(url_matches))

    normalized_title = normalize_title(bullet.title)
    title_matches = [
        paper.key
        for paper in papers
        if normalized_title and normalize_title(paper.title) == normalized_title
    ]
    return sorted(set(title_matches))


def _extract_paper_url(block: str) -> str:
    paper_link = re.search(r"\[\s*Paper\s*\]\(([^)]+)\)", block, flags=re.IGNORECASE)
    if paper_link:
        return paper_link.group(1).strip()
    generic_link = re.search(r"https?://[^\s)\]]+", block)
    return generic_link.group(0).rstrip(".,);") if generic_link else ""


def _extract_year(block: str) -> int | None:
    match = re.search(r"\b(19|20)\d{2}\b", block)
    return int(match.group(0)) if match else None


def _staged_paper_key_for_bullet(bullet: _PaperBullet) -> str:
    identity = normalize_title(bullet.title) or normalize_url_value(bullet.url) or bullet.body
    return f"IMPORTED-{short_hash(identity)}"


def _dedupe_preserving_order(values: list[str]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        output.append(value)
    return output


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
            existing.source_paths = _dedupe_preserving_order(
                existing.source_paths + write.source_paths
            )
            existing.paper_keys = _dedupe_preserving_order(
                existing.paper_keys + write.paper_keys
            )
            existing.paper_paths = _dedupe_preserving_order(
                existing.paper_paths + write.paper_paths
            )
            existing.review_required = existing.review_required or write.review_required
            existing.child_paths = _dedupe_preserving_order(
                existing.child_paths + write.child_paths
            )
            existing.title = existing.title or write.title
            existing.parent_path = existing.parent_path or write.parent_path
            existing.section_level = existing.section_level or write.section_level
            if write.body and write.body not in existing.body:
                existing.body = (
                    f"{existing.body.rstrip()}\n\n{write.body.strip()}".strip()
                    if existing.body
                    else write.body
                )
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
    for path in section_dir.rglob("*.md"):
        relative_path = path.relative_to(vault).as_posix()
        if relative_path in planned_section_paths:
            continue
        if _is_generated_markdown_without_user_notes(path):
            path.unlink()
            continue
        plan.review_items.append(
            MarkdownImportReviewItem(
                category="unsupported-structure",
                source_path=relative_path,
                message=(
                    "Stale generated guide section has user notes or non-generated "
                    "content; left it in place during reimport."
                ),
            )
        )
    for directory in sorted(
        (path for path in section_dir.rglob("*") if path.is_dir()),
        key=lambda path: len(path.parts),
        reverse=True,
    ):
        try:
            directory.rmdir()
        except OSError:
            pass
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

- [[PaperIndex]]

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
    section_lines = _top_level_section_lines(plan)
    review_lines = [
        f"- {item.severity}: {item.category} - {item.message}" for item in plan.review_items
    ]
    imported_guide_material = _imported_main_guide_material(Path(plan.source_path), plan)
    goal_block = (
        plan.goal
        if plan.goal
        else "_No user research goal was provided for this import._"
    )
    synthesis_brief = (
        _task_aware_synthesis_brief(plan)
        if plan.goal
        else "_Add `--goal` to create an agent-ready synthesis brief for this source._"
    )
    return f"""---
type: guide
topic: {plan.topic.name}
topic_slug: {plan.topic.slug}
goal: {json.dumps(plan.goal, ensure_ascii=False)}
paper_keys: {guide.paper_keys}
---

# {guide.title}

<!-- paperhub:generated:start -->

## Purpose And Scope

{guide.purpose or "_Imported guide scaffold. Review and refine scope._"}

## User Research Goal

{goal_block}

## Agent Synthesis Brief

{synthesis_brief}

## Source-Derived Baseline

{imported_guide_material}

## Reading Structure

{chr(10).join(section_lines) or "_No guide sections imported yet._"}

## Open Questions

{chr(10).join(review_lines) or "_None recorded during import._"}

<!-- paperhub:generated:end -->

## User Notes
"""


def _task_aware_synthesis_brief(plan: MarkdownImportPlan) -> str:
    return "\n".join(
        [
            "Use this imported source as evidence, not as the final outline.",
            "Reorganize the reading path around the user's role, constraints, and target artifact.",
            (
                "Prefer a small ordered set of paper-backed sections over the source "
                "repository taxonomy."
            ),
            (
                "Every recommended paper should resolve to a normalized `Papers/` note "
                "or a staged imported paper."
            ),
            (
                "Codex, Claude Code, an MCP client, or a future PaperHub service can own "
                "the open-ended synthesis step; PaperHub core owns extraction, "
                "reconciliation, vault writes, and validation."
            ),
        ]
    )


def _top_level_section_lines(plan: MarkdownImportPlan) -> list[str]:
    section_writes = [write for write in plan.planned_writes if write.kind == "guide-section"]
    top_level_writes = [write for write in section_writes if not write.parent_path]

    def sort_key(write: PlannedMarkdownWrite) -> tuple[int, str]:
        return (write.section_level or 999, write.target_path)

    lines: list[str] = []
    for child in sorted(top_level_writes, key=sort_key):
        label = child.title or Path(child.target_path).stem.replace("-", " ").title()
        lines.append(f"- [[{child.target_path.removesuffix('.md')}|{label}]]")
    return lines


def _imported_main_guide_material(source_root: Path, plan: MarkdownImportPlan) -> str:
    blocks = []
    source_number = 0
    for write in plan.planned_writes:
        if write.kind != "main-guide":
            continue
        for source_path in write.source_paths:
            source_number += 1
            content = write.body if write.body else _source_text(source_root, source_path)
            content = _remove_non_vault_file_references(content)
            content = content.strip()
            if content:
                blocks.append(f"### Imported Source {source_number}\n\n{content}")
    return "\n\n".join(blocks) if blocks else "_No source guide material imported yet._"


def _render_guide_section(
    source_root: Path, write: PlannedMarkdownWrite, plan: MarkdownImportPlan
) -> str:
    source_path = write.source_paths[0] if write.source_paths else ""
    title = (
        write.title
        or (
            _source_title(source_root, source_path)
            if source_path
            else Path(write.target_path).stem
        )
    )
    content = (
        write.body
        if write.body
        else (_source_text(source_root, source_path) if source_path else "")
    )
    content = _rewrite_local_markdown_links_to_papers(content, source_path, source_root, plan)
    content = _remove_non_vault_file_references(content)
    paper_lines = [] if write.child_paths else _write_paper_link_lines(write)
    child_lines = [
        f"- [[{path.removesuffix('.md')}|{Path(path).stem.replace('-', ' ').title()}]]"
        for path in write.child_paths
    ]
    return f"""---
type: guide-section
topic: {plan.topic.name}
topic_slug: {plan.topic.slug}
paper_keys: {write.paper_keys}
parent: {write.parent_path}
children: {write.child_paths}
---

# {title}

<!-- paperhub:generated:start -->

## Paper Links

{chr(10).join(paper_lines) or "_No paper links resolved yet._"}

## Child Sections

{chr(10).join(child_lines) or "_No child sections._"}

## Imported Material

{content.strip() or "_No imported content._"}

<!-- paperhub:generated:end -->

## User Notes
"""


def _render_imported_paper_note(
    source_root: Path, write: PlannedMarkdownWrite, topic: Topic
) -> str:
    source_path = write.source_paths[0] if write.source_paths else ""
    title = (
        write.title
        or (
            _source_title(source_root, source_path)
            if source_path
            else Path(write.target_path).stem
        )
    )
    key = write.paper_keys[0] if write.paper_keys else ""
    digest = (
        _remove_non_vault_file_references(write.body.strip())
        if write.body
        else _imported_paper_digest_blocks(source_root, write.source_paths)
    )
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
        if write.body:
            source_id = write.source_paths[0] if write.source_paths else write.target_path
            existing = _merge_imported_digest(existing, source_id, write.body)
        else:
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
