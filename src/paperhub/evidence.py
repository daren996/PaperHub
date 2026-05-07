from __future__ import annotations

import json
import re
from pathlib import Path

from paperhub.models import (
    Attachment,
    EnrichmentMode,
    EvidenceQuality,
    EvidenceTextExcerpt,
    Paper,
    PaperEvidenceBundle,
    PaperFigure,
)
from paperhub.obsidian import paper_filename


def build_paper_evidence_bundle(
    vault: Path,
    paper: Paper,
    *,
    mode: EnrichmentMode = "quick",
    paper_stem: str | None = None,
) -> PaperEvidenceBundle:
    """Collect deterministic evidence for model-side paper-note writing."""
    stem = paper_stem or paper_filename(paper)
    issues: list[str] = []
    pdf_text_excerpts: list[EvidenceTextExcerpt] = []
    figures: list[PaperFigure] = []

    for attachment in paper.attachments:
        if not attachment.is_pdf:
            continue
        local_path = resolve_attachment_path(vault, attachment)
        if not local_path:
            issues.append(f"PDF attachment is not a local readable path: {attachment.link}")
            continue
        extracted = _extract_pdf_text(local_path)
        if not extracted:
            issues.append(f"No PDF text extracted from {local_path}")
            continue
        pdf_text_excerpts.extend(extracted[:12])
        figures.extend(_figure_placeholders_from_text(extracted))

    if not paper.attachments and paper.pdf_links:
        issues.append(
            "Only legacy PDF links are available; no attachment metadata was imported yet."
        )

    if not figures:
        figures = _figure_placeholders_from_annotations(paper)

    quality = _evidence_quality(pdf_text_excerpts, paper.annotations)
    if mode == "deep" and quality in {"metadata-only", "insufficient"}:
        issues.append("Deep enrichment needs PDF text or Zotero annotations before writing.")

    return PaperEvidenceBundle(
        paper_key=paper.key,
        paper_stem=stem,
        mode=mode,
        title=paper.title,
        metadata=_paper_metadata(paper),
        bibtex=paper.bibtex,
        annotations=paper.annotations,
        attachments=paper.attachments,
        pdf_text_excerpts=pdf_text_excerpts,
        figures=figures,
        evidence_quality=quality,
        issues=issues,
    )


def evidence_dir(vault: Path) -> Path:
    return vault / ".paperhub" / "evidence"


def evidence_bundle_relative_path(bundle: PaperEvidenceBundle) -> str:
    return f".paperhub/evidence/{bundle.paper_stem}.json"


def save_evidence_bundle(vault: Path, bundle: PaperEvidenceBundle) -> Path:
    path = vault / evidence_bundle_relative_path(bundle)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = bundle.model_dump(mode="json")
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def apply_evidence_bundle_to_paper(paper: Paper, bundle: PaperEvidenceBundle) -> Paper:
    updated = paper.model_copy(deep=True)
    updated.evidence_bundle_path = evidence_bundle_relative_path(bundle)
    updated.figures = bundle.figures
    if bundle.mode == "quick" and updated.reading_status == "unread":
        updated.reading_status = "summarized"
    if bundle.mode == "deep":
        updated.reading_status = "synthesized"
    return updated


def resolve_attachment_path(vault: Path, attachment: Attachment) -> Path | None:
    raw = attachment.path or attachment.filename
    if raw.startswith("file://"):
        raw = raw.removeprefix("file://")
    if raw.startswith("storage:"):
        return None
    if not raw:
        return None
    candidates = [Path(raw).expanduser()]
    if not candidates[0].is_absolute():
        candidates.append(vault / raw)
    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate.resolve()
    return None


def _paper_metadata(paper: Paper) -> dict[str, object]:
    return {
        "title": paper.title,
        "authors": [author.display for author in paper.authors if author.display],
        "year": paper.year,
        "venue": paper.venue,
        "doi": paper.doi,
        "url": paper.url,
        "zotero_key": paper.key,
        "citation_key": paper.citation_key,
        "item_type": paper.item_type,
        "abstract": paper.abstract,
        "tags": paper.tags,
        "collections": paper.collections,
    }


def _extract_pdf_text(path: Path) -> list[EvidenceTextExcerpt]:
    try:
        import fitz  # type: ignore[import-not-found]
    except ImportError:
        return []

    excerpts: list[EvidenceTextExcerpt] = []
    try:
        with fitz.open(path) as document:
            for page_index, page in enumerate(document, start=1):
                text = _normalize_text(page.get_text("text"))
                if not text:
                    continue
                excerpts.append(
                    EvidenceTextExcerpt(
                        source=str(path),
                        page_label=str(page_index),
                        text=text[:4000],
                    )
                )
    except Exception:
        return []
    return excerpts


def _figure_placeholders_from_text(excerpts: list[EvidenceTextExcerpt]) -> list[PaperFigure]:
    figures: list[PaperFigure] = []
    seen: set[str] = set()
    pattern = re.compile(
        r"\b((?:Fig\.?|Figure|Table)\s+\d+[A-Za-z]?)\s*[:.\-]?\s+(.{12,220})",
        flags=re.IGNORECASE,
    )
    for excerpt in excerpts:
        for match in pattern.finditer(excerpt.text):
            label = _normalize_figure_label(match.group(1))
            if label.lower() in seen:
                continue
            caption = _clean_caption(match.group(2))
            seen.add(label.lower())
            figures.append(
                PaperFigure(
                    figure_id=label.lower().replace(" ", "-").replace(".", ""),
                    label=label,
                    caption=caption,
                    page_label=excerpt.page_label,
                    suggested_location="Method or results section",
                    why_it_matters="_Pending review._",
                    status="placeholder",
                )
            )
            if len(figures) >= 8:
                return figures
    return figures


def _figure_placeholders_from_annotations(paper: Paper) -> list[PaperFigure]:
    figures: list[PaperFigure] = []
    for annotation in paper.annotations:
        text = annotation.text or annotation.comment
        match = re.search(r"\b((?:Fig\.?|Figure|Table)\s+\d+[A-Za-z]?)\b", text, flags=re.I)
        if not match:
            continue
        label = _normalize_figure_label(match.group(1))
        figures.append(
            PaperFigure(
                figure_id=label.lower().replace(" ", "-").replace(".", ""),
                label=label,
                caption=_clean_caption(text),
                page_label=annotation.page_label,
                suggested_location="Annotation-backed review",
                why_it_matters="_Pending review._",
                status="placeholder",
            )
        )
        if len(figures) >= 8:
            break
    return figures


def _evidence_quality(
    excerpts: list[EvidenceTextExcerpt], annotations: list[object]
) -> EvidenceQuality:
    if excerpts and annotations:
        return "mixed"
    if excerpts:
        return "pdf-backed"
    if annotations:
        return "annotation-backed"
    return "metadata-only"


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _normalize_figure_label(value: str) -> str:
    value = value.strip()
    if re.match(r"(?i)^fig\.\s+", value):
        return "Fig. " + re.sub(r"(?i)^fig\.\s+", "", value)
    return re.sub(r"^Fig\b", "Fig.", value, flags=re.IGNORECASE)


def _clean_caption(value: str) -> str:
    value = _normalize_text(value)
    value = re.split(r"(?<=[.!?])\s+", value, maxsplit=1)[0]
    return value[:240]
