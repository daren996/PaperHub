from __future__ import annotations

from pathlib import Path

import yaml

from paperhub.models import Author, Collection, Paper, PaperHubIndex
from paperhub.obsidian import ObsidianExporter
from paperhub.store import save_index


def test_obsidian_export_writes_notes_dashboards_and_indexes(tmp_path: Path) -> None:
    paper = Paper(key="P1", title="Agent-as-a-Judge: Evaluate Agents with Agents", year=2025)
    index = PaperHubIndex(papers=[paper])

    vault = tmp_path / "vault"
    vault.mkdir()
    save_index(vault, index)
    ObsidianExporter(vault).export_all(index)

    assert (vault / "PaperIndex.md").exists()
    assert not (vault / "00 Home.md").exists()
    assert not (vault / "01 Reading Dashboard.md").exists()
    assert not (vault / "02 Paper Index.md").exists()
    assert not (vault / "02 Collection Index.md").exists()
    assert (vault / "Papers").is_dir()
    assert (vault / "Guides").is_dir()
    assert not (vault / "02 Digest Index.md").exists()
    assert not (vault / "02 Guide Index.md").exists()
    assert not (vault / "Maps").exists()


def test_paper_note_frontmatter_is_valid_yaml_and_includes_pdf_links(tmp_path: Path) -> None:
    paper = Paper(
        key="P1",
        title='One Thousand and One Pairs: A "novel" challenge',
        authors=[Author(first_name="Ada", last_name="Lovelace")],
        year=2024,
        doi="10.123/example",
        url="https://example.com/paper",
        pdf_links=["Lovelace - 2024 - Example.pdf"],
    )
    vault = tmp_path / "vault"
    vault.mkdir()

    path = ObsidianExporter(vault).write_paper(paper)
    text = path.read_text(encoding="utf-8")
    frontmatter = yaml.safe_load(text.split("---", 2)[1])

    assert frontmatter["title"] == paper.title
    assert frontmatter["authors"] == ["Ada Lovelace"]
    assert frontmatter["pdf_links"] == paper.pdf_links
    assert "## Attachments\n\n- Lovelace - 2024 - Example.pdf" in text
    assert path.name == "lovelace2024one.md"


def test_paper_note_filename_uses_citation_key(tmp_path: Path) -> None:
    paper = Paper(
        key="ABCD1234",
        title="A Very Long Paper Title That Should Not Become The Obsidian Graph Label",
        authors=[Author(last_name="Smith")],
        year=2026,
    )
    vault = tmp_path / "vault"
    vault.mkdir()

    path = ObsidianExporter(vault).write_paper(paper)

    assert path.relative_to(vault).as_posix() == "Papers/smith2026very.md"
    assert paper.title in path.read_text(encoding="utf-8")


def test_export_migrates_generated_legacy_title_slug_paper_note(tmp_path: Path) -> None:
    paper = Paper(
        key="P1",
        title="Preserve Long Legacy Filename",
        authors=[Author(last_name="Ng")],
        year=2025,
    )
    index = PaperHubIndex(papers=[paper])
    vault = tmp_path / "vault"
    vault.mkdir()
    legacy_path = vault / "Papers" / "2025-preserve-long-legacy-filename-P1.md"
    legacy_path.parent.mkdir()
    legacy_path.write_text(
        """---
type: paper
---
# Preserve Long Legacy Filename

<!-- paperhub:generated:start -->
Generated body.
<!-- paperhub:generated:end -->

## User Notes

Keep this note.
""",
        encoding="utf-8",
    )

    ObsidianExporter(vault).export_all(index)

    citation_path = vault / "Papers" / "ng2025preserve.md"
    assert citation_path.exists()
    assert "Keep this note." in citation_path.read_text(encoding="utf-8")
    assert not legacy_path.exists()


def test_obsidian_export_writes_zotero_collections_inside_paper_notes(
    tmp_path: Path,
) -> None:
    collection = Collection(key="COL1", name="Agent Benchmarks")
    paper = Paper(
        key="P1",
        title="Agent-as-a-Judge: Evaluate Agents with Agents",
        year=2025,
        collections=["COL1"],
    )
    index = PaperHubIndex(papers=[paper], collections=[collection])
    vault = tmp_path / "vault"
    vault.mkdir()

    ObsidianExporter(vault).export_all(index)

    paper_text = next((vault / "Papers").glob("*.md")).read_text(encoding="utf-8")

    assert "## Zotero Collections" in paper_text
    assert "- Agent Benchmarks (`COL1`)" in paper_text
    assert not (vault / "Collections").exists()
    assert not (vault / "02 Collection Index.md").exists()


def test_paper_note_uses_papers_surface_for_paper_level_material(tmp_path: Path) -> None:
    paper = Paper(
        key="P1",
        title="Complete Paper Contract",
        tags=["evaluation"],
        zotero_version=12,
    )
    vault = tmp_path / "vault"
    vault.mkdir()

    path = ObsidianExporter(vault).write_paper(paper)
    text = path.read_text(encoding="utf-8")

    for section in [
        "## Metadata",
        "## Zotero Sync",
        "## Citation",
        "## BibTeX",
        "## Zotero Collections",
        "## Zotero Tags",
        "## Zotero Notes",
        "## Attachments",
        "## Relations",
        "## Evidence Bundle",
        "## Digest",
        "## Summary",
        "## Method",
        "## Key Findings",
        "## Limitations",
        "## Relevance",
        "## Zotero Annotations",
        "## Key Figures",
        "## Related Papers",
        "## User Notes",
    ]:
        assert section in text
    assert "## Zotero Tags\n\n- evaluation" in text
    assert "- Zotero Version: 12" in text
    assert path.parent.name == "Papers"


def test_paper_note_export_preserves_user_notes(tmp_path: Path) -> None:
    paper = Paper(key="P1", title="Preserve Me")
    vault = tmp_path / "vault"
    vault.mkdir()
    exporter = ObsidianExporter(vault)
    path = exporter.write_paper(paper)
    path.write_text(
        path.read_text(encoding="utf-8") + "\nThis is my handwritten note.\n",
        encoding="utf-8",
    )

    exporter.write_paper(paper)

    assert "This is my handwritten note." in path.read_text(encoding="utf-8")


def test_paper_index_maps_short_filename_to_paper_title(tmp_path: Path) -> None:
    paper = Paper(
        key="P1",
        title="Efficient Learned Query Execution over Text and Tables [Technical Report]",
        authors=[Author(last_name="Chen")],
        year=2025,
    )
    index = PaperHubIndex(papers=[paper])
    vault = tmp_path / "vault"
    vault.mkdir()

    ObsidianExporter(vault).export_all(index)
    text = (vault / "PaperIndex.md").read_text(encoding="utf-8")

    assert "# PaperIndex" in text
    assert "## Library" in text
    assert "## Topic Guides" in text
    assert "## Papers" in text
    assert "| Paper File | Paper Title | Year | Zotero Key |" in text
    assert (
        "| [[Papers/chen2025efficient|chen2025efficient.md]] | Efficient Learned Query "
        "Execution over Text and Tables "
        "[Technical Report] | 2025 | `P1` |"
    ) in text
    assert "[Technical Report]" in text


def test_paper_index_escapes_markdown_table_pipes(tmp_path: Path) -> None:
    paper = Paper(key="P1", title="A | B Paper")
    index = PaperHubIndex(papers=[paper])
    vault = tmp_path / "vault"
    vault.mkdir()

    ObsidianExporter(vault).export_all(index)
    text = (vault / "PaperIndex.md").read_text(encoding="utf-8")

    assert "A \\| B Paper" in text


def test_dashboard_reports_data_quality_issues(tmp_path: Path) -> None:
    papers = [
        Paper(key="P1", title="Same Paper", url="https://example.com/paper"),
        Paper(key="P2", title="Same Paper", url="https://example.com/paper/"),
    ]
    index = PaperHubIndex(papers=papers)
    vault = tmp_path / "vault"
    vault.mkdir()

    ObsidianExporter(vault).export_all(index)
    text = (vault / "PaperIndex.md").read_text(encoding="utf-8")

    assert "## Data Quality" in text
    assert "- Missing abstracts: 2" in text
    assert "- Missing DOI values: 2" in text
    assert "- Duplicate URL groups: 1" in text
    assert "- Duplicate title groups: 1" in text
    assert "## Needs Attention\n\n- Duplicate URL groups: 1" in text
