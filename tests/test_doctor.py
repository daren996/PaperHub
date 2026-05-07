from __future__ import annotations

from pathlib import Path

import httpx

from paperhub.doctor import run_doctor
from paperhub.models import Attachment, Paper, PaperHubIndex
from paperhub.obsidian import ObsidianExporter
from paperhub.store import save_index


def test_doctor_reports_duplicate_url_and_pdf_availability(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    papers = [
        Paper(
            key="P1",
            title="Duplicate Paper",
            url="https://example.com/paper",
            pdf_links=["paper-1.pdf"],
        ),
        Paper(key="P2", title="Duplicate Paper", url="https://example.com/paper/"),
    ]
    index = PaperHubIndex(papers=papers)
    save_index(vault, index)
    ObsidianExporter(vault).export_all(index)

    checks = run_doctor(vault, index)
    messages = [check.message for check in checks]

    assert any("duplicate paper URL groups" in message for message in messages)
    assert any("duplicate paper title groups" in message for message in messages)
    assert any("papers have PDF links" in message for message in messages)


def test_doctor_reports_zotero_local_api_bbt_and_citation_keys(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    missing_pdf = tmp_path / "missing.pdf"
    index = PaperHubIndex(
        papers=[
            Paper(
                key="P1",
                title="One",
                citation_key="smith2024one",
                attachments=[
                    Attachment(
                        key="A1",
                        title="missing.pdf",
                        content_type="application/pdf",
                        path=str(missing_pdf),
                    )
                ],
            ),
            Paper(key="P2", title="Two"),
        ]
    )
    save_index(vault, index)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/users/0/items":
            return httpx.Response(200, json=[])
        if request.url.path == "/better-bibtex/json-rpc":
            return httpx.Response(200, json={"result": "7.0.0"})
        raise AssertionError(f"Unexpected request: {request.url}")

    checks = run_doctor(
        vault,
        index,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    messages = [check.message for check in checks]

    assert "Zotero Desktop local API is reachable" in messages
    assert "Better BibTeX JSON-RPC is reachable" in messages
    assert any("papers missing citation keys" in message for message in messages)
    assert any("local PDF attachments are not readable" in message for message in messages)
