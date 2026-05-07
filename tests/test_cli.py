from __future__ import annotations

import json

from typer.testing import CliRunner

from paperhub.cli import app
from paperhub.models import Author, Paper, PaperHubIndex
from paperhub.store import load_index, save_index


def test_init_defaults_to_paperhub_vault_env(tmp_path, monkeypatch) -> None:
    vault = tmp_path / "ResearchVault"
    monkeypatch.setenv("PAPERHUB_VAULT", str(vault))
    result = CliRunner().invoke(app, ["init"])

    assert result.exit_code == 0
    assert (vault / ".paperhub" / "paperhub.yaml").exists()
    assert (vault / "Papers").is_dir()
    assert (vault / "Guides").is_dir()
    assert not (vault / "Collections").exists()


def test_obsidian_connect_defaults_to_paperhub_vault_env(tmp_path, monkeypatch) -> None:
    vault = tmp_path / "ResearchVault"
    monkeypatch.setenv("PAPERHUB_VAULT", str(vault))
    result = CliRunner().invoke(app, ["obsidian", "connect"])

    assert result.exit_code == 0
    assert (vault / ".paperhub" / "paperhub.yaml").exists()
    assert (vault / "Papers").is_dir()
    assert (vault / "Guides").is_dir()
    assert not (vault / "Collections").exists()
    assert not (vault / "Maps").exists()


def test_top_level_help_explains_vault_env() -> None:
    result = CliRunner().invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "PAPERHUB_VAULT" in result.output
    assert "Zotero" in result.output


def test_help_command_shows_top_level_help() -> None:
    result = CliRunner().invoke(app, ["help"])

    assert result.exit_code == 0
    assert "PAPERHUB_VAULT" in result.output
    assert "Commands" in result.output


def test_import_markdown_dry_run_plans_guides_without_writing(tmp_path, monkeypatch) -> None:
    vault = tmp_path / "ResearchVault"
    source = tmp_path / "source"
    source.mkdir()
    (source / "guide.md").write_text(
        "# LLM as a Judge Guide\n\n## Overview\n\nA survey guide.\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("PAPERHUB_VAULT", str(vault))
    CliRunner().invoke(app, ["init"])

    result = CliRunner().invoke(
        app,
        [
            "import",
            "markdown",
            str(source),
            "--topic",
            "LLM as a Judge",
            "--dry-run",
        ],
    )

    assert result.exit_code == 0
    assert "Guides/llm-as-a-judge/llm-as-a-judge.md" in result.output
    assert not (vault / "Guides" / "llm-as-a-judge").exists()
    assert not (vault / "Collections").exists()
    assert not (vault / "README.md").exists()


def test_import_markdown_defaults_to_plan_without_writing(tmp_path, monkeypatch) -> None:
    vault = tmp_path / "ResearchVault"
    source = tmp_path / "source"
    source.mkdir()
    (source / "guide.md").write_text(
        "# LLM as a Judge Guide\n\n## Overview\n\nA survey guide.\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("PAPERHUB_VAULT", str(vault))
    CliRunner().invoke(app, ["init"])

    result = CliRunner().invoke(
        app,
        ["import", "markdown", str(source), "--topic", "LLM as a Judge"],
    )

    assert result.exit_code == 0
    assert "Import plan complete. No files were written." in result.output
    assert "Guides/llm-as-a-judge/llm-as-a-judge.md" in result.output
    assert not (vault / "Guides" / "llm-as-a-judge").exists()


def test_import_markdown_writes_only_papers_and_guides_surfaces(tmp_path, monkeypatch) -> None:
    vault = tmp_path / "ResearchVault"
    source = tmp_path / "source"
    source.mkdir()
    (source / "guide.md").write_text(
        "# LLM as a Judge Guide\n\n## Overview\n\nA survey guide.\n",
        encoding="utf-8",
    )
    (source / "bias.md").write_text(
        "# Bias and Reliability\n\n## Evidence\n\nThis guide section discusses PAPER1.\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("PAPERHUB_VAULT", str(vault))
    save_index(
        vault,
        PaperHubIndex(
            papers=[
                Paper(
                    key="PAPER1",
                    title="Judge Bias",
                    authors=[Author(last_name="Smith")],
                    year=2024,
                )
            ]
        ),
    )
    CliRunner().invoke(app, ["init"])

    result = CliRunner().invoke(
        app,
        ["import", "markdown", str(source), "--topic", "LLM as a Judge", "--apply"],
    )

    assert result.exit_code == 0
    main_guide = vault / "Guides" / "llm-as-a-judge" / "llm-as-a-judge.md"
    section = vault / "Guides" / "llm-as-a-judge" / "sections" / "bias-and-reliability.md"
    assert main_guide.exists()
    assert section.exists()
    assert "[[Papers/smith2024judge|PAPER1]]" in section.read_text(encoding="utf-8")
    relationship_manifest = (
        vault / ".paperhub" / "relationships" / "guide-section-cites-paper.json"
    )
    manifest = json.loads(relationship_manifest.read_text(encoding="utf-8"))
    assert manifest["relationship_type"] == "guide-section-cites-paper"
    assert manifest["relationships"][0]["paper_path"] == "Papers/smith2024judge.md"
    root_names = {path.name for path in vault.iterdir() if path.name != ".paperhub"}
    assert root_names == {
        "00 Home.md",
        "01 Reading Dashboard.md",
        "02 Paper Index.md",
        "README.md",
        "Papers",
        "Guides",
    }
    readme = (vault / "README.md").read_text(encoding="utf-8")
    assert "[[Guides/llm-as-a-judge/llm-as-a-judge|LLM as a Judge]]" in readme
    assert not (vault / "Obsidian").exists()
    assert not (vault / "PaperHub").exists()


def test_import_markdown_accepts_single_file_source(tmp_path, monkeypatch) -> None:
    vault = tmp_path / "ResearchVault"
    source_dir = tmp_path / "source"
    paper_dir = source_dir / "papers"
    paper_dir.mkdir(parents=True)
    source = source_dir / "README.md"
    source.write_text(
        "# LLM as a Judge Guide\n\n## Overview\n\nSingle file guide.\n\n"
        "[Missing Paper](papers/missing-paper.md)\n",
        encoding="utf-8",
    )
    (paper_dir / "missing-paper.md").write_text(
        "# Missing Paper\n\n## Summary\n\nPaper linked from the single imported guide file.\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("PAPERHUB_VAULT", str(vault))
    CliRunner().invoke(app, ["init"])

    result = CliRunner().invoke(
        app,
        ["import", "markdown", str(source), "--topic", "LLM as a Judge", "--apply"],
    )

    assert result.exit_code == 0
    main_guide = vault / "Guides" / "llm-as-a-judge" / "llm-as-a-judge.md"
    assert "Single file guide." in main_guide.read_text(encoding="utf-8")
    staged_papers = [
        paper for paper in load_index(vault).papers if paper.key.startswith("IMPORTED-")
    ]
    assert len(staged_papers) == 1
    staged_paper = staged_papers[0]
    assert staged_paper.title == "Missing Paper"
    assert (vault / "Papers" / f"{staged_paper.key}.md").exists()
    assert f"[[Papers/{staged_paper.key}|{staged_paper.key}]]" in main_guide.read_text(
        encoding="utf-8"
    )


def test_import_markdown_strips_references_to_files_outside_vault(
    tmp_path, monkeypatch
) -> None:
    vault = tmp_path / "ResearchVault"
    source = tmp_path / "source"
    paper_dir = source / "papers"
    paper_dir.mkdir(parents=True)
    outside = tmp_path / "outside.md"
    outside.write_text("# Outside\n", encoding="utf-8")
    (source / "guide.md").write_text(
        "# LLM as a Judge Guide\n\n"
        "Keep [Paper](papers/missing.md), [Web](https://example.com/paper), "
        "[outside](../outside.md), [absolute](/Users/someone/file.pdf), "
        "![local figure](assets/figure.png), and /tmp/source-data.pdf.\n",
        encoding="utf-8",
    )
    (source / "section.md").write_text(
        "# Bias Section\n\n## Evidence\n\n"
        "This section cites PAPER1 and [local support](support.pdf).\n",
        encoding="utf-8",
    )
    (paper_dir / "missing.md").write_text(
        "# Missing Paper\n\n## Summary\n\n"
        "Digest with [supplement](../supplement.pdf), "
        "<img src=\"figures/chart.png\">, and [Web](https://example.com/supplement).",
        encoding="utf-8",
    )
    monkeypatch.setenv("PAPERHUB_VAULT", str(vault))
    save_index(
        vault,
        PaperHubIndex(
            papers=[
                Paper(
                    key="PAPER1",
                    title="Judge Bias",
                    authors=[Author(last_name="Smith")],
                    year=2024,
                )
            ]
        ),
    )
    runner = CliRunner()
    runner.invoke(app, ["init"])

    result = runner.invoke(
        app,
        ["import", "markdown", str(source), "--topic", "LLM as a Judge", "--apply"],
    )

    assert result.exit_code == 0
    generated_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in [
            vault / "Guides" / "llm-as-a-judge" / "llm-as-a-judge.md",
            vault / "Guides" / "llm-as-a-judge" / "sections" / "bias-section.md",
            next((vault / "Papers").glob("IMPORTED-*.md")),
        ]
    )
    assert "[[Papers/IMPORTED-" in generated_text
    assert "[Web](https://example.com/paper)" in generated_text
    assert "[Web](https://example.com/supplement)" in generated_text
    for forbidden in [
        "../outside.md",
        "/Users/someone/file.pdf",
        "assets/figure.png",
        "/tmp/source-data.pdf",
        "support.pdf",
        "../supplement.pdf",
        "figures/chart.png",
        "source_paths:",
        "guide.md",
        "section.md",
        "papers/missing.md",
    ]:
        assert forbidden not in generated_text
    index = load_index(vault)
    assert index.guides[0].sections[0].source_paths == []
    relationship_manifest = json.loads(
        (
            vault / ".paperhub" / "relationships" / "guide-section-cites-paper.json"
        ).read_text(encoding="utf-8")
    )
    assert relationship_manifest["relationships"][0]["source_paths"] == []


def test_import_markdown_normalizes_heterogeneous_markdown_sources(
    tmp_path, monkeypatch
) -> None:
    vault = tmp_path / "ResearchVault"
    source = tmp_path / "source"
    (source / "modules").mkdir(parents=True)
    (source / "notes").mkdir()
    (source / "papers").mkdir()
    (source / "overview.md").write_text(
        "# Topic Survey\n\n## Overview\n\nMain survey material.\n",
        encoding="utf-8",
    )
    (source / "extra-guide.md").write_text(
        "# Extra Guide\n\n## Open Questions\n\nSecond guide source.\n",
        encoding="utf-8",
    )
    (source / "modules" / "intro.md").write_text(
        "# Intro\n\n## Evidence\n\nThis section cites PAPER1.\n",
        encoding="utf-8",
    )
    (source / "notes" / "intro.md").write_text(
        "# Intro\n\n## Evidence\n\nThis section cites DOI 10.2222/bias.\n",
        encoding="utf-8",
    )
    (source / "papers" / "judge-bias.md").write_text(
        "# Judge Bias\n\nDOI: 10.111/judge-bias\n\n## Method\n\nPaper digest content.\n",
        encoding="utf-8",
    )
    (source / "loose.md").write_text(
        "A free-form support note without headings.",
        encoding="utf-8",
    )
    (source / "mixed.md").write_text(
        "# Mixed Source\n\nDOI: 10.111/judge-bias\n\n## Overview\n\nGuide and digest markers.",
        encoding="utf-8",
    )
    (source / "empty.md").write_text("", encoding="utf-8")
    monkeypatch.setenv("PAPERHUB_VAULT", str(vault))
    save_index(
        vault,
        PaperHubIndex(
            papers=[
                Paper(
                    key="PAPER1",
                    title="Anchor Paper",
                    authors=[Author(last_name="Smith")],
                    year=2024,
                ),
                Paper(
                    key="PAPER2",
                    title="DOI Paper",
                    authors=[Author(last_name="Jones")],
                    year=2023,
                    doi="10.2222/bias",
                ),
                Paper(
                    key="PAPER3",
                    title="Judge Bias",
                    authors=[Author(last_name="Lee")],
                    year=2022,
                    doi="10.111/judge-bias",
                ),
            ]
        ),
    )
    runner = CliRunner()
    runner.invoke(app, ["init"])

    result = runner.invoke(
        app,
        ["import", "markdown", str(source), "--topic", "LLM as a Judge", "--apply"],
    )

    assert result.exit_code == 0
    root_names = {path.name for path in vault.iterdir() if path.name != ".paperhub"}
    assert root_names == {
        "00 Home.md",
        "01 Reading Dashboard.md",
        "02 Paper Index.md",
        "README.md",
        "Papers",
        "Guides",
    }
    main_guide = vault / "Guides" / "llm-as-a-judge" / "llm-as-a-judge.md"
    main_text = main_guide.read_text(encoding="utf-8")
    assert "Main survey material." in main_text
    assert "Second guide source." in main_text
    assert "ambiguous-classification" in main_text
    assert "unknown-file" in main_text
    section_paths = sorted(
        path.relative_to(vault).as_posix()
        for path in (vault / "Guides" / "llm-as-a-judge" / "sections").glob("*.md")
    )
    assert section_paths == [
        "Guides/llm-as-a-judge/sections/intro-76126540.md",
        "Guides/llm-as-a-judge/sections/intro.md",
        "Guides/llm-as-a-judge/sections/loose.md",
    ]
    assert "[[Papers/smith2024anchor|PAPER1]]" in (
        vault / "Guides" / "llm-as-a-judge" / "sections" / "intro.md"
    ).read_text(encoding="utf-8")
    assert "[[Papers/jones2023doi|PAPER2]]" in (
        vault / "Guides" / "llm-as-a-judge" / "sections" / "intro-76126540.md"
    ).read_text(encoding="utf-8")
    paper_text = (vault / "Papers" / "lee2022judge.md").read_text(encoding="utf-8")
    assert "Paper digest content." in paper_text
    relationship_manifest = (
        vault / ".paperhub" / "relationships" / "guide-section-cites-paper.json"
    )
    manifest = json.loads(relationship_manifest.read_text(encoding="utf-8"))
    assert {
        (relationship["guide_section_path"], relationship["paper_path"])
        for relationship in manifest["relationships"]
    } >= {
        ("Guides/llm-as-a-judge/sections/intro.md", "Papers/smith2024anchor.md"),
        ("Guides/llm-as-a-judge/sections/intro-76126540.md", "Papers/jones2023doi.md"),
    }
    assert not (vault / "source").exists()
    assert not (vault / "Collections").exists()


def test_import_markdown_does_not_turn_paper_catalog_files_into_sections(
    tmp_path, monkeypatch
) -> None:
    vault = tmp_path / "ResearchVault"
    source = tmp_path / "source"
    paper_catalog = source / "papers" / "readme" / "4-meta-evaluation"
    paper_catalog.mkdir(parents=True)
    (source / "reading-guide.md").write_text(
        "# LLM as a Judge\n\n## Overview\n\nUse the curated reading guide.\n",
        encoding="utf-8",
    )
    (source / "conference-list.md").write_text(
        "# Conference List\n\n## Oral Papers\n\nTop-level curated list.\n\n"
        "## Poster Papers\n\nMore papers.",
        encoding="utf-8",
    )
    (paper_catalog / "001-paper-note.md").write_text(
        "# Unmatched Paper Note\n\n## Summary\n\nPaper-level digest material.\n\n"
        "## Method\n\nDetails.",
        encoding="utf-8",
    )
    monkeypatch.setenv("PAPERHUB_VAULT", str(vault))
    runner = CliRunner()
    runner.invoke(app, ["init"])

    result = runner.invoke(
        app,
        ["import", "markdown", str(source), "--topic", "LLM as a Judge", "--apply"],
    )

    assert result.exit_code == 0
    assert not (vault / "Guides" / "llm-as-a-judge" / "sections").exists()
    staged_papers = [
        paper for paper in load_index(vault).papers if paper.key.startswith("IMPORTED-")
    ]
    assert len(staged_papers) == 1
    staged_paper = staged_papers[0]
    assert staged_paper.title == "Unmatched Paper Note"
    assert (vault / "Papers" / f"{staged_paper.key}.md").exists()
    main_guide = vault / "Guides" / "llm-as-a-judge" / "llm-as-a-judge.md"
    main_text = main_guide.read_text(encoding="utf-8")
    assert "Use the curated reading guide." in main_text
    assert "Top-level curated list." in main_text
    assert "Import completed with review items." in result.output


def test_import_markdown_merges_duplicate_staged_paper_titles(tmp_path, monkeypatch) -> None:
    vault = tmp_path / "ResearchVault"
    source = tmp_path / "source"
    paper_catalog = source / "papers" / "readme"
    paper_catalog.mkdir(parents=True)
    (source / "reading-guide.md").write_text(
        "# LLM as a Judge\n\n[Paper](papers/readme/paper.md)\n",
        encoding="utf-8",
    )
    (paper_catalog / "paper.md").write_text(
        "# Shared Missing Paper\n\n## Summary\n\nEnglish digest.",
        encoding="utf-8",
    )
    (paper_catalog / "paper_zh.md").write_text(
        "# Shared Missing Paper\n\n## Summary\n\nChinese digest.",
        encoding="utf-8",
    )
    monkeypatch.setenv("PAPERHUB_VAULT", str(vault))
    runner = CliRunner()
    runner.invoke(app, ["init"])

    result = runner.invoke(
        app,
        ["import", "markdown", str(source), "--topic", "LLM as a Judge", "--apply"],
    )

    assert result.exit_code == 0
    staged_papers = [
        paper for paper in load_index(vault).papers if paper.key.startswith("IMPORTED-")
    ]
    assert len(staged_papers) == 1
    paper_note = vault / "Papers" / f"{staged_papers[0].key}.md"
    paper_text = paper_note.read_text(encoding="utf-8")
    assert "English digest." in paper_text
    assert "Chinese digest." in paper_text
    main_text = (vault / "Guides" / "llm-as-a-judge" / "llm-as-a-judge.md").read_text(
        encoding="utf-8"
    )
    assert main_text.count(f"[[Papers/{staged_papers[0].key}|Paper]]") == 1

    second = runner.invoke(
        app,
        ["import", "markdown", str(source), "--topic", "LLM as a Judge", "--apply"],
    )

    assert second.exit_code == 0
    paper_text = paper_note.read_text(encoding="utf-8")
    assert paper_text.count("English digest.") == 1
    assert paper_text.count("Chinese digest.") == 1


def test_import_markdown_removes_stale_generated_sections_on_reimport(
    tmp_path, monkeypatch
) -> None:
    vault = tmp_path / "ResearchVault"
    source = tmp_path / "source"
    source.mkdir()
    (source / "guide.md").write_text(
        "# LLM as a Judge\n\n## Overview\n\nMain guide.\n",
        encoding="utf-8",
    )
    (source / "section.md").write_text(
        "# Temporary Section\n\n## Evidence\n\nThis section cites PAPER1.\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("PAPERHUB_VAULT", str(vault))
    save_index(
        vault,
        PaperHubIndex(
            papers=[
                Paper(
                    key="PAPER1",
                    title="Anchor Paper",
                    authors=[Author(last_name="Smith")],
                    year=2024,
                )
            ]
        ),
    )
    runner = CliRunner()
    runner.invoke(app, ["init"])
    first = runner.invoke(
        app,
        ["import", "markdown", str(source), "--topic", "LLM as a Judge", "--apply"],
    )
    assert first.exit_code == 0
    section_path = (
        vault / "Guides" / "llm-as-a-judge" / "sections" / "temporary-section.md"
    )
    assert section_path.exists()

    (source / "section.md").unlink()
    second = runner.invoke(
        app,
        ["import", "markdown", str(source), "--topic", "LLM as a Judge", "--apply"],
    )

    assert second.exit_code == 0
    assert not section_path.exists()


def test_zotero_push_staged_defaults_to_dry_run(tmp_path, monkeypatch) -> None:
    vault = tmp_path / "ResearchVault"
    monkeypatch.setenv("PAPERHUB_VAULT", str(vault))
    runner = CliRunner()
    runner.invoke(app, ["init"])
    save_index(
        vault,
        PaperHubIndex(
            papers=[
                Paper(
                    key="IMPORTED-123",
                    title="Missing Paper",
                    authors=[Author(last_name="Lovelace")],
                    year=2025,
                    topics=["LLM as a Judge"],
                )
            ]
        ),
    )

    result = runner.invoke(app, ["zotero", "push-staged"])

    assert result.exit_code == 0
    assert "IMPORTED-123" in result.output
    assert "Dry run only" in result.output
    assert not (vault / ".paperhub" / "zotero-push-staged.json").exists()
