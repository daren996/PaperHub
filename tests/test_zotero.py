from __future__ import annotations

import httpx

from paperhub.models import Author, Paper, ZoteroCredentials
from paperhub.zotero import ZoteroClient, staged_paper_to_zotero_item


def test_zotero_sync_normalizes_papers_attachments_and_annotations() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/collections"):
            return httpx.Response(
                200,
                headers={"Total-Results": "1"},
                json=[{"key": "COL1", "version": 1, "data": {"name": "Agent Benchmark"}}],
            )
        if path.endswith("/items"):
            return httpx.Response(
                200,
                headers={"Total-Results": "4"},
                json=[
                    {
                        "key": "PAPER1",
                        "version": 7,
                        "bibtex": "@article{lovelace2025agent, title={Agent-as-a-Judge}}",
                        "data": {
                            "itemType": "conferencePaper",
                            "title": "Agent-as-a-Judge: Evaluate Agents with Agents",
                            "creators": [
                                {
                                    "creatorType": "author",
                                    "firstName": "Ada",
                                    "lastName": "Lovelace",
                                }
                            ],
                            "date": "2025",
                            "conferenceName": "TestConf",
                            "DOI": "10.123/test",
                            "abstractNote": "A paper about agent judges.",
                            "extra": "Citation Key: lovelace2025agent",
                            "tags": [{"tag": "agent benchmark"}],
                            "collections": ["COL1"],
                            "relations": {"dc:relation": "https://example.com/related"},
                        },
                    },
                    {
                        "key": "PDF1",
                        "data": {
                            "itemType": "attachment",
                            "parentItem": "PAPER1",
                            "contentType": "application/pdf",
                            "title": "paper.pdf",
                            "url": "https://example.com/paper.pdf",
                            "path": "/tmp/paper.pdf",
                        },
                    },
                    {
                        "key": "NOTE1",
                        "data": {
                            "itemType": "note",
                            "parentItem": "PAPER1",
                            "note": "<p>Remember the benchmark setup.</p>",
                        },
                    },
                    {
                        "key": "ANN1",
                        "data": {
                            "itemType": "annotation",
                            "parentItem": "PAPER1",
                            "annotationText": "Important quote",
                            "annotationPageLabel": "3",
                        },
                    },
                ],
            )
        raise AssertionError(f"Unexpected request: {request.url}")

    client = ZoteroClient(
        ZoteroCredentials(api_key="key", user_id="123"),
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    result = client.sync_all()

    assert len(result.collections) == 1
    assert len(result.papers) == 1
    paper = result.papers[0]
    assert paper.key == "PAPER1"
    assert paper.year == 2025
    assert paper.author_text == "Ada Lovelace"
    assert paper.pdf_links == ["/tmp/paper.pdf"]
    assert paper.attachments[0].path == "/tmp/paper.pdf"
    assert paper.citation_key == "lovelace2025agent"
    assert paper.bibtex.startswith("@article{lovelace2025agent")
    assert paper.zotero_notes == ["Remember the benchmark setup."]
    assert paper.relations == {"dc:relation": "https://example.com/related"}
    assert paper.annotations[0].text == "Important quote"


def test_zotero_sync_accepts_false_collection_parent() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/collections"):
            return httpx.Response(
                200,
                headers={"Total-Results": "1"},
                json=[
                    {
                        "key": "COL1",
                        "version": 1,
                        "data": {
                            "key": "COL1",
                            "name": "Top-level Collection",
                            "parentCollection": False,
                        },
                    }
                ],
            )
        if path.endswith("/items"):
            return httpx.Response(200, headers={"Total-Results": "0"}, json=[])
        raise AssertionError(f"Unexpected request: {request.url}")

    client = ZoteroClient(
        ZoteroCredentials(api_key="key", user_id="123"),
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    result = client.sync_all()

    assert result.collections[0].parent_key is None


def test_zotero_sync_strips_markup_from_human_readable_fields() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/collections"):
            return httpx.Response(200, headers={"Total-Results": "0"}, json=[])
        if path.endswith("/items"):
            return httpx.Response(
                200,
                headers={"Total-Results": "1"},
                json=[
                    {
                        "key": "PNEUMA1",
                        "data": {
                            "itemType": "journalArticle",
                            "title": (
                                '<span style="font-variant:small-caps;">Pneuma</span> : '
                                "Leveraging LLMs for Tabular Data"
                            ),
                            "publicationTitle": "Proceedings &amp; Reports",
                            "abstractNote": "<p>A system for table retrieval.</p>",
                        },
                    }
                ],
            )
        raise AssertionError(f"Unexpected request: {request.url}")

    client = ZoteroClient(
        ZoteroCredentials(api_key="key", user_id="123"),
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    result = client.sync_all()

    paper = result.papers[0]
    assert paper.title == "Pneuma: Leveraging LLMs for Tabular Data"
    assert paper.venue == "Proceedings & Reports"
    assert paper.abstract == "A system for table retrieval."


def test_zotero_create_items_posts_staged_papers() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.method == "POST"
        assert request.url.path.endswith("/items")
        assert request.headers["Zotero-API-Key"] == "key"
        assert request.headers["Content-Type"] == "application/json"
        return httpx.Response(200, json={"success": {"0": "ZOTERO1"}, "failed": {}})

    client = ZoteroClient(
        ZoteroCredentials(api_key="key", user_id="123"),
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    item = staged_paper_to_zotero_item(
        Paper(
            key="IMPORTED-123",
            title="Missing Paper",
            authors=[Author(first_name="Ada", last_name="Lovelace")],
            year=2025,
            topics=["LLM as a Judge"],
        )
    )
    result = client.create_items([item])

    assert result.created == {0: "ZOTERO1"}
    assert not result.failed
    payload = json_from_request(requests[0])
    assert payload[0]["title"] == "Missing Paper"
    assert payload[0]["creators"] == [
        {"creatorType": "author", "firstName": "Ada", "lastName": "Lovelace"}
    ]
    assert {"tag": "paperhub-staged-import"} in payload[0]["tags"]
    assert {"tag": "topic:LLM as a Judge"} in payload[0]["tags"]
    assert payload[0]["extra"] == "PaperHub staged key: IMPORTED-123"


def json_from_request(request: httpx.Request):
    import json

    return json.loads(request.content.decode("utf-8"))
