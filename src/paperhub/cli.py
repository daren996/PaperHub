from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from paperhub.config import default_config_path, load_config, save_config
from paperhub.doctor import run_doctor
from paperhub.enrichment_lint import lint_enriched_note, lint_evidence_bundle
from paperhub.evidence import (
    apply_evidence_bundle_to_paper,
    build_paper_evidence_bundle,
    save_evidence_bundle,
)
from paperhub.importers.markdown import build_markdown_import_plan, execute_markdown_import
from paperhub.mcp_server import serve
from paperhub.models import MissingPaperAction, ZoteroApiConfig, ZoteroCredentials
from paperhub.obsidian import ObsidianExporter, paper_filename_map
from paperhub.store import load_index, save_index
from paperhub.zotero import ZoteroClient, ZoteroError, staged_paper_to_zotero_item

VAULT_HELP = (
    "Vault behavior: most commands use PAPERHUB_VAULT from .env. "
    "Pass a vault path or --vault only when setting the vault for the first time, "
    "switching vaults, or overriding the configured vault for one run."
)

app = typer.Typer(
    help=(
        "PaperHub: Zotero + Obsidian + agent-native literature management. "
        "Reads Zotero credentials and the default Obsidian vault from .env."
    ),
    epilog=VAULT_HELP,
)
zotero_app = typer.Typer(help="Connect and sync a Zotero account through the Zotero Web API.")
obsidian_app = typer.Typer(
    help="Connect and manage a local Obsidian vault folder.",
    epilog="Defaults to PAPERHUB_VAULT from .env when no vault path is provided.",
)
mcp_app = typer.Typer(help="Run PaperHub MCP tools for Codex, Claude Code, and other agents.")
paper_app = typer.Typer(help="Inspect and enrich normalized Zotero-backed paper notes.")
import_app = typer.Typer(
    help=(
        "Processed imports from external research sources. "
        "Substantial guide imports should become a main guide plus section notes."
    )
)
app.add_typer(zotero_app, name="zotero")
app.add_typer(obsidian_app, name="obsidian")
app.add_typer(mcp_app, name="mcp")
app.add_typer(paper_app, name="paper")
app.add_typer(import_app, name="import")
console = Console()


VaultOption = Annotated[
    Path | None,
    typer.Option(
        "--vault",
        "-v",
        help=(
            "Override the local Obsidian vault path for this run. "
            "Defaults to PAPERHUB_VAULT in .env."
        ),
    ),
]


def resolve_vault(vault: Path | None) -> Path:
    candidate = vault
    if not candidate and os.environ.get("PAPERHUB_VAULT"):
        candidate = Path(os.environ["PAPERHUB_VAULT"])
    if not candidate:
        raise typer.BadParameter(
            "Vault path is required. Pass --vault or set PAPERHUB_VAULT in .env."
        )
    return candidate.expanduser().resolve()


@app.command(
    epilog=(
        "If VAULT is omitted, PaperHub uses PAPERHUB_VAULT from .env. "
        "Use an explicit VAULT only to create or switch to a different Obsidian vault."
    )
)
def init(
    vault: Annotated[
        Path | None,
        typer.Argument(
            help="Obsidian vault path to initialize. Defaults to PAPERHUB_VAULT in .env."
        ),
    ] = None,
) -> None:
    """Initialize PaperHub directories in an Obsidian vault."""
    vault = resolve_vault(vault)
    config = load_config(vault=vault)
    config.obsidian.vault_path = str(vault)
    ObsidianExporter(vault, config.obsidian).init_vault()
    save_config(config, default_config_path(vault))
    console.print(f"[green]Initialized PaperHub vault:[/] {vault}")


@app.command("help")
def show_help(ctx: typer.Context) -> None:
    """Show PaperHub help, including .env and vault behavior."""
    root = ctx.parent or ctx
    console.print(root.get_help())


@obsidian_app.command(
    "connect",
    epilog=(
        "If VAULT is omitted, PaperHub uses PAPERHUB_VAULT from .env. "
        "This command records the local vault path; it does not log in to an Obsidian account."
    ),
)
def obsidian_connect(
    vault: Annotated[
        Path | None,
        typer.Argument(help="Obsidian vault path. Defaults to PAPERHUB_VAULT in .env."),
    ] = None,
) -> None:
    """Connect PaperHub to a local Obsidian vault path."""
    init(vault)


@zotero_app.command("connect")
def zotero_connect(
    vault: VaultOption = None,
    user_id: Annotated[str, typer.Option("--user-id", help="Zotero user id.")] = "",
    api_key: Annotated[str, typer.Option("--api-key", help="Zotero API key.")] = "",
    library_type: Annotated[
        str, typer.Option("--library-type", help="Zotero library type.")
    ] = "user",
) -> None:
    """Save Zotero account settings in the vault config."""
    vault = resolve_vault(vault)
    config = load_config(vault=vault)
    config.obsidian.vault_path = str(vault)
    if user_id:
        config.zotero.user_id = user_id
    if api_key:
        config.zotero.api_key = api_key
    config.zotero.library_type = library_type or config.resolved_library_type()
    save_config(config, default_config_path(vault))
    console.print(f"[green]Zotero settings saved for vault:[/] {vault}")
    if not config.resolved_zotero_api_key():
        console.print("[yellow]No API key saved. Set ZOTERO_API_KEY or pass --api-key.[/]")
    if not config.resolved_zotero_user_id():
        console.print("[yellow]No user id saved. Set ZOTERO_USER_ID or pass --user-id.[/]")


@zotero_app.command("sync")
def zotero_sync(vault: VaultOption = None) -> None:
    """Sync the full Zotero account into the PaperHub index, then export Obsidian files."""
    vault = resolve_vault(vault)
    config = load_config(vault=vault)
    api_key = config.resolved_zotero_api_key()
    user_id = config.resolved_zotero_user_id()
    if not api_key or not user_id:
        raise typer.BadParameter(
            "Zotero sync needs ZOTERO_API_KEY and ZOTERO_USER_ID or saved config."
        )

    credentials = ZoteroCredentials(
        api_key=api_key,
        user_id=user_id,
        library_type=config.resolved_library_type(),  # type: ignore[arg-type]
    )
    client = ZoteroClient(
        credentials=credentials,
        config=ZoteroApiConfig(api_base_url=config.zotero.api_base_url),
    )
    try:
        result = client.sync_all()
    except ZoteroError as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(code=1) from exc

    index = load_index(vault)
    index.zotero_user_id = user_id
    index.zotero_library_type = config.zotero.library_type
    index.papers = _merge_synced_and_staged_papers(result.papers, index.papers)
    index.collections = result.collections
    save_index(vault, index)
    ObsidianExporter(vault, config.obsidian).export_all(index)
    console.print(f"[green]Synced {len(result.papers)} papers from Zotero.[/]")


@zotero_app.command("push-staged")
def zotero_push_staged(
    vault: VaultOption = None,
    write: Annotated[
        bool,
        typer.Option(
            "--write",
            help="Actually create staged imported papers in Zotero. Omit for a dry run.",
        ),
    ] = False,
) -> None:
    """Push local IMPORTED-* staged papers to Zotero, explicitly and safely."""
    vault = resolve_vault(vault)
    config = load_config(vault=vault)
    index = load_index(vault)
    staged_papers = [
        paper
        for paper in index.papers
        if paper.key.startswith("IMPORTED-") and paper.zotero_version is None
    ]
    if not staged_papers:
        console.print("[green]No staged imported papers found.[/]")
        return

    _print_staged_zotero_items(staged_papers)
    if not write:
        console.print("[yellow]Dry run only. Re-run with --write to create Zotero items.[/]")
        return

    api_key = config.resolved_zotero_api_key()
    user_id = config.resolved_zotero_user_id()
    if not api_key or not user_id:
        raise typer.BadParameter(
            "Zotero write needs ZOTERO_API_KEY and ZOTERO_USER_ID or saved config."
        )
    client = ZoteroClient(
        ZoteroCredentials(
            api_key=api_key,
            user_id=user_id,
            library_type=config.resolved_library_type(),  # type: ignore[arg-type]
        ),
        config=ZoteroApiConfig(api_base_url=config.zotero.api_base_url),
    )
    result = client.create_items([staged_paper_to_zotero_item(paper) for paper in staged_papers])
    if result.failed:
        console.print(f"[red]Zotero rejected {len(result.failed)} staged papers.[/]")
        raise typer.Exit(code=1)
    mapping = {
        staged_papers[index].key: zotero_key
        for index, zotero_key in result.created.items()
        if zotero_key
    }
    _write_zotero_push_report(vault, mapping)
    console.print(f"[green]Created {len(mapping)} Zotero items from staged papers.[/]")
    console.print(
        "[yellow]Run `paperhub zotero sync` to refresh official Zotero keys in Papers/.[/]"
    )


@app.command()
def export(vault: VaultOption = None) -> None:
    """Regenerate Obsidian Markdown notes, dashboards, and indexes from the index."""
    vault = resolve_vault(vault)
    config = load_config(vault=vault)
    index = load_index(vault)
    ObsidianExporter(vault, config.obsidian).export_all(index)
    console.print(f"[green]Exported PaperHub vault:[/] {vault}")


@import_app.command("markdown")
def import_markdown(
    source: Annotated[
        Path,
        typer.Argument(help="One-off Markdown file or directory to process into the vault."),
    ],
    topic: Annotated[str, typer.Option("--topic", help="Topic guide name for Guides/<topic>.")],
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            help="Legacy alias for the default preview behavior. Cannot be combined with --apply.",
        ),
    ] = False,
    apply: Annotated[
        bool,
        typer.Option("--apply", help="Write the reviewed import plan into the vault."),
    ] = False,
    on_missing_paper: Annotated[
        MissingPaperAction,
        typer.Option(
            "--on-missing-paper",
            help="How to handle paper digests that do not match a synced Zotero paper.",
        ),
    ] = "stage",
    vault: VaultOption = None,
) -> None:
    """Plan or apply a processed import into normalized Papers/ and Guides/."""
    if dry_run and apply:
        raise typer.BadParameter("--dry-run cannot be combined with --apply.")
    vault = resolve_vault(vault)
    config = load_config(vault=vault)
    index = load_index(vault)
    plan = build_markdown_import_plan(
        source,
        topic,
        index,
        dry_run=not apply,
        on_missing_paper=on_missing_paper,
    )
    report = execute_markdown_import(vault, plan)
    if apply:
        index.papers = _merge_imported_papers(index.papers, plan.staged_papers)
        index.guides = [guide for guide in index.guides if guide.topic.slug != plan.topic.slug]
        if plan.guide:
            index.guides.append(plan.guide)
        save_index(vault, index)
        exporter = ObsidianExporter(vault, config.obsidian)
        exporter.init_vault()
        exporter.write_indexes(index)
    _print_import_plan(plan)
    if report.needs_review:
        console.print("[yellow]Import completed with review items.[/]")
    elif not apply:
        console.print("[green]Import plan complete. No files were written.[/]")
    else:
        console.print(f"[green]Imported Markdown into vault:[/] {vault}")


@paper_app.command("enrich")
def paper_enrich(
    paper: Annotated[
        str,
        typer.Argument(
            help="PaperHub/Zotero key, Better BibTeX citation key, or paper note stem."
        ),
    ],
    mode: Annotated[str, typer.Option("--mode", help="Enrichment mode: quick or deep.")] = "quick",
    vault: VaultOption = None,
) -> None:
    """Build an evidence bundle and refresh the normalized paper note scaffold."""
    if mode not in {"quick", "deep"}:
        raise typer.BadParameter("--mode must be quick or deep.")
    vault = resolve_vault(vault)
    config = load_config(vault=vault)
    index = load_index(vault)
    paper_index = _resolve_paper_index(index, paper)
    if paper_index is None:
        console.print(
            f"[red]No indexed paper matched `{paper}`. Sync or import it into PaperHub first.[/]"
        )
        raise typer.Exit(code=1)

    filenames_by_key = paper_filename_map(index.papers)
    original_paper = index.papers[paper_index]
    paper_stem = filenames_by_key.get(original_paper.key)
    bundle = build_paper_evidence_bundle(
        vault,
        original_paper,
        mode=mode,  # type: ignore[arg-type]
        paper_stem=paper_stem,
    )
    bundle_report = lint_evidence_bundle(bundle)
    if not bundle_report.passed:
        _print_lint_report(bundle_report)
        raise typer.Exit(code=1)

    enriched_paper = apply_evidence_bundle_to_paper(original_paper, bundle)
    exporter = ObsidianExporter(vault, config.obsidian)
    collections_by_key = {collection.key: collection for collection in index.collections}
    rendered = exporter.render_paper_note(enriched_paper, collections_by_key)
    note_report = lint_enriched_note(rendered, bundle)
    if not note_report.passed:
        _print_lint_report(note_report)
        raise typer.Exit(code=1)

    bundle_path = save_evidence_bundle(vault, bundle)
    index.papers[paper_index] = enriched_paper
    save_index(vault, index)
    exporter.write_paper(
        enriched_paper,
        collections_by_key,
        filename=filenames_by_key.get(enriched_paper.key),
    )
    exporter.write_indexes(index, filenames_by_key)
    _print_lint_report(note_report)
    console.print(f"[green]Evidence bundle written:[/] {bundle_path.relative_to(vault)}")
    console.print(
        f"[green]Paper note enriched:[/] Papers/{filenames_by_key[enriched_paper.key]}.md"
    )


@app.command()
def doctor(vault: VaultOption = None) -> None:
    """Check the PaperHub vault, Zotero sync state, and data quality."""
    vault = resolve_vault(vault)
    index = load_index(vault)
    checks = run_doctor(vault, index)
    table = Table(title="PaperHub Doctor")
    table.add_column("Status")
    table.add_column("Check")
    for check in checks:
        marker = {"ok": "[green]✓[/]", "warn": "[yellow]![/]", "fail": "[red]x[/]"}[check.status]
        table.add_row(marker, check.message)
    console.print(table)
    if any(check.status == "fail" for check in checks):
        raise typer.Exit(code=1)


@mcp_app.command("serve")
def mcp_serve(vault: VaultOption = None) -> None:
    """Serve PaperHub MCP tools for Codex, Claude Code, and other MCP clients."""
    try:
        serve(resolve_vault(vault))
    except RuntimeError as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(code=1) from exc


def _print_import_plan(plan) -> None:
    table = Table(title="Markdown Import Plan")
    table.add_column("Kind")
    table.add_column("Target")
    table.add_column("Sources")
    table.add_column("Review")
    for write in plan.planned_writes:
        table.add_row(
            write.kind,
            write.target_path,
            ", ".join(write.source_paths) or "-",
            "yes" if write.review_required else "no",
        )
    console.print(table)
    if plan.review_items:
        review_table = Table(title="Review Items")
        review_table.add_column("Severity")
        review_table.add_column("Category")
        review_table.add_column("Source")
        review_table.add_column("Message")
        for item in plan.review_items:
            review_table.add_row(item.severity, item.category, item.source_path, item.message)
        console.print(review_table)
    resolved = sorted({path for write in plan.planned_writes for path in write.paper_paths})
    if resolved:
        resolved_table = Table(title="Resolved Papers")
        resolved_table.add_column("Paper Path")
        for path in resolved:
            resolved_table.add_row(path)
        console.print(resolved_table)
    if plan.staged_papers:
        _print_staged_zotero_items(plan.staged_papers)
    sections = [write for write in plan.planned_writes if write.kind == "guide-section"]
    if sections:
        section_table = Table(title="Proposed Guide Sections")
        section_table.add_column("Target")
        section_table.add_column("Papers")
        for write in sections:
            section_table.add_row(write.target_path, ", ".join(write.paper_paths) or "-")
        console.print(section_table)
    broken_links = [item for item in plan.review_items if item.category == "broken-link"]
    if broken_links:
        broken_table = Table(title="Broken Links")
        broken_table.add_column("Source")
        broken_table.add_column("Message")
        for item in broken_links:
            broken_table.add_row(item.source_path, item.message)
        console.print(broken_table)


def _print_lint_report(report) -> None:
    if not report.items:
        console.print("[green]Enrichment lint passed.[/]")
        return
    table = Table(title="Enrichment Lint")
    table.add_column("Severity")
    table.add_column("Section")
    table.add_column("Message")
    for item in report.items:
        table.add_row(item.severity, item.section or "-", item.message)
    console.print(table)


def _print_staged_zotero_items(staged_papers) -> None:
    table = Table(title="Staged Papers For Zotero")
    table.add_column("PaperHub Key")
    table.add_column("Title")
    table.add_column("Topics")
    for paper in staged_papers:
        table.add_row(paper.key, paper.title, ", ".join(paper.topics) or "-")
    console.print(table)


def _write_zotero_push_report(vault: Path, mapping: dict[str, str]) -> None:
    path = vault / ".paperhub" / "zotero-push-staged.json"
    payload = {
        "created": [
            {"staged_key": staged_key, "zotero_key": zotero_key}
            for staged_key, zotero_key in sorted(mapping.items())
        ]
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _resolve_paper_index(index, query: str) -> int | None:
    normalized = Path(query).stem if query.endswith(".md") else query
    normalized = normalized.removeprefix("Papers/")
    filenames_by_key = paper_filename_map(index.papers)
    for idx, paper in enumerate(index.papers):
        if query == paper.key or normalized == paper.key:
            return idx
        if paper.citation_key and query == paper.citation_key:
            return idx
        if filenames_by_key.get(paper.key) == normalized:
            return idx
    return None


def _merge_imported_papers(existing_papers, staged_papers):
    if not staged_papers:
        return existing_papers
    by_key = {paper.key: paper for paper in existing_papers}
    for paper in staged_papers:
        by_key[paper.key] = paper
    return list(by_key.values())


def _merge_synced_and_staged_papers(synced_papers, existing_papers):
    staged = [
        paper
        for paper in existing_papers
        if paper.key.startswith("IMPORTED-") and paper.zotero_version is None
    ]
    return _merge_imported_papers(synced_papers, staged)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
