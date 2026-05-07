from __future__ import annotations

import pytest
from pydantic import ValidationError

from paperhub.models import (
    Guide,
    GuideSection,
    GuideSectionCitesPaper,
    MarkdownImportPlan,
    MarkdownImportReport,
    MarkdownImportReviewItem,
    MarkdownSourceFile,
    PlannedMarkdownWrite,
    Topic,
)


def test_topic_slug_owns_guides_folder_without_topic_surface() -> None:
    topic = Topic(name="LLMs as Judges")

    assert topic.slug == "llms-as-judges"
    assert topic.guide_folder == "Guides/llms-as-judges"
    assert "Topic" not in topic.guide_folder


def test_guide_defaults_to_main_markdown_file_under_topic_folder() -> None:
    section = GuideSection(title="Bias and Reliability", paper_keys=["PAPER1"])
    guide = Guide(topic=Topic(name="LLM as a Judge"), sections=[section])

    assert guide.folder_path == "Guides/llm-as-a-judge"
    assert guide.main_path == "Guides/llm-as-a-judge/llm-as-a-judge.md"
    assert guide.sections[0].filename == "bias-and-reliability.md"
    assert guide.sections[0].paper_keys == ["PAPER1"]


def test_guide_main_file_cannot_escape_topic_folder() -> None:
    with pytest.raises(ValidationError):
        Guide(topic=Topic(name="LLM as a Judge"), main_filename="../Overview.md")


def test_markdown_import_plan_accepts_heterogeneous_sources_and_review_items() -> None:
    topic = Topic(name="LLM as a Judge")
    review_item = MarkdownImportReviewItem(
        category="ambiguous-classification",
        source_path="notes/mixed.md",
        message="File contains both survey prose and paper digest sections.",
    )
    plan = MarkdownImportPlan(
        source_path="/path/to/research-notes",
        topic=topic,
        discovered_files=[
            MarkdownSourceFile(
                source_path="notes/survey.md",
                classification="topic-guide",
                confidence=0.9,
            ),
            MarkdownSourceFile(
                source_path="notes/paper.md",
                classification="paper-digest",
                candidate_paper_keys=["PAPER1"],
                confidence=0.8,
            ),
            MarkdownSourceFile(source_path="notes/mixed.md", classification="unknown"),
        ],
        planned_writes=[
            PlannedMarkdownWrite(
                target_surface="Guides",
                target_path="Guides/llm-as-a-judge/llm-as-a-judge.md",
                kind="main-guide",
                source_paths=["notes/survey.md"],
                paper_keys=["PAPER1"],
            ),
            PlannedMarkdownWrite(
                target_surface="Papers",
                target_path="Papers/PAPER1.md",
                kind="paper-note",
                source_paths=["notes/paper.md"],
                paper_keys=["PAPER1"],
            ),
        ],
        review_items=[review_item],
    )

    assert plan.guide is not None
    assert plan.guide_folder == "Guides/llm-as-a-judge"
    assert plan.has_review_items
    assert {file.classification for file in plan.discovered_files} == {
        "topic-guide",
        "paper-digest",
        "unknown",
    }


def test_planned_markdown_write_rejects_non_mvp_surfaces() -> None:
    with pytest.raises(ValidationError):
        PlannedMarkdownWrite(
            target_surface="Guides",
            target_path="Collections/benchmarks.md",
            kind="guide-section",
        )


def test_markdown_import_report_tracks_review_state() -> None:
    report = MarkdownImportReport(
        source_path="/path/to/research-notes",
        topic=Topic(name="LLM as a Judge"),
        status="completed-with-review",
        planned_write_count=2,
        completed_write_count=1,
        review_items=[
            MarkdownImportReviewItem(
                category="ambiguous-paper-match",
                message="Two candidate papers share a normalized title.",
                candidate_targets=["PAPER1", "PAPER2"],
            )
        ],
    )

    assert report.needs_review
    assert report.completed_write_count < report.planned_write_count


def test_guide_section_cites_paper_relationship_records_typed_edge() -> None:
    relationship = GuideSectionCitesPaper(
        topic_name="LLM as a Judge",
        topic_slug="llm-as-a-judge",
        guide_section_path="Guides/llm-as-a-judge/sections/bias.md",
        guide_section_title="Bias",
        paper_key="PAPER1",
        paper_path="Papers/PAPER1.md",
    )

    assert relationship.relationship_type == "guide-section-cites-paper"
    assert relationship.paper_path == "Papers/PAPER1.md"
