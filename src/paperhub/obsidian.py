from __future__ import annotations

import re
import shutil
from collections import defaultdict
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape

from paperhub.config import ObsidianConfig
from paperhub.models import Collection, Paper, PaperHubIndex
from paperhub.text import (
    GENERATED_START,
    duplicate_groups,
    extract_user_notes,
    normalize_doi_value,
    normalize_title,
    normalize_url_value,
    slugify,
)

TEMPLATE_DIR = Path(__file__).resolve().parents[2] / "templates" / "obsidian"


class ObsidianExporter:
    def __init__(self, vault: Path, config: ObsidianConfig | None = None) -> None:
        self.vault = vault
        self.config = config or ObsidianConfig(vault_path=str(vault))
        self.env = Environment(
            loader=FileSystemLoader(str(TEMPLATE_DIR)),
            autoescape=select_autoescape(enabled_extensions=()),
            keep_trailing_newline=True,
        )

    def init_vault(self) -> None:
        for directory in [self.config.paper_dir, self.config.guide_dir]:
            (self.vault / directory).mkdir(parents=True, exist_ok=True)

    def export_all(self, index: PaperHubIndex) -> None:
        self.remove_stale_bulk_outputs()
        self.init_vault()
        collections_by_key = {collection.key: collection for collection in index.collections}
        filenames_by_key = paper_filename_map(index.papers)
        for paper in index.papers:
            self.write_paper(paper, collections_by_key, filename=filenames_by_key.get(paper.key))
        self.write_indexes(index, filenames_by_key)

    def remove_stale_bulk_outputs(self) -> None:
        maps_dir = self.vault / "Maps"
        if maps_dir.exists():
            shutil.rmtree(maps_dir)

        paper_dir = self.vault / self.config.paper_dir
        if not paper_dir.exists():
            return
        for path in paper_dir.glob("*.md"):
            if _is_generated_paper_note_without_user_notes(path):
                path.unlink()
        try:
            paper_dir.rmdir()
        except OSError:
            pass

    def write_paper(
        self,
        paper: Paper,
        collections_by_key: dict[str, Collection] | None = None,
        *,
        filename: str | None = None,
    ) -> Path:
        filename = filename or paper_filename(paper)
        path = self.vault / self.config.paper_dir / f"{filename}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        legacy_path = self.vault / self.config.paper_dir / f"{_legacy_paper_filename(paper)}.md"
        user_notes = _merged_user_notes(path, legacy_path)
        content = self.render_paper_note(
            paper,
            collections_by_key or {},
            user_notes=user_notes,
        )
        path.write_text(content, encoding="utf-8")
        if legacy_path != path and legacy_path.exists() and _is_generated_paper_note(legacy_path):
            legacy_path.unlink()
        return path

    def render_paper_note(
        self,
        paper: Paper,
        collections_by_key: dict[str, Collection] | None = None,
        *,
        user_notes: str = "",
    ) -> str:
        template = self.env.get_template("paper-note.md")
        content = template.render(
            frontmatter=_paper_frontmatter(paper),
            title=paper.title,
            metadata=_metadata_section(paper),
            zotero_sync=_zotero_sync_section(paper),
            citation=_citation_section(paper),
            bibtex=_bibtex_section(paper),
            collection_links=_paper_collection_links(paper, collections_by_key or {}),
            zotero_tags=_zotero_tags_section(paper),
            zotero_notes=_zotero_notes_section(paper),
            attachments=_attachments_section(paper),
            relations=_relations_section(paper),
            evidence_bundle=_evidence_bundle_section(paper),
            key_figures=_key_figures_section(paper),
            summary=paper.abstract or "_No abstract imported yet._",
            method="_Pending agent or user synthesis._",
            key_findings="_Pending agent or user synthesis._",
            limitations="_Pending agent or user synthesis._",
            relevance="_Pending agent or user synthesis._",
            digest="_Pending agent or user synthesis._",
            synthesis="_Pending agent or user synthesis._",
            annotations=_annotations_section(paper),
            related_papers="_Pending agent or user synthesis._",
            user_notes=user_notes,
        )
        return content

    def write_indexes(
        self, index: PaperHubIndex, filenames_by_key: dict[str, str] | None = None
    ) -> None:
        filenames_by_key = filenames_by_key or paper_filename_map(index.papers)
        (self.vault / "00 Home.md").write_text(_home(index), encoding="utf-8")
        (self.vault / "01 Reading Dashboard.md").write_text(_dashboard(index), encoding="utf-8")
        (self.vault / "02 Paper Index.md").write_text(
            _paper_index(index, filenames_by_key), encoding="utf-8"
        )


def paper_filename(paper: Paper) -> str:
    return citation_key_filename(paper)


def paper_filename_map(papers: list[Paper]) -> dict[str, str]:
    base_groups: dict[str, list[Paper]] = defaultdict(list)
    for paper in papers:
        base_groups[paper_filename(paper)].append(paper)

    filenames: dict[str, str] = {}
    for base, group in base_groups.items():
        if len(group) == 1:
            filenames[group[0].key] = base
            continue
        for paper in sorted(group, key=lambda candidate: candidate.key):
            suffix = paper_key_filename(paper.key).lower()[-8:]
            filenames[paper.key] = f"{base}-{suffix}"
    return filenames


def citation_key_filename(paper: Paper) -> str:
    author = _citation_author_part(paper)
    year = str(paper.year) if paper.year else ""
    first_word = _citation_title_word(paper.title)
    if not author and not year:
        return paper_key_filename(paper.key)
    return paper_key_filename(f"{author}{year}{first_word}".lower() or paper.key)


def paper_key_filename(key: str) -> str:
    filename = re.sub(r"[^A-Za-z0-9._-]+", "-", key.strip())
    filename = filename.strip(".-")
    return filename[:64] or "untitled"


def _citation_author_part(paper: Paper) -> str:
    if not paper.authors:
        return ""
    author = paper.authors[0]
    name = author.last_name or author.name or author.display
    if not name:
        return ""
    token = re.split(r"\s+", name.strip())[-1]
    token = re.sub(r"[^A-Za-z0-9]+", "", token)
    return token


def _citation_title_word(title: str) -> str:
    stopwords = {"a", "an", "the"}
    for token in re.findall(r"[A-Za-z0-9]+", title):
        lowered = token.lower()
        if lowered not in stopwords:
            return lowered
    return "untitled"


def _legacy_paper_filename(paper: Paper) -> str:
    year = f"{paper.year}-" if paper.year else ""
    return f"{year}{slugify(paper.title)}-{paper.key}"


def _paper_frontmatter(paper: Paper) -> str:
    data = {
        "type": "paper",
        "title": paper.title,
        "authors": [author.display for author in paper.authors if author.display],
        "year": paper.year,
        "venue": paper.venue,
        "doi": paper.doi,
        "url": paper.url,
        "zotero_key": paper.key,
        "citation_key": paper.citation_key,
        "item_type": paper.item_type,
        "reading_status": paper.reading_status,
        "tags": paper.tags,
        "collections": paper.collections,
        "pdf_links": paper.pdf_links,
        "topics": paper.topics,
        "evidence_bundle_path": paper.evidence_bundle_path,
    }
    payload = yaml.safe_dump(data, sort_keys=False, allow_unicode=True)
    return f"---\n{payload}---"


def _metadata_section(paper: Paper) -> str:
    rows = [
        ("Authors", paper.author_text),
        ("Year", str(paper.year) if paper.year else ""),
        ("Venue", paper.venue),
        ("DOI", paper.doi),
        ("URL", paper.url),
        ("Zotero Key", paper.key),
        ("Citation Key", paper.citation_key),
        ("Item Type", paper.item_type),
    ]
    lines = [f"- {label}: {value}" for label, value in rows if value]
    return "\n".join(lines)


def _zotero_sync_section(paper: Paper) -> str:
    lines = [f"- Zotero Key: `{paper.key}`"]
    if paper.zotero_version is not None:
        lines.append(f"- Zotero Version: {paper.zotero_version}")
    else:
        lines.append("- Zotero Version: _Not imported yet._")
    return "\n".join(lines)


def _citation_section(paper: Paper) -> str:
    lines = []
    if paper.author_text or paper.year:
        year = f" ({paper.year})" if paper.year else ""
        lines.append(f"- Citation: {paper.author_text}{year}. {paper.title}.")
    if paper.citation_key:
        lines.append(f"- Citation Key: `{paper.citation_key}`")
    if paper.doi:
        lines.append(f"- DOI: {paper.doi}")
    if paper.url:
        lines.append(f"- URL: {paper.url}")
    return "\n".join(lines) if lines else "_No citation metadata imported yet._"


def _bibtex_section(paper: Paper) -> str:
    if not paper.bibtex:
        return "_No BibTeX imported yet._"
    return f"```bibtex\n{paper.bibtex.strip()}\n```"


def _paper_collection_links(paper: Paper, collections_by_key: dict[str, Collection]) -> str:
    links = []
    for key in paper.collections:
        collection = collections_by_key.get(key)
        if collection:
            links.append(f"- {collection.name} (`{collection.key}`)")
        else:
            links.append(f"- Zotero collection `{key}`")
    return "\n".join(links) if links else "_None yet._"


def _zotero_tags_section(paper: Paper) -> str:
    if not paper.tags:
        return "_None yet._"
    return "\n".join(f"- {tag}" for tag in paper.tags)


def _attachments_section(paper: Paper) -> str:
    if not paper.attachments and not paper.pdf_links:
        return "_No PDF link imported yet._"
    lines = []
    for attachment in paper.attachments:
        label = attachment.title or attachment.filename or attachment.key or "Attachment"
        details = []
        if attachment.content_type:
            details.append(attachment.content_type)
        if attachment.link:
            details.append(attachment.link)
        suffix = f" - {'; '.join(details)}" if details else ""
        lines.append(f"- {label}{suffix}")
    for link in paper.pdf_links:
        if not any(link and link in line for line in lines):
            lines.append(f"- {link}")
    return "\n".join(lines)


def _zotero_notes_section(paper: Paper) -> str:
    if not paper.zotero_notes:
        return "_No Zotero notes imported yet._"
    return "\n\n".join(f"- {note}" for note in paper.zotero_notes if note.strip())


def _relations_section(paper: Paper) -> str:
    if not paper.relations:
        return "_No Zotero relations imported yet._"
    lines = []
    for key, value in sorted(paper.relations.items()):
        lines.append(f"- {key}: {value}")
    return "\n".join(lines)


def _evidence_bundle_section(paper: Paper) -> str:
    if not paper.evidence_bundle_path:
        return "_No evidence bundle generated yet. Run `paperhub paper enrich`._"
    return (
        f"- Bundle: `{paper.evidence_bundle_path}`\n"
        "- Status: scaffolded evidence, ready for agent writing."
    )


def _key_figures_section(paper: Paper) -> str:
    if not paper.figures:
        return "_No figure placeholders generated yet._"
    blocks = []
    for figure in paper.figures:
        title = f"{figure.label} {figure.caption}".strip()
        lines = [
            f"> [!figure] {title}",
            f"> Suggested location: {figure.suggested_location or '_Pending review._'}",
            f"> Why it matters: {figure.why_it_matters or '_Pending review._'}",
            f"> Status: {figure.status}",
        ]
        if figure.page_label:
            lines.insert(1, f"> Page: {figure.page_label}")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def _existing_user_notes(path: Path) -> str:
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8")
    return extract_user_notes(text)


def _merged_user_notes(primary_path: Path, legacy_path: Path) -> str:
    notes = []
    for path in [primary_path, legacy_path]:
        note = _existing_user_notes(path)
        if note and note not in notes:
            notes.append(note)
    return "\n\n".join(notes)


def _is_generated_paper_note_without_user_notes(path: Path) -> bool:
    return _is_generated_paper_note(path) and not _existing_user_notes(path)


def _is_generated_paper_note(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    frontmatter = text.split("---", 2)[1] if text.startswith("---") and "---" in text[3:] else ""
    return "type: paper" in frontmatter and GENERATED_START in text


def _annotations_section(paper: Paper) -> str:
    if not paper.annotations:
        return "_No annotations imported yet._"
    lines = []
    for annotation in paper.annotations:
        body = annotation.text or annotation.comment
        suffix = f" (p. {annotation.page_label})" if annotation.page_label else ""
        lines.append(f"- {body}{suffix}")
    return "\n".join(lines)


def _home(index: PaperHubIndex) -> str:
    return f"""# PaperHub

<!-- paperhub:generated:start -->

- Papers: {len(index.papers)}
- Guides: {len(index.guides)}

## Navigation

- [[01 Reading Dashboard]]
- [[02 Paper Index]]

<!-- paperhub:generated:end -->
"""


def _dashboard(index: PaperHubIndex) -> str:
    missing_abstracts = [paper for paper in index.papers if not paper.abstract]
    missing_doi = [paper for paper in index.papers if not paper.doi]
    missing_url = [paper for paper in index.papers if not paper.url]
    pdf_count = sum(1 for paper in index.papers if paper.pdf_links)
    duplicate_titles = duplicate_groups(index.papers, lambda paper: normalize_title(paper.title))
    duplicate_dois = duplicate_groups(index.papers, lambda paper: normalize_doi_value(paper.doi))
    duplicate_urls = duplicate_groups(index.papers, lambda paper: normalize_url_value(paper.url))
    attention = []
    if duplicate_dois:
        attention.append(f"- Duplicate DOI groups: {len(duplicate_dois)}")
    if duplicate_urls:
        attention.append(f"- Duplicate URL groups: {len(duplicate_urls)}")
    if duplicate_titles:
        attention.append(f"- Duplicate title groups: {len(duplicate_titles)}")
    if missing_abstracts:
        attention.append(f"- Papers missing abstracts: {len(missing_abstracts)}")
    if missing_doi:
        attention.append(f"- Papers missing DOI values: {len(missing_doi)}")
    if missing_url:
        attention.append(f"- Papers missing URL values: {len(missing_url)}")
    return f"""# Reading Dashboard

<!-- paperhub:generated:start -->

## Library

- Zotero papers: {len(index.papers)}
- Papers with PDF links: {pdf_count}

## Data Quality

- Missing abstracts: {len(missing_abstracts)}
- Missing DOI values: {len(missing_doi)}
- Missing URL values: {len(missing_url)}
- Duplicate DOI groups: {len(duplicate_dois)}
- Duplicate URL groups: {len(duplicate_urls)}
- Duplicate title groups: {len(duplicate_titles)}

## Needs Attention

{chr(10).join(attention) or "- None"}

<!-- paperhub:generated:end -->
"""


def _paper_index(index: PaperHubIndex, filenames_by_key: dict[str, str]) -> str:
    lines = [
        "# Paper Index",
        "",
        "<!-- paperhub:generated:start -->",
        "",
        "| Paper File | Paper Title | Year | Zotero Key |",
        "| --- | --- | --- | --- |",
    ]
    for paper in index.papers:
        stem = filenames_by_key.get(paper.key, paper_filename(paper))
        filename = f"{stem}.md"
        link = f"[[Papers/{stem}|{filename}]]"
        year = str(paper.year) if paper.year else ""
        lines.append(
            "| "
            + " | ".join(
                [
                    link,
                    _markdown_table_cell(paper.title),
                    year,
                    f"`{paper.key}`",
                ]
            )
            + " |"
        )
    lines.extend(["", "<!-- paperhub:generated:end -->", ""])
    return "\n".join(lines)


def _markdown_table_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ").strip()
