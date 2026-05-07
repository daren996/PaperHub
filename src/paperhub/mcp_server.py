from __future__ import annotations

from pathlib import Path
from typing import Any

from paperhub.doctor import run_doctor
from paperhub.store import load_index


def serve(vault: Path) -> None:
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:  # pragma: no cover - depends on optional extra
        raise RuntimeError("Install PaperHub with the MCP extra: pip install -e '.[mcp]'") from exc

    mcp = FastMCP("paperhub")

    @mcp.tool()
    def list_papers() -> list[dict[str, Any]]:
        """List Zotero papers currently indexed in the connected PaperHub vault."""
        index = load_index(vault)
        return [
            {
                "key": paper.key,
                "title": paper.title,
                "year": paper.year,
                "venue": paper.venue,
                "doi": paper.doi,
                "tags": paper.tags,
            }
            for paper in index.papers
        ]

    @mcp.tool()
    def run_paperhub_doctor() -> list[dict[str, str]]:
        """Run PaperHub diagnostics for the connected vault."""
        index = load_index(vault)
        return [check.__dict__ for check in run_doctor(vault, index)]

    mcp.run()
