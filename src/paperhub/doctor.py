from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import httpx

from paperhub.evidence import resolve_attachment_path
from paperhub.models import Paper, PaperHubIndex
from paperhub.store import index_path
from paperhub.text import (
    duplicate_groups,
    normalize_doi_value,
    normalize_title,
    normalize_url_value,
)


@dataclass(frozen=True)
class DoctorCheck:
    status: str
    message: str


def run_doctor(
    vault: Path,
    index: PaperHubIndex,
    *,
    http_client: httpx.Client | None = None,
) -> list[DoctorCheck]:
    checks: list[DoctorCheck] = []
    checks.append(
        _check(vault.exists(), "Obsidian vault found", f"Obsidian vault missing: {vault}")
    )
    checks.append(
        _check(index_path(vault).exists(), "PaperHub index found", "PaperHub index missing")
    )
    checks.append(
        _check(
            bool(index.papers),
            f"{len(index.papers)} papers indexed",
            "No papers indexed",
        )
    )
    checks.extend(_duplicate_checks(index))
    checks.extend(_citation_key_checks(index))

    pdf_count = sum(1 for paper in index.papers if paper.pdf_links)
    checks.append(
        _check(pdf_count > 0, f"{pdf_count} papers have PDF links", "No PDF links imported yet")
    )

    annotation_count = sum(len(paper.annotations) for paper in index.papers)
    checks.append(
        _check(
            annotation_count > 0,
            f"{annotation_count} Zotero annotations imported",
            "No Zotero annotations imported yet",
            warn=True,
        )
    )

    missing_abstracts = [paper for paper in index.papers if not paper.abstract]
    checks.append(
        _check(
            not missing_abstracts,
            "All papers have abstracts",
            f"{len(missing_abstracts)} papers missing abstracts",
            warn=True,
        )
    )
    missing_doi = [paper for paper in index.papers if not paper.doi]
    checks.append(
        _check(
            not missing_doi,
            "All papers have DOI values",
            f"{len(missing_doi)} papers missing DOI values",
            warn=True,
        )
    )
    missing_url = [paper for paper in index.papers if not paper.url]
    checks.append(
        _check(
            not missing_url,
            "All papers have URL values",
            f"{len(missing_url)} papers missing URL values",
            warn=True,
        )
    )

    checks.append(_local_pdf_attachment_check(vault, index))
    checks.extend(_zotero_desktop_checks(http_client))

    return checks


def _check(condition: bool, ok: str, fail: str, *, warn: bool = False) -> DoctorCheck:
    if condition:
        return DoctorCheck("ok", ok)
    return DoctorCheck("warn" if warn else "fail", fail)


def _duplicate_checks(index: PaperHubIndex) -> list[DoctorCheck]:
    return [
        _duplicate_check(index.papers, "DOI", lambda paper: normalize_doi_value(paper.doi)),
        _duplicate_check(index.papers, "URL", lambda paper: normalize_url_value(paper.url)),
        _duplicate_check(index.papers, "title", lambda paper: normalize_title(paper.title)),
    ]


def _citation_key_checks(index: PaperHubIndex) -> list[DoctorCheck]:
    missing = [paper for paper in index.papers if not paper.citation_key]
    return [
        _check(
            not missing,
            "All papers have citation keys",
            f"{len(missing)} papers missing citation keys",
            warn=True,
        ),
        _duplicate_check(index.papers, "citation key", lambda paper: paper.citation_key),
    ]


def _duplicate_check(papers: list[Paper], label: str, key_fn) -> DoctorCheck:
    groups = duplicate_groups(papers, key_fn)
    examples = ", ".join(group[0].title for group in groups[:3])
    suffix = f": {examples}" if examples else ""
    return _check(
        not groups,
        f"No duplicate paper {label}s detected",
        f"{len(groups)} duplicate paper {label} groups detected{suffix}",
        warn=True,
    )


def _local_pdf_attachment_check(vault: Path, index: PaperHubIndex) -> DoctorCheck:
    pdf_attachments = [
        attachment
        for paper in index.papers
        for attachment in paper.attachments
        if attachment.is_pdf
    ]
    local_candidates = [
        attachment
        for attachment in pdf_attachments
        if attachment.path and not attachment.path.startswith("storage:")
    ]
    readable = [
        attachment
        for attachment in local_candidates
        if resolve_attachment_path(vault, attachment) is not None
    ]
    if not local_candidates:
        return DoctorCheck("warn", "No local PDF attachment paths imported yet")
    return _check(
        len(readable) == len(local_candidates),
        f"{len(readable)} local PDF attachments are readable",
        f"{len(local_candidates) - len(readable)} local PDF attachments are not readable",
        warn=True,
    )


def _zotero_desktop_checks(http_client: httpx.Client | None) -> list[DoctorCheck]:
    owns_client = http_client is None
    client = http_client or httpx.Client(timeout=1.0)
    try:
        return [_zotero_local_api_check(client), _better_bibtex_check(client)]
    finally:
        if owns_client:
            client.close()


def _zotero_local_api_check(client: httpx.Client) -> DoctorCheck:
    try:
        response = client.get(
            "http://127.0.0.1:23119/api/users/0/items",
            params={"format": "json", "limit": "1"},
        )
    except httpx.HTTPError:
        return DoctorCheck(
            "warn",
            "Zotero Desktop local API is not reachable on 127.0.0.1:23119",
        )
    if response.status_code == 200:
        return DoctorCheck("ok", "Zotero Desktop local API is reachable")
    return DoctorCheck(
        "warn",
        f"Zotero Desktop local API returned HTTP {response.status_code}",
    )


def _better_bibtex_check(client: httpx.Client) -> DoctorCheck:
    try:
        response = client.post(
            "http://127.0.0.1:23119/better-bibtex/json-rpc",
            json={"jsonrpc": "2.0", "method": "version", "params": [], "id": 1},
        )
    except httpx.HTTPError:
        return DoctorCheck("warn", "Better BibTeX JSON-RPC is not reachable")
    if response.status_code == 200:
        return DoctorCheck("ok", "Better BibTeX JSON-RPC is reachable")
    return DoctorCheck("warn", f"Better BibTeX JSON-RPC returned HTTP {response.status_code}")
