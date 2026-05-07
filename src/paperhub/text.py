from __future__ import annotations

import html
import re
import unicodedata
from collections import defaultdict
from collections.abc import Callable, Iterable
from hashlib import sha1
from typing import TypeVar
from urllib.parse import urlparse

T = TypeVar("T")

GENERATED_START = "<!-- paperhub:generated:start -->"
USER_NOTES_MARKER = "\n## User Notes\n"


def slugify(value: str, *, max_length: int = 96) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    normalized = normalized.lower()
    normalized = re.sub(r"[^a-z0-9]+", "-", normalized)
    normalized = normalized.strip("-")
    if not normalized:
        normalized = "untitled"
    return normalized[:max_length].strip("-") or "untitled"


def short_hash(value: str, *, length: int = 8) -> str:
    return sha1(value.encode("utf-8")).hexdigest()[:length]


def title_from_markdown(content: str, fallback: str) -> str:
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip() or fallback
    return fallback


def extract_headings(content: str) -> list[str]:
    headings: list[str] = []
    for line in content.splitlines():
        match = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if match:
            headings.append(match.group(2).strip())
    return headings


def normalize_title(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[_\-:]+", " ", value)
    value = re.sub(r"[^a-z0-9\s]+", "", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def normalize_doi_value(value: str) -> str:
    return (
        value.lower()
        .strip()
        .removeprefix("https://doi.org/")
        .removeprefix("http://doi.org/")
    )


def normalize_url_value(value: str) -> str:
    url = value.strip().lower()
    if not url:
        return ""
    parsed = urlparse(url)
    host = parsed.netloc.removeprefix("www.")
    path = parsed.path.rstrip("/")
    return f"{host}{path}" if host else url.rstrip("/")


def duplicate_groups(items: Iterable[T], key_fn: Callable[[T], str]) -> list[list[T]]:
    groups: dict[str, list[T]] = defaultdict(list)
    for item in items:
        key = key_fn(item)
        if key:
            groups[key].append(item)
    return [values for values in groups.values() if len(values) > 1]


def extract_user_notes(markdown: str) -> str:
    if USER_NOTES_MARKER not in markdown:
        return ""
    return markdown.split(USER_NOTES_MARKER, 1)[1].strip()


def clean_zotero_text(value: str) -> str:
    value = html.unescape(value or "")
    value = re.sub(r"<[^>]+>", "", value)
    value = re.sub(r"\s+", " ", value)
    value = re.sub(r"\s+([:;,.!?])", r"\1", value)
    return value.strip()


def first_year(value: str) -> int | None:
    match = re.search(r"(19|20)\d{2}", value or "")
    if not match:
        return None
    return int(match.group(0))
