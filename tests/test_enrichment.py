from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

import paperhub.evidence as evidence
from paperhub.cli import app
from paperhub.models import Attachment, Author, EvidenceTextExcerpt, Paper, PaperHubIndex
from paperhub.obsidian import ObsidianExporter
from paperhub.store import load_index, save_index


def test_paper_enrich_quick_generates_metadata_bundle_and_note(
    tmp_path: Path, monkeypatch
) -> None:
    vault = tmp_path / "ResearchVault"
    paper = Paper(
        key="P1",
        title="Judge Bias",
        authors=[Author(last_name="Smith")],
        year=2024,
        abstract="A paper about evaluation bias.",
    )
    save_index(vault, PaperHubIndex(papers=[paper]))
    monkeypatch.setenv("PAPERHUB_VAULT", str(vault))
    runner = CliRunner()
    runner.invoke(app, ["init"])

    result = runner.invoke(app, ["paper", "enrich", "P1", "--mode", "quick"])

    assert result.exit_code == 0
    assert "metadata-only" in result.output
    bundle_path = vault / ".paperhub" / "evidence" / "smith2024judge.json"
    assert bundle_path.exists()
    note_text = (vault / "Papers" / "smith2024judge.md").read_text(encoding="utf-8")
    assert "## Evidence Bundle" in note_text
    assert "` .paperhub/evidence" not in note_text
    assert ".paperhub/evidence/smith2024judge.json" in note_text
    indexed = load_index(vault).papers[0]
    assert indexed.evidence_bundle_path == ".paperhub/evidence/smith2024judge.json"
    assert indexed.reading_status == "summarized"


def test_paper_enrich_deep_fails_without_pdf_text_or_annotations(
    tmp_path: Path, monkeypatch
) -> None:
    vault = tmp_path / "ResearchVault"
    paper = Paper(
        key="P1",
        title="Judge Bias",
        authors=[Author(last_name="Smith")],
        year=2024,
    )
    save_index(vault, PaperHubIndex(papers=[paper]))
    monkeypatch.setenv("PAPERHUB_VAULT", str(vault))
    runner = CliRunner()
    runner.invoke(app, ["init"])

    result = runner.invoke(app, ["paper", "enrich", "P1", "--mode", "deep"])

    assert result.exit_code == 1
    assert "Deep enrichment requires PDF text" in result.output
    assert not (vault / ".paperhub" / "evidence" / "smith2024judge.json").exists()


def test_paper_enrich_deep_uses_pdf_caption_placeholders(
    tmp_path: Path, monkeypatch
) -> None:
    vault = tmp_path / "ResearchVault"
    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"%PDF fake for mocked extractor")
    paper = Paper(
        key="P1",
        title="Judge Bias",
        authors=[Author(last_name="Smith")],
        year=2024,
        attachments=[
            Attachment(
                key="A1",
                title="paper.pdf",
                content_type="application/pdf",
                path=str(pdf_path),
            )
        ],
    )
    save_index(vault, PaperHubIndex(papers=[paper]))
    monkeypatch.setenv("PAPERHUB_VAULT", str(vault))

    def fake_extract(path: Path) -> list[EvidenceTextExcerpt]:
        return [
            EvidenceTextExcerpt(
                source=str(path),
                page_label="2",
                text="Fig. 2 Method overview shows the pipeline and main execution flow.",
            )
        ]

    monkeypatch.setattr(evidence, "_extract_pdf_text", fake_extract)
    runner = CliRunner()
    runner.invoke(app, ["init"])

    result = runner.invoke(app, ["paper", "enrich", "smith2024judge", "--mode", "deep"])

    assert result.exit_code == 0
    note_text = (vault / "Papers" / "smith2024judge.md").read_text(encoding="utf-8")
    assert (
        "> [!figure] Fig. 2 Method overview shows the pipeline and main execution flow."
        in note_text
    )
    assert "> Status: placeholder" in note_text
    assert load_index(vault).papers[0].reading_status == "synthesized"


def test_paper_enrich_preserves_user_notes(tmp_path: Path, monkeypatch) -> None:
    vault = tmp_path / "ResearchVault"
    paper = Paper(
        key="P1",
        title="Preserve User Notes",
        authors=[Author(last_name="Ng")],
        year=2025,
    )
    save_index(vault, PaperHubIndex(papers=[paper]))
    monkeypatch.setenv("PAPERHUB_VAULT", str(vault))
    runner = CliRunner()
    runner.invoke(app, ["init"])
    note_path = ObsidianExporter(vault).write_paper(paper)
    note_path.write_text(
        note_path.read_text(encoding="utf-8") + "\nKeep this handwritten note.\n",
        encoding="utf-8",
    )

    result = runner.invoke(app, ["paper", "enrich", "P1", "--mode", "quick"])

    assert result.exit_code == 0
    assert "Keep this handwritten note." in note_path.read_text(encoding="utf-8")
