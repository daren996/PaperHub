from __future__ import annotations

import json
from pathlib import Path

from paperhub.models import PaperHubIndex


def index_dir(vault: Path) -> Path:
    return vault / ".paperhub"


def index_path(vault: Path) -> Path:
    return index_dir(vault) / "index.json"


def load_index(vault: Path) -> PaperHubIndex:
    path = index_path(vault)
    if not path.exists():
        return PaperHubIndex()
    return PaperHubIndex.model_validate_json(path.read_text(encoding="utf-8"))


def save_index(vault: Path, index: PaperHubIndex) -> None:
    index_dir(vault).mkdir(parents=True, exist_ok=True)
    payload = index.model_dump(mode="json")
    index_path(vault).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
