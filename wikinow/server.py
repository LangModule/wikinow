"""WikiNow MCP server — exposes all tools via FastMCP."""

import hashlib
import re
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from fastmcp import FastMCP

from wikinow.config import get_project_path
from wikinow.db import (
    find_dead_links,
    find_orphans,
    find_uncompiled,
    get_contradictions,
    get_stats,
    index_article as db_index_article,
    index_raw as db_index_raw,
    init_storage,
    list_articles,
    list_raw,
    list_tags,
    mark_compiled as db_mark_compiled,
)
from wikinow.export import export_single
from wikinow.ingestion import fetch_url, fetch_youtube, is_youtube_url, format_youtube
from wikinow.search import search_wiki, search_web as web_search


mcp = FastMCP("wikinow")


# ── Cached Paths ──────────────────────────────────────────────────────────

_project_path: Path | None = None


def _project() -> Path:
    """Get active project path, cached after first call."""
    global _project_path
    if _project_path is None:
        _project_path = get_project_path()
        init_storage(_project_path)
    return _project_path


def _wiki() -> Path:
    return _project() / "wiki"


def _raw() -> Path:
    return _project() / "raw"


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _slugify(name: str) -> str:
    """Convert a name to a clean filename."""
    slug = name.lower()
    slug = re.sub(r"[^a-z0-9._-]+", "-", slug)
    slug = slug.strip("-")
    return slug or "source.md"


def _check_dedup(content_hash: str) -> bool:
    """Check if content already exists in raw sources. Returns True if duplicate."""
    from wikinow.db import has_content_hash

    return has_content_hash(content_hash)


# ── Ingest Tools ──────────────────────────────────────────────────────────


@mcp.tool()
def ingest_url(url: str) -> str:
    """Fetch a URL and save to raw/. Returns the content for compilation."""
    if is_youtube_url(url):
        response = fetch_youtube(url)
        content = format_youtube(response)
        filename = f"youtube-{response.title[:50]}.md"
    else:
        from wikinow.config import get_ingestion_config

        jina_key = get_ingestion_config().jina_api_key
        response = fetch_url(url, api_key=jina_key)
        content = f"# {response.title}\n\n{response.content}"
        filename = f"{response.title[:50]}.md"

    content_hash = hashlib.sha256(content.encode()).hexdigest()
    if _check_dedup(content_hash):
        return "Already ingested (duplicate content). Skipped."

    filename = _slugify(filename)
    (_raw() / filename).write_text(content, encoding="utf-8")
    db_index_raw(filename, url, content_hash)

    return content


@mcp.tool()
def ingest_text(name: str, content: str) -> str:
    """Save text content to raw/. Returns the content for compilation."""
    content_hash = hashlib.sha256(content.encode()).hexdigest()
    if _check_dedup(content_hash):
        return "Already ingested (duplicate content). Skipped."

    filename = _slugify(f"{name}.md")
    (_raw() / filename).write_text(content, encoding="utf-8")
    db_index_raw(filename, "", content_hash)

    return content


@mcp.tool()
def ingest_file(path: str) -> str:
    """Ingest a local file (PDF, epub, text). Returns the content for compilation."""
    file_path = Path(path)
    suffix = file_path.suffix.lower()

    if suffix == ".pdf":
        from wikinow.ingestion import extract_pdf

        response = extract_pdf(file_path)
        content = response.content
        title = response.title
    elif suffix == ".epub":
        from wikinow.ingestion import extract_epub

        response = extract_epub(file_path)
        content = response.content
        title = response.title
    elif suffix in (".mp3", ".wav", ".m4a", ".ogg", ".flac", ".webm"):
        from wikinow.ingestion import transcribe_audio, format_audio

        response = transcribe_audio(file_path)
        content = format_audio(response)
        title = response.title
    else:
        from wikinow.ingestion import read_text

        response = read_text(file_path)
        content = response.content
        title = response.title

    content_hash = hashlib.sha256(content.encode()).hexdigest()
    if _check_dedup(content_hash):
        return "Already ingested (duplicate content). Skipped."

    filename = _slugify(f"{title}.md")
    (_raw() / filename).write_text(content, encoding="utf-8")
    db_index_raw(filename, str(file_path), content_hash)

    return content


# ── Read / Write Tools ────────────────────────────────────────────────────


@mcp.tool()
def read(path: str) -> str:
    """Read a wiki article. Path relative to wiki/ (e.g. concepts/attention.md)."""
    wiki_root = str(_wiki().resolve()) + "/"
    file_path = (_wiki() / path).resolve()
    if not str(file_path).startswith(wiki_root):
        return f"Invalid path: {path}"
    if not file_path.exists():
        return f"Article not found: {path}"
    return file_path.read_text(encoding="utf-8")


@mcp.tool()
def write(path: str, content: str) -> str:
    """Create or update a wiki article. Path relative to wiki/ (e.g. concepts/attention.md)."""
    wiki_root = str(_wiki().resolve()) + "/"
    file_path = (_wiki() / path).resolve()
    if not str(file_path).startswith(wiki_root):
        return f"Invalid path: {path}"
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding="utf-8")
    return f"Written: {path}"


@mcp.tool()
def index_article(
    path: str,
    title: str,
    summary: str,
    tags: list[str],
    confidence: str,
    links: list[str],
    created: str = "",
    updated: str = "",
) -> str:
    """Index a wiki article in the database. Call after write()."""
    article_id = db_index_article(
        path, title, summary, tags, confidence, links, created, updated
    )
    return f"Indexed: {path} (id={article_id})"


@mcp.tool()
def index_raw(path: str, source_url: str, content_hash: str) -> str:
    """Index a raw source in the database."""
    raw_id = db_index_raw(path, source_url, content_hash)
    return f"Indexed raw: {path} (id={raw_id})"


@mcp.tool()
def mark_compiled(raw_path: str) -> str:
    """Mark a raw source as compiled into wiki articles."""
    db_mark_compiled(raw_path)
    return f"Marked compiled: {raw_path}"


# ── Search Tools ──────────────────────────────────────────────────────────


@mcp.tool()
def search(query: str, max_results: int = 10) -> list[dict]:
    """Search the wiki using FTS5 keyword search."""
    results = search_wiki(query, max_results)
    return [asdict(r) for r in results]


@mcp.tool()
def search_web(query: str, max_results: int = 5) -> list[dict]:
    """Search the web via Ollama API. Requires OLLAMA_API_KEY."""
    results = web_search(query, max_results)
    return [asdict(r) for r in results]


# ── List / Stats Tools ────────────────────────────────────────────────────


@mcp.tool()
def list_all_articles() -> list[dict]:
    """List all wiki articles with metadata."""
    return [asdict(a) for a in list_articles()]


@mcp.tool()
def list_all_raw() -> list[dict]:
    """List all raw sources with compiled status."""
    return [asdict(r) for r in list_raw()]


@mcp.tool()
def list_all_tags() -> list[dict]:
    """List all tags with article counts."""
    return [asdict(t) for t in list_tags()]


@mcp.tool()
def get_project_stats() -> dict:
    """Get project statistics and health score."""
    return asdict(get_stats())


@mcp.tool()
def get_all_contradictions() -> list[dict]:
    """Get articles with conflicting claims."""
    return [asdict(a) for a in get_contradictions()]


@mcp.tool()
def get_gaps() -> str:
    """Get knowledge gaps and open questions."""
    gaps_path = _wiki() / "gaps.md"
    if gaps_path.exists():
        return gaps_path.read_text(encoding="utf-8")
    return "No gaps file found."


# ── Lint Tools ────────────────────────────────────────────────────────────


@mcp.tool()
def lint() -> dict:
    """Health check — find issues in the wiki."""
    orphans = find_orphans()
    dead = find_dead_links()
    uncompiled = find_uncompiled()

    total_issues = len(orphans) + len(dead) + len(uncompiled)
    stats = get_stats()
    total_articles = stats.articles
    health = max(0, 100 - (total_issues * 5)) if total_articles > 0 else 100

    return {
        "health_score": health,
        "orphan_pages": [asdict(o) for o in orphans],
        "dead_links": [asdict(d) for d in dead],
        "uncompiled_sources": [asdict(u) for u in uncompiled],
    }


# ── Maintenance Tools ─────────────────────────────────────────────────────


@mcp.tool()
def append_log(entry: str) -> str:
    """Append an entry to wiki/log.md."""
    log_path = _wiki() / "log.md"
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"\n## [{_today()}] {entry}\n")
    return f"Logged: {entry}"


@mcp.tool()
def update_schema(section: str, content: str) -> str:
    """Update a section in CLAUDE.md. Used to co-evolve the schema."""
    claude_path = _project() / "CLAUDE.md"
    current = claude_path.read_text(encoding="utf-8")

    marker = f"## {section}"
    if marker in current:
        parts = current.split(marker, 1)
        before = parts[0]
        after_parts = parts[1].split("\n## ", 1)
        rest = f"\n## {after_parts[1]}" if len(after_parts) > 1 else ""
        new_content = f"{before}{marker}\n{content}\n{rest}"
    else:
        new_content = f"{current}\n{marker}\n{content}\n"

    claude_path.write_text(new_content, encoding="utf-8")
    return f"Updated schema section: {section}"


@mcp.tool()
def re_ingest(source: str) -> str:
    """Re-read a raw source from disk and return its content."""
    raw_path = _raw() / source
    if not raw_path.exists():
        return f"Source not found: {source}"

    return raw_path.read_text(encoding="utf-8")


# ── Export Tool ────────────────────────────────────────────────────────────


@mcp.tool()
def export() -> str:
    """Export the wiki as a single markdown file."""
    output = export_single()
    return f"Exported to: {output}"


# ── Run ───────────────────────────────────────────────────────────────────


def run() -> None:
    """Start the MCP server."""
    mcp.run()
