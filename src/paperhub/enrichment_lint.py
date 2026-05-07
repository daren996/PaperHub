from __future__ import annotations

import re

from paperhub.models import EnrichmentLintItem, EnrichmentLintReport, PaperEvidenceBundle

REQUIRED_PAPER_NOTE_SECTIONS = [
    "## Evidence Bundle",
    "## Key Figures",
    "## Digest",
    "## Summary",
    "## Method",
    "## Limitations",
    "## Relevance",
]


def lint_evidence_bundle(bundle: PaperEvidenceBundle) -> EnrichmentLintReport:
    items: list[EnrichmentLintItem] = []
    if not bundle.title:
        items.append(EnrichmentLintItem(severity="error", message="Evidence bundle has no title."))
    if bundle.mode == "deep" and not bundle.has_deep_evidence:
        items.append(
            EnrichmentLintItem(
                severity="error",
                message="Deep enrichment requires PDF text excerpts or Zotero annotations.",
            )
        )
    if bundle.mode == "quick" and bundle.evidence_quality == "metadata-only":
        items.append(
            EnrichmentLintItem(
                severity="warning",
                message="Quick enrichment is metadata-only; generated note should stay scaffolded.",
            )
        )
    for issue in bundle.issues:
        items.append(EnrichmentLintItem(severity="warning", message=issue))
    return EnrichmentLintReport(mode=bundle.mode, items=items)


def lint_enriched_note(markdown: str, bundle: PaperEvidenceBundle) -> EnrichmentLintReport:
    report = lint_evidence_bundle(bundle)
    for section in REQUIRED_PAPER_NOTE_SECTIONS:
        if section not in markdown:
            report.items.append(
                EnrichmentLintItem(
                    severity="error",
                    section=section,
                    message=f"Generated paper note is missing {section}.",
                )
            )
    if bundle.figures and "> [!figure]" not in markdown:
        report.items.append(
            EnrichmentLintItem(
                severity="error",
                section="## Key Figures",
                message="Figure placeholders exist in the bundle but not in the paper note.",
            )
        )
    for figure in bundle.figures:
        if figure.label not in markdown:
            report.items.append(
                EnrichmentLintItem(
                    severity="error",
                    section="## Key Figures",
                    message=f"Missing figure placeholder for {figure.label}.",
                )
            )
    for match in re.finditer(r"> \[!figure\][^\n]*(?:\n> .*)*", markdown):
        block = match.group(0)
        if "> Status:" not in block:
            report.items.append(
                EnrichmentLintItem(
                    severity="error",
                    section="## Key Figures",
                    message="Figure callout is missing a Status line.",
                )
            )
    return report
