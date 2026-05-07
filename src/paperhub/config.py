from __future__ import annotations

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()


class ZoteroConfig(BaseModel):
    api_key_env: str = "ZOTERO_API_KEY"
    user_id_env: str = "ZOTERO_USER_ID"
    api_key: str = ""
    user_id: str = ""
    library_type: str = "user"
    api_base_url: str = "https://api.zotero.org"
    sync_all: bool = True
    import_pdfs: bool = True
    import_annotations: bool = True


class ObsidianConfig(BaseModel):
    vault_path: str = ""
    paper_dir: str = "Papers"
    guide_dir: str = "Guides"


class PaperHubConfig(BaseModel):
    zotero: ZoteroConfig = Field(default_factory=ZoteroConfig)
    obsidian: ObsidianConfig = Field(default_factory=ObsidianConfig)

    def resolved_zotero_api_key(self) -> str:
        return self.zotero.api_key or os.environ.get(self.zotero.api_key_env, "")

    def resolved_zotero_user_id(self) -> str:
        return self.zotero.user_id or os.environ.get(self.zotero.user_id_env, "")

    def resolved_vault_path(self) -> str:
        return self.obsidian.vault_path or os.environ.get("PAPERHUB_VAULT", "")

    def resolved_library_type(self) -> str:
        return os.environ.get("ZOTERO_LIBRARY_TYPE", self.zotero.library_type)


def default_config_path(vault: Path) -> Path:
    return vault / ".paperhub" / "paperhub.yaml"


def load_config(path: Path | None = None, vault: Path | None = None) -> PaperHubConfig:
    candidate = path or (default_config_path(vault) if vault else None)
    if candidate and candidate.exists():
        data = yaml.safe_load(candidate.read_text(encoding="utf-8")) or {}
        return PaperHubConfig.model_validate(data)
    return PaperHubConfig()


def save_config(config: PaperHubConfig, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = config.model_dump(mode="json")
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
