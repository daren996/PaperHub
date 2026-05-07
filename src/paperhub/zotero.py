from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from itertools import islice
from typing import Any

import httpx

from paperhub.models import (
    Annotation,
    Attachment,
    Author,
    Collection,
    Paper,
    ZoteroApiConfig,
    ZoteroCredentials,
)
from paperhub.text import clean_zotero_text, first_year


class ZoteroError(RuntimeError):
    pass


@dataclass(frozen=True)
class ZoteroSyncResult:
    papers: list[Paper]
    collections: list[Collection]
    raw_item_count: int


@dataclass(frozen=True)
class ZoteroCreateResult:
    created: dict[int, str]
    failed: dict[int, Any]
    unchanged: dict[int, str]


class ZoteroClient:
    def __init__(
        self,
        credentials: ZoteroCredentials,
        config: ZoteroApiConfig | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.credentials = credentials
        self.config = config or ZoteroApiConfig()
        self.http = http_client or httpx.Client(timeout=30)

    @property
    def prefix(self) -> str:
        library = "users" if self.credentials.library_type == "user" else "groups"
        return f"{library}/{self.credentials.user_id}"

    def sync_all(self) -> ZoteroSyncResult:
        collections = self.fetch_collections()
        items = self.fetch_items()
        papers = normalize_zotero_items(items)
        return ZoteroSyncResult(papers=papers, collections=collections, raw_item_count=len(items))

    def fetch_collections(self) -> list[Collection]:
        objects = self._fetch_paginated(f"{self.prefix}/collections", params={"format": "json"})
        collections: list[Collection] = []
        for obj in objects:
            data = obj.get("data", {})
            collections.append(
                Collection(
                    key=obj.get("key", data.get("key", "")),
                    name=data.get("name", ""),
                    parent_key=_optional_zotero_key(data.get("parentCollection")),
                    version=obj.get("version"),
                )
            )
        return collections

    def fetch_items(self) -> list[dict[str, Any]]:
        return self._fetch_paginated(
            f"{self.prefix}/items",
            params={
                "format": "json",
                "include": "data,bibtex",
                "limit": str(self.config.page_limit),
            },
        )

    def create_items(self, items: list[dict[str, Any]]) -> ZoteroCreateResult:
        created: dict[int, str] = {}
        failed: dict[int, Any] = {}
        unchanged: dict[int, str] = {}
        for offset, batch in _batched_with_offset(items, 50):
            response = self.http.post(
                f"{str(self.config.api_base_url).rstrip('/')}/{self.prefix}/items",
                json=batch,
                headers={**self._headers(), "Content-Type": "application/json"},
            )
            if response.status_code == 403:
                raise ZoteroError("Zotero API key needs write access to create items.")
            if response.status_code == 404:
                raise ZoteroError("Zotero library was not found. Check user id and library type.")
            if response.status_code == 413:
                raise ZoteroError("Too many Zotero items were submitted in one request.")
            response.raise_for_status()
            payload = response.json()
            batch_created = payload.get("success") or payload.get("successful") or {}
            batch_unchanged = payload.get("unchanged") or {}
            batch_failed = payload.get("failed") or {}
            for index, value in batch_created.items():
                created[offset + int(index)] = _created_item_key(value)
            for index, value in batch_unchanged.items():
                unchanged[offset + int(index)] = _created_item_key(value)
            for index, value in batch_failed.items():
                failed[offset + int(index)] = value
        return ZoteroCreateResult(created=created, failed=failed, unchanged=unchanged)

    def _fetch_paginated(
        self, endpoint: str, params: dict[str, str] | None = None
    ) -> list[dict[str, Any]]:
        url = f"{str(self.config.api_base_url).rstrip('/')}/{endpoint.lstrip('/')}"
        start = 0
        output: list[dict[str, Any]] = []
        limit = self.config.page_limit
        while True:
            page_params = dict(params or {})
            page_params["start"] = str(start)
            page_params["limit"] = str(limit)
            response = self.http.get(url, params=page_params, headers=self._headers())
            if response.status_code == 403:
                raise ZoteroError("Zotero API rejected the key or permissions.")
            if response.status_code == 404:
                raise ZoteroError("Zotero library was not found. Check user id and library type.")
            response.raise_for_status()
            batch = response.json()
            if not isinstance(batch, list):
                raise ZoteroError(f"Unexpected Zotero response for {endpoint}: expected a list.")
            output.extend(batch)
            total = int(response.headers.get("Total-Results", len(output)))
            if len(output) >= total or not batch:
                break
            start += len(batch)
        return output

    def _headers(self) -> dict[str, str]:
        return {
            "Zotero-API-Key": self.credentials.api_key,
            "Zotero-API-Version": "3",
            "User-Agent": "PaperHub/0.1",
        }


def normalize_zotero_items(items: list[dict[str, Any]]) -> list[Paper]:
    children_by_parent: dict[str, list[dict[str, Any]]] = defaultdict(list)
    top_level: list[dict[str, Any]] = []
    for item in items:
        data = item.get("data", {})
        parent = data.get("parentItem")
        if parent:
            children_by_parent[parent].append(item)
        else:
            top_level.append(item)

    papers: list[Paper] = []
    for item in top_level:
        data = item.get("data", {})
        item_type = data.get("itemType", "")
        if item_type in {"attachment", "note", "annotation"}:
            continue
        key = item.get("key") or data.get("key", "")
        children = children_by_parent.get(key, [])
        papers.append(_paper_from_zotero_item(item, children))
    papers.sort(key=lambda paper: (paper.year or 0, paper.title.lower()), reverse=True)
    return papers


def staged_paper_to_zotero_item(paper: Paper) -> dict[str, Any]:
    item: dict[str, Any] = {
        "itemType": paper.item_type or "journalArticle",
        "title": paper.title,
        "creators": _zotero_creators(paper.authors),
        "date": str(paper.year) if paper.year else paper.date,
        "DOI": paper.doi,
        "url": paper.url,
        "abstractNote": paper.abstract,
        "tags": _zotero_tags(paper),
        "collections": [],
        "relations": {},
        "extra": f"PaperHub staged key: {paper.key}",
    }
    return {key: value for key, value in item.items() if not _is_empty_zotero_value(value)}


def _paper_from_zotero_item(item: dict[str, Any], children: list[dict[str, Any]]) -> Paper:
    data = item.get("data", {})
    creators = data.get("creators", []) or []
    authors = [
        Author(
            first_name=creator.get("firstName", ""),
            last_name=creator.get("lastName", ""),
            name=creator.get("name", ""),
        )
        for creator in creators
        if creator.get("creatorType", "author") in {"author", "editor", "contributor"}
    ]
    date = data.get("date", "") or ""
    venue = clean_zotero_text(
        data.get("publicationTitle")
        or data.get("conferenceName")
        or data.get("proceedingsTitle")
        or data.get("publisher")
        or ""
    )
    attachments = [_attachment_from_item(child) for child in children if _is_attachment(child)]
    pdf_links = [
        attachment.link for attachment in attachments if attachment.is_pdf and attachment.link
    ]
    zotero_notes = [_note_from_item(child) for child in children if _is_note(child)]
    zotero_notes = [note for note in zotero_notes if note]
    annotations = [_annotation_from_item(child) for child in children if _is_annotation(child)]

    return Paper(
        key=item.get("key") or data.get("key", ""),
        title=clean_zotero_text(data.get("title") or "Untitled") or "Untitled",
        item_type=data.get("itemType") or "journalArticle",
        authors=authors,
        year=first_year(date),
        date=date,
        venue=venue,
        doi=data.get("DOI", "") or "",
        url=data.get("url", "") or "",
        abstract=clean_zotero_text(data.get("abstractNote", "") or ""),
        citation_key=_citation_key_from_item(item),
        bibtex=_bibtex_from_item(item),
        tags=[tag.get("tag", "") for tag in data.get("tags", []) if tag.get("tag")],
        collections=data.get("collections", []) or [],
        attachments=attachments,
        pdf_links=pdf_links,
        zotero_notes=zotero_notes,
        annotations=annotations,
        relations=data.get("relations", {}) or {},
        zotero_version=item.get("version"),
    )


def _is_empty_zotero_value(value: Any) -> bool:
    return value == "" or value == [] or value == {}


def _zotero_creators(authors: list[Author]) -> list[dict[str, str]]:
    creators = []
    for author in authors:
        if author.name:
            creators.append({"creatorType": "author", "name": author.name})
        elif author.first_name or author.last_name:
            creators.append(
                {
                    "creatorType": "author",
                    "firstName": author.first_name,
                    "lastName": author.last_name,
                }
            )
    return creators


def _zotero_tags(paper: Paper) -> list[dict[str, str]]:
    tags = [{"tag": "paperhub-staged-import"}]
    tags.extend({"tag": tag} for tag in paper.tags)
    tags.extend({"tag": f"topic:{topic}"} for topic in paper.topics)
    return tags


def _is_attachment(item: dict[str, Any]) -> bool:
    data = item.get("data", {})
    return data.get("itemType") == "attachment"


def _is_pdf_attachment(item: dict[str, Any]) -> bool:
    return _attachment_from_item(item).is_pdf


def _attachment_from_item(item: dict[str, Any]) -> Attachment:
    data = item.get("data", {})
    return Attachment(
        key=item.get("key") or data.get("key", ""),
        parent_key=_optional_zotero_key(data.get("parentItem")),
        title=clean_zotero_text(data.get("title", "") or ""),
        content_type=data.get("contentType", "") or "",
        path=data.get("path", "") or "",
        url=data.get("url", "") or "",
        filename=data.get("filename", "") or "",
        link_mode=data.get("linkMode", "") or "",
    )


def _attachment_link(item: dict[str, Any]) -> str:
    return _attachment_from_item(item).link


def _is_note(item: dict[str, Any]) -> bool:
    return item.get("data", {}).get("itemType") == "note"


def _note_from_item(item: dict[str, Any]) -> str:
    return clean_zotero_text(item.get("data", {}).get("note", "") or "")


def _is_annotation(item: dict[str, Any]) -> bool:
    return item.get("data", {}).get("itemType") == "annotation"


def _annotation_from_item(item: dict[str, Any]) -> Annotation:
    data = item.get("data", {})
    return Annotation(
        key=item.get("key") or data.get("key", ""),
        parent_key=_optional_zotero_key(data.get("parentItem")),
        text=data.get("annotationText", "") or "",
        comment=data.get("annotationComment", "") or "",
        color=data.get("annotationColor", "") or "",
        page_label=data.get("annotationPageLabel", "") or "",
        sort_index=data.get("annotationSortIndex", "") or "",
    )


def _optional_zotero_key(value: Any) -> str | None:
    if isinstance(value, str) and value:
        return value
    return None


def _citation_key_from_item(item: dict[str, Any]) -> str:
    data = item.get("data", {})
    for value in [item.get("citationKey"), data.get("citationKey")]:
        if isinstance(value, str) and value.strip():
            return value.strip()
    extra = data.get("extra", "") or ""
    patterns = [
        r"(?im)^\s*Citation Key:\s*([^\s]+)\s*$",
        r"(?im)^\s*bibtex:\s*([^\s]+)\s*$",
        r"(?im)^\s*biblatex:\s*([^\s]+)\s*$",
    ]
    for pattern in patterns:
        match = re.search(pattern, extra)
        if match:
            return match.group(1).strip()
    return ""


def _bibtex_from_item(item: dict[str, Any]) -> str:
    for key in ["bibtex", "bib", "citation"]:
        value = item.get(key)
        if isinstance(value, str) and value.strip().startswith("@"):
            return value.strip()
    data = item.get("data", {})
    value = data.get("bibtex")
    if isinstance(value, str) and value.strip().startswith("@"):
        return value.strip()
    return ""


def _batched_with_offset(items: list[dict[str, Any]], size: int):
    iterator = iter(enumerate(items))
    while batch := list(islice(iterator, size)):
        first_index = batch[0][0]
        yield first_index, [item for _, item in batch]


def _created_item_key(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return value.get("key") or value.get("data", {}).get("key", "")
    return ""
