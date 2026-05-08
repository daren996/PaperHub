from __future__ import annotations

import json
from pathlib import Path

from paperhub.models import GuideSectionCitesPaper, MarkdownImportPlan
from paperhub.store import index_dir

RELATIONSHIP_TYPE = "guide-section-cites-paper"
SCHEMA_VERSION = 1


def relationship_dir(vault: Path) -> Path:
    return index_dir(vault) / "relationships"


def guide_section_cites_paper_manifest_path(vault: Path) -> Path:
    return relationship_dir(vault) / f"{RELATIONSHIP_TYPE}.json"


def build_guide_section_cites_paper_relationships(
    plan: MarkdownImportPlan,
) -> list[GuideSectionCitesPaper]:
    relationships: list[GuideSectionCitesPaper] = []
    for write in plan.planned_writes:
        if write.kind != "guide-section" or write.child_paths:
            continue
        section_title = write.title or _section_title_from_path(write.target_path)
        for index, paper_key in enumerate(write.paper_keys):
            paper_path = write.paper_paths[index] if index < len(write.paper_paths) else ""
            if not paper_path:
                continue
            relationships.append(
                GuideSectionCitesPaper(
                    topic_name=plan.topic.name,
                    topic_slug=plan.topic.slug,
                    guide_section_path=write.target_path,
                    guide_section_title=section_title,
                    paper_key=paper_key,
                    paper_path=paper_path,
                )
            )
    return relationships


def write_guide_section_cites_paper_manifest(vault: Path, plan: MarkdownImportPlan) -> Path:
    path = guide_section_cites_paper_manifest_path(vault)
    existing_relationships = _existing_relationships(path)
    retained = [
        relationship
        for relationship in existing_relationships
        if relationship.get("topic_slug") != plan.topic.slug
    ]
    current = [
        relationship.model_dump(mode="json")
        for relationship in build_guide_section_cites_paper_relationships(plan)
    ]
    payload = {
        "schema_version": SCHEMA_VERSION,
        "relationship_type": RELATIONSHIP_TYPE,
        "relationships": sorted(
            retained + current,
            key=lambda relationship: (
                relationship.get("topic_slug", ""),
                relationship.get("guide_section_path", ""),
                relationship.get("paper_key", ""),
            ),
        ),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _existing_relationships(path: Path) -> list[dict]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("relationship_type") != RELATIONSHIP_TYPE:
        return []
    relationships = payload.get("relationships", [])
    return [relationship for relationship in relationships if isinstance(relationship, dict)]


def _section_title_from_path(path: str) -> str:
    return Path(path).stem.replace("-", " ").title()
