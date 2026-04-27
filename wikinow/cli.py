"""WikiNow CLI — wn commands."""

import hashlib
import re
from dataclasses import asdict
from pathlib import Path
from typing import NoReturn

import typer
import yaml
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.rule import Rule
from rich.syntax import Syntax

app = typer.Typer(
    name="wikinow",
    help="Know it now. Keep it forever.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)
console = Console()

LOGO = """[bold cyan]
 ██╗    ██╗██╗██╗  ██╗██╗███╗   ██╗ ██████╗ ██╗    ██╗
 ██║    ██║██║██║ ██╔╝██║████╗  ██║██╔═══██╗██║    ██║
 ██║ █╗ ██║██║█████╔╝ ██║██╔██╗ ██║██║   ██║██║ █╗ ██║
 ██║███╗██║██║██╔═██╗ ██║██║╚██╗██║██║   ██║██║███╗██║
 ╚███╔███╔╝██║██║  ██╗██║██║ ╚████║╚██████╔╝╚███╔███╔╝
  ╚══╝╚══╝ ╚═╝╚═╝  ╚═╝╚═╝╚═╝  ╚═══╝ ╚═════╝  ╚══╝╚══╝
[/bold cyan][dim]  Know it now. Keep it forever.[/dim]"""


def _require_project() -> Path:
    """Get active project path or exit with helpful message."""
    from wikinow.config import get_project_path

    try:
        return get_project_path()
    except ValueError:
        _error(
            "Run [bold]wn init <name>[/bold] to create a project first.",
            title="No Active Project",
        )


def _panel(msg: object, title: str = "", border_style: str = "dim") -> None:
    """Print a panel with left-aligned title."""
    console.print(
        Panel(msg, title=title, title_align="left", border_style=border_style)
    )


def _error(msg: str, title: str = "Error") -> NoReturn:
    """Print error panel and exit. Never returns."""
    _panel(msg, title=title, border_style="red")
    raise typer.Exit(1)


def _success(msg: str, title: str = "Done") -> None:
    """Print success panel."""
    _panel(msg, title=title, border_style="green")


# ── Project Commands ──────────────────────────────────────────────────────


@app.command()
def init(name: str = typer.Argument(help="Project name")):
    """[bold green]Create[/bold green] a new WikiNow project."""
    from wikinow.project import init_project

    try:
        path = init_project(name)
        console.print(LOGO)
        _success(
            f"Created [bold]{name}[/bold]\n"
            f"[dim]{path}[/dim]\n\n"
            f"[dim]1.[/dim] Open project folder in [bold]Obsidian[/bold]\n"
            f"[dim]2.[/dim] Start server: [cyan]wn serve[/cyan]\n"
            f"[dim]3.[/dim] Connect: [cyan]claude mcp add wikinow -- wn serve[/cyan]",
            title="Project Created",
        )
    except (ValueError, FileExistsError) as e:
        _error(str(e), title="Init Failed")


@app.command()
def use(name: str = typer.Argument(help="Project name to switch to")):
    """[bold blue]Switch[/bold blue] the active project."""
    from wikinow.project import switch_project

    try:
        switch_project(name)
        _success(
            f"[green]●[/green] Active project: [bold]{name}[/bold]", title="Switched"
        )
    except FileNotFoundError as e:
        _error(str(e), title="Not Found")


@app.command(name="list")
def list_cmd():
    """[bold]List[/bold] all projects."""
    from wikinow.project import list_projects
    from wikinow.config import get_active_project

    projects = list_projects()
    active = get_active_project()

    if not projects:
        _panel(
            "Run [bold cyan]wn init <name>[/bold cyan] to create one.",
            title="No Projects",
            border_style="dim",
        )
        return

    lines = []
    for p in projects:
        if p == active:
            lines.append(f"[green]●[/green] [bold]{p}[/bold]  [dim](active)[/dim]")
        else:
            lines.append(f"[dim]○[/dim] {p}")

    _panel("\n".join(lines), title="Projects", border_style="blue")


# ── Server ────────────────────────────────────────────────────────────────


@app.command()
def serve():
    """[bold cyan]Start[/bold cyan] the MCP server."""
    from wikinow.server import run
    from wikinow.config import get_active_project

    project = get_active_project()
    if not project:
        _error("Run [bold]wn init <name>[/bold] first.", title="No Active Project")

    _panel(
        f"[green]●[/green] WikiNow MCP server\n[dim]Project: {project}[/dim]",
        title="Server",
        border_style="green",
    )
    run()


# ── Ingest ────────────────────────────────────────────────────────────────


@app.command()
def ingest(source: str = typer.Argument(help="URL or file path to ingest")):
    """[bold yellow]Ingest[/bold yellow] a URL or local file into raw/."""
    from wikinow.db import init_storage, index_raw, has_content_hash

    project = _require_project()
    init_storage(project)
    raw_dir = project / "raw"

    try:
        with console.status("[cyan]Fetching...[/cyan]", spinner="dots"):
            path = Path(source)
            if path.exists():
                content, title = _ingest_local(path)
            elif source.startswith(("http://", "https://")):
                content, title = _ingest_url(source)
            else:
                _error(
                    f"Not a valid URL or file path: {source}", title="Invalid Source"
                )

        content_hash = hashlib.sha256(content.encode()).hexdigest()
        if has_content_hash(content_hash):
            _panel(
                "Duplicate content — already ingested.",
                title="Skipped",
                border_style="yellow",
            )
            return

        slug = re.sub(r"[^a-z0-9._-]+", "-", title[:50].lower()).strip("-") or "source"
        filename = f"{slug}.md"
        (raw_dir / filename).write_text(content, encoding="utf-8")
        index_raw(
            filename, source if source.startswith("http") else str(path), content_hash
        )

        _success(
            f"[bold]{title}[/bold]\n"
            f"[dim]raw/{filename} · {len(content):,} chars[/dim]\n"
            f"[dim]Start MCP mode to compile into wiki[/dim]",
            title="Ingested",
        )

    except (ConnectionError, ImportError, FileNotFoundError, ValueError) as e:
        _error(str(e), title="Ingest Failed")


def _ingest_local(path: Path) -> tuple[str, str]:
    """Ingest a local file."""
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        from wikinow.ingestion import extract_pdf

        r = extract_pdf(path)
    elif suffix == ".epub":
        from wikinow.ingestion import extract_epub

        r = extract_epub(path)
    elif suffix in (".mp3", ".wav", ".m4a", ".ogg", ".flac", ".webm"):
        from wikinow.ingestion import transcribe_audio, format_audio

        r = transcribe_audio(path)
        return format_audio(r), r.title
    else:
        from wikinow.ingestion import read_text

        r = read_text(path)
    return r.content, r.title


def _ingest_url(url: str) -> tuple[str, str]:
    """Ingest a URL."""
    from wikinow.ingestion import (
        is_youtube_url,
        fetch_url,
        fetch_youtube,
        format_youtube,
    )
    from wikinow.config import get_ingestion_config

    if is_youtube_url(url):
        r = fetch_youtube(url)
        return format_youtube(r), r.title
    else:
        jina_key = get_ingestion_config().jina_api_key
        r = fetch_url(url, api_key=jina_key)
        return f"# {r.title}\n\n{r.content}", r.title


# ── Search ────────────────────────────────────────────────────────────────


@app.command()
def search(query: str = typer.Argument(help="Search query")):
    """[bold magenta]Search[/bold magenta] the wiki."""
    from wikinow.db import init_storage, search as db_search

    project = _require_project()
    init_storage(project)
    results = db_search(query)

    if not results:
        _panel(f"No results for [bold]{query}[/bold]", border_style="dim")
        return

    lines = []
    for r in results:
        conf_color = {
            "high": "green",
            "medium": "yellow",
            "low": "red",
            "conflict": "red",
        }.get(r.confidence, "dim")
        lines.append(
            f"[bold]{r.title}[/bold]  [{conf_color}]{r.confidence}[/{conf_color}]"
        )
        lines.append(f"[dim]{r.path}[/dim]")
        if r.summary:
            lines.append(f"[dim]{r.summary[:120]}[/dim]")
        lines.append("")

    _panel(
        "\n".join(lines).strip(),
        title=f"Search: {query}",
        border_style="magenta",
    )


# ── Read ──────────────────────────────────────────────────────────────────


@app.command()
def read(
    article: str = typer.Argument(help="Article path (e.g. concepts/attention.md)"),
):
    """[bold]Read[/bold] a wiki article."""
    wiki_dir = _require_project() / "wiki"
    wiki_root = str(wiki_dir.resolve()) + "/"
    file_path = (wiki_dir / article).resolve()
    if not str(file_path).startswith(wiki_root):
        _error(f"Invalid path: {article}", title="Invalid Path")
    if not file_path.exists():
        _error(f"Article not found: {article}", title="Not Found")

    console.print()
    console.print(Rule(f"[bold]{article}[/bold]", style="blue"))
    console.print()
    console.print(Markdown(file_path.read_text(encoding="utf-8")))
    console.print()


# ── Stats ─────────────────────────────────────────────────────────────────


@app.command()
def stats():
    """[bold]Show[/bold] project statistics."""
    from wikinow.config import get_active_project
    from wikinow.db import init_storage, get_stats

    project = _require_project()
    init_storage(project)
    s = get_stats()
    name = get_active_project()

    _panel(
        f"📄 Articles        [bold cyan]{s.articles}[/bold cyan]\n"
        f"📥 Raw sources     [bold cyan]{s.raw_sources}[/bold cyan]\n"
        f"✅ Compiled        [bold cyan]{s.raw_compiled}[/bold cyan]\n"
        f"⏳ Pending         [bold cyan]{s.raw_pending}[/bold cyan]\n"
        f"🔗 Links           [bold cyan]{s.links}[/bold cyan]\n"
        f"🏷️  Tags            [bold cyan]{s.tags}[/bold cyan]\n"
        f"⚡ Contradictions  [bold cyan]{s.contradictions}[/bold cyan]",
        title=name,
        border_style="cyan",
    )


# ── Lint ──────────────────────────────────────────────────────────────────


@app.command()
def lint():
    """[bold yellow]Health check[/bold yellow] — find issues in the wiki."""
    from wikinow.db import (
        init_storage,
        find_orphans,
        find_dead_links,
        find_uncompiled,
        get_stats,
    )

    project = _require_project()
    init_storage(project)

    orphans = find_orphans()
    dead = find_dead_links()
    uncompiled = find_uncompiled()
    s = get_stats()

    total = len(orphans) + len(dead) + len(uncompiled)
    health = max(0, 100 - (total * 5)) if s.articles > 0 else 100
    color = "green" if health >= 80 else "yellow" if health >= 50 else "red"
    bar = "█" * (health // 10) + "░" * (10 - health // 10)

    lines = [f"[{color}]{bar}[/{color}]  [{color} bold]{health}%[/{color} bold]"]

    if orphans:
        lines.append(f"\n[yellow]⚠ Orphan pages ({len(orphans)})[/yellow]")
        for o in orphans:
            lines.append(f"  [dim]○ {o.path}[/dim]")

    if dead:
        lines.append(f"\n[red]✗ Dead links ({len(dead)})[/red]")
        for d in dead:
            lines.append(f"  [dim]✗ [[{d.target_path}]] → {d.source_path}[/dim]")

    if uncompiled:
        lines.append(f"\n[yellow]⚠ Uncompiled ({len(uncompiled)})[/yellow]")
        for u in uncompiled:
            lines.append(f"  [dim]○ {u.path}[/dim]")

    if total == 0:
        lines.append("[green]No issues ✓[/green]")

    _panel("\n".join(lines), title="Health Check", border_style=color)


# ── Gaps ──────────────────────────────────────────────────────────────────


@app.command()
def gaps():
    """Show [bold]knowledge gaps[/bold] and open questions."""
    gaps_path = _require_project() / "wiki" / "gaps.md"
    if not gaps_path.exists():
        _panel("No gaps file found.", border_style="dim")
        return

    console.print()
    console.print(Rule("[bold]Knowledge Gaps[/bold]", style="yellow"))
    console.print()
    console.print(Markdown(gaps_path.read_text(encoding="utf-8")))
    console.print()


# ── Config ────────────────────────────────────────────────────────────────


@app.command()
def config(
    key: str = typer.Argument(None, help="Config key (dot notation)"),
    value: str = typer.Argument(None, help="Value to set"),
):
    """[bold]Show or update[/bold] configuration."""
    from wikinow.config import get_config, set_config

    if key and value:
        set_config(key, value)
        _success(f"[bold]{key}[/bold] = {value}", title="Config Updated")
    elif key:
        _error(
            "Missing value. Usage: [bold]wn config <key> <value>[/bold]",
            title="Missing Value",
        )
    else:
        c = get_config()
        yaml_str = yaml.dump(
            asdict(c), default_flow_style=False, sort_keys=False
        ).strip()
        _panel(
            Syntax(yaml_str, "yaml", theme="monokai"),
            title="Configuration",
            border_style="cyan",
        )


# ── Export ─────────────────────────────────────────────────────────────────


@app.command()
def export():
    """[bold]Export[/bold] wiki as a single markdown file."""
    from wikinow.export import export_single

    try:
        with console.status("[cyan]Exporting...[/cyan]", spinner="dots"):
            output = export_single()
        _success(
            f"[bold]{output.name}[/bold]\n"
            f"[dim]{output} · {output.stat().st_size:,} bytes[/dim]",
            title="Exported",
        )
    except ValueError as e:
        _error(str(e), title="Export Failed")


# ── Version ───────────────────────────────────────────────────────────────


def _version_callback(value: bool):
    if value:
        from wikinow import __version__

        console.print(f"{LOGO}\n  [bold]v{__version__}[/bold]\n")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        None,
        "--version",
        "-v",
        callback=_version_callback,
        is_eager=True,
        help="Show version.",
    ),
):
    """[bold cyan]WikiNow[/bold cyan] — Know it now. Keep it forever."""
