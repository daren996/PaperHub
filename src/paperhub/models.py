from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, HttpUrl, ValidationInfo, field_validator, model_validator

from paperhub.text import slugify

ReadingStatus = Literal["unread", "reading", "summarized", "synthesized", "used-in-paper"]
EnrichmentMode = Literal["quick", "deep"]
EvidenceQuality = Literal[
    "metadata-only", "annotation-backed", "pdf-backed", "mixed", "insufficient"
]
FigureStatus = Literal["placeholder", "extracted", "needs-review"]
GuideSectionKind = Literal["overview", "paper-backed", "appendix", "support-note"]
MarkdownSourceKind = Literal[
    "paper-digest",
    "topic-guide",
    "guide-section",
    "guide-support-note",
    "unknown",
]
MarkdownWriteKind = Literal["paper-note", "main-guide", "guide-section", "guide-support-note"]
MarkdownImportReviewCategory = Literal[
    "ambiguous-classification",
    "ambiguous-paper-match",
    "unknown-file",
    "broken-link",
    "duplicate-candidate",
    "unsupported-structure",
]
MarkdownImportReviewSeverity = Literal["info", "warning", "error"]
MarkdownImportStatus = Literal["planned", "completed", "completed-with-review", "failed"]
MissingPaperAction = Literal["report", "stage", "zotero"]
RelationshipType = Literal["guide-section-cites-paper"]


def utc_now() -> datetime:
    return datetime.now(UTC)


class Author(BaseModel):
    first_name: str = ""
    last_name: str = ""
    name: str = ""

    @property
    def display(self) -> str:
        if self.name:
            return self.name
        return " ".join(part for part in [self.first_name, self.last_name] if part).strip()


class Collection(BaseModel):
    key: str
    name: str
    parent_key: str | None = None
    version: int | None = None


class Annotation(BaseModel):
    key: str
    parent_key: str | None = None
    text: str = ""
    comment: str = ""
    color: str = ""
    page_label: str = ""
    sort_index: str = ""


class Attachment(BaseModel):
    key: str = ""
    parent_key: str | None = None
    title: str = ""
    content_type: str = ""
    path: str = ""
    url: str = ""
    filename: str = ""
    link_mode: str = ""

    @property
    def link(self) -> str:
        return self.path or self.url or self.filename or self.title

    @property
    def is_pdf(self) -> bool:
        return self.content_type == "application/pdf" or self.link.lower().endswith(".pdf")


class PaperFigure(BaseModel):
    figure_id: str
    label: str
    caption: str = ""
    page_label: str = ""
    suggested_location: str = ""
    why_it_matters: str = "_Pending review._"
    status: FigureStatus = "placeholder"


class EvidenceTextExcerpt(BaseModel):
    source: str
    text: str
    page_label: str = ""
    section: str = ""


class PaperEvidenceBundle(BaseModel):
    paper_key: str
    paper_stem: str
    mode: EnrichmentMode = "quick"
    title: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    bibtex: str = ""
    annotations: list[Annotation] = Field(default_factory=list)
    attachments: list[Attachment] = Field(default_factory=list)
    pdf_text_excerpts: list[EvidenceTextExcerpt] = Field(default_factory=list)
    figures: list[PaperFigure] = Field(default_factory=list)
    evidence_quality: EvidenceQuality = "metadata-only"
    issues: list[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=utc_now)

    @property
    def has_deep_evidence(self) -> bool:
        return bool(self.pdf_text_excerpts or self.annotations)


class EnrichmentLintItem(BaseModel):
    severity: Literal["info", "warning", "error"] = "warning"
    message: str
    section: str = ""


class EnrichmentLintReport(BaseModel):
    mode: EnrichmentMode = "quick"
    items: list[EnrichmentLintItem] = Field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not any(item.severity == "error" for item in self.items)


class Paper(BaseModel):
    key: str
    title: str
    item_type: str = "journalArticle"
    authors: list[Author] = Field(default_factory=list)
    year: int | None = None
    date: str = ""
    venue: str = ""
    doi: str = ""
    url: str = ""
    abstract: str = ""
    citation_key: str = ""
    bibtex: str = ""
    tags: list[str] = Field(default_factory=list)
    collections: list[str] = Field(default_factory=list)
    attachments: list[Attachment] = Field(default_factory=list)
    pdf_links: list[str] = Field(default_factory=list)
    zotero_notes: list[str] = Field(default_factory=list)
    annotations: list[Annotation] = Field(default_factory=list)
    relations: dict[str, Any] = Field(default_factory=dict)
    zotero_version: int | None = None
    reading_status: ReadingStatus = "unread"
    topics: list[str] = Field(default_factory=list)
    concepts: list[str] = Field(default_factory=list)
    claims: list[str] = Field(default_factory=list)
    evidence_bundle_path: str = ""
    figures: list[PaperFigure] = Field(default_factory=list)

    @property
    def author_text(self) -> str:
        names = [author.display for author in self.authors if author.display]
        return ", ".join(names)


class Topic(BaseModel):
    name: str
    slug: str = ""
    aliases: list[str] = Field(default_factory=list)
    description: str = ""

    @model_validator(mode="after")
    def fill_slug(self) -> Topic:
        self.slug = slugify(self.slug or self.name)
        return self

    @property
    def guide_folder(self) -> str:
        return f"Guides/{self.slug}"


class GuideSection(BaseModel):
    title: str
    slug: str = ""
    kind: GuideSectionKind = "paper-backed"
    summary: str = ""
    paper_keys: list[str] = Field(default_factory=list)
    source_paths: list[str] = Field(default_factory=list)
    body: str = ""
    review_required: bool = False

    @model_validator(mode="after")
    def fill_slug(self) -> GuideSection:
        self.slug = slugify(self.slug or self.title)
        return self

    @property
    def filename(self) -> str:
        return f"{self.slug}.md"


class Guide(BaseModel):
    topic: Topic
    title: str = ""
    purpose: str = ""
    scope: str = ""
    main_filename: str = ""
    sections: list[GuideSection] = Field(default_factory=list)
    paper_keys: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def fill_guide_defaults(self) -> Guide:
        if not self.title:
            self.title = self.topic.name
        if not self.main_filename:
            self.main_filename = f"{self.topic.slug}.md"
        if "/" in self.main_filename or "\\" in self.main_filename:
            raise ValueError("Guide main_filename must be a filename inside Guides/<topic>/")
        if not self.main_filename.endswith(".md"):
            self.main_filename = f"{self.main_filename}.md"
        return self

    @property
    def folder_path(self) -> str:
        return self.topic.guide_folder

    @property
    def main_path(self) -> str:
        return f"{self.folder_path}/{self.main_filename}"


class MarkdownSourceFile(BaseModel):
    source_path: str
    classification: MarkdownSourceKind = "unknown"
    title: str = ""
    headings: list[str] = Field(default_factory=list)
    candidate_paper_keys: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class MarkdownImportReviewItem(BaseModel):
    category: MarkdownImportReviewCategory
    message: str
    severity: MarkdownImportReviewSeverity = "warning"
    source_path: str = ""
    candidate_targets: list[str] = Field(default_factory=list)


class PlannedMarkdownWrite(BaseModel):
    target_surface: Literal["Papers", "Guides"]
    target_path: str
    kind: MarkdownWriteKind
    source_paths: list[str] = Field(default_factory=list)
    paper_keys: list[str] = Field(default_factory=list)
    paper_paths: list[str] = Field(default_factory=list)
    review_required: bool = False

    @field_validator("target_path")
    @classmethod
    def target_path_stays_in_surface(cls, value: str, info: ValidationInfo) -> str:
        if value.startswith("/") or "\\" in value:
            raise ValueError("target_path must be a vault-relative POSIX path")
        parts = value.split("/")
        if ".." in parts:
            raise ValueError("target_path must not contain parent-directory segments")
        surface = info.data.get("target_surface")
        if surface and parts[0] != surface:
            raise ValueError("target_path must stay under its target_surface")
        if parts[0] not in {"Papers", "Guides"}:
            raise ValueError("target_path must stay under Papers/ or Guides/")
        return value


class GuideSectionCitesPaper(BaseModel):
    relationship_type: RelationshipType = "guide-section-cites-paper"
    topic_name: str
    topic_slug: str
    guide_section_path: str
    guide_section_title: str = ""
    paper_key: str
    paper_path: str
    source_paths: list[str] = Field(default_factory=list)


class MarkdownImportPlan(BaseModel):
    source_path: str
    topic: Topic
    dry_run: bool = True
    on_missing_paper: MissingPaperAction = "report"
    discovered_files: list[MarkdownSourceFile] = Field(default_factory=list)
    planned_writes: list[PlannedMarkdownWrite] = Field(default_factory=list)
    review_items: list[MarkdownImportReviewItem] = Field(default_factory=list)
    staged_papers: list[Paper] = Field(default_factory=list)
    guide: Guide | None = None
    generated_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def fill_guide(self) -> MarkdownImportPlan:
        if self.guide is None:
            self.guide = Guide(topic=self.topic)
        return self

    @property
    def guide_folder(self) -> str:
        return self.topic.guide_folder

    @property
    def has_review_items(self) -> bool:
        return bool(self.review_items)


class MarkdownImportReport(BaseModel):
    source_path: str
    topic: Topic
    status: MarkdownImportStatus = "planned"
    planned_write_count: int = 0
    completed_write_count: int = 0
    written_paths: list[str] = Field(default_factory=list)
    skipped_paths: list[str] = Field(default_factory=list)
    review_items: list[MarkdownImportReviewItem] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=utc_now)

    @property
    def needs_review(self) -> bool:
        return bool(self.review_items) or self.status in {"completed-with-review", "failed"}


class ReadingPath(BaseModel):
    id: str
    title: str
    goal: str = ""
    paper_keys: list[str] = Field(default_factory=list)


class PaperHubIndex(BaseModel):
    generated_at: datetime = Field(default_factory=utc_now)
    zotero_user_id: str = ""
    zotero_library_type: str = "user"
    papers: list[Paper] = Field(default_factory=list)
    collections: list[Collection] = Field(default_factory=list)
    guides: list[Guide] = Field(default_factory=list)
    reading_paths: list[ReadingPath] = Field(default_factory=list)


class ZoteroCredentials(BaseModel):
    api_key: str
    user_id: str
    library_type: Literal["user", "group"] = "user"


class ZoteroApiConfig(BaseModel):
    api_base_url: HttpUrl | str = "https://api.zotero.org"
    page_limit: int = 100
