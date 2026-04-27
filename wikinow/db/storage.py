"""WikiNow storage — self-healing SQLite cache over .md files."""

import hashlib
import os
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import yaml

from wikinow.db.schemas import ALL_TABLES, CREATE_INDEXES


# ── Regex ─────────────────────────────────────────────────────────────────

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_WIKILINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]*)?\]\]")


# ── Dataclasses ───────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Article:
    """Wiki article metadata."""

    path: str
    title: str
    summary: str
    confidence: str
    created: str
    updated: str


@dataclass(frozen=True)
class RawSource:
    """Raw source metadata."""

    path: str
    source_url: str
    content_hash: str
    compiled: int
    ingested_at: str


@dataclass(frozen=True)
class SearchResult:
    """FTS5 search result."""

    path: str
    title: str
    summary: str
    confidence: str
    rank: float


@dataclass(frozen=True)
class TagCount:
    """Tag with article count."""

    tag: str
    count: int


@dataclass(frozen=True)
class DeadLink:
    """Wikilink pointing to nonexistent article."""

    target_path: str
    source_path: str


@dataclass(frozen=True)
class Stats:
    """Project statistics."""

    articles: int
    raw_sources: int
    raw_compiled: int
    raw_pending: int
    links: int
    tags: int
    contradictions: int


# ── Parsers (self-healing) ────────────────────────────────────────────────


def _parse_frontmatter(content: str) -> dict:
    """Extract YAML frontmatter from markdown content."""
    match = _FRONTMATTER_RE.match(content)
    if not match:
        return {}
    try:
        return yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError:
        return {}


def _extract_wikilinks(content: str) -> list[str]:
    """Extract [[wikilink]] targets from markdown content."""
    return _WIKILINK_RE.findall(content)


def _strip_frontmatter(content: str) -> str:
    """Return content without YAML frontmatter."""
    match = _FRONTMATTER_RE.match(content)
    if not match:
        return content
    return content[match.end() :]


def _now() -> str:
    """Current UTC timestamp as ISO string."""
    return datetime.now(timezone.utc).isoformat()


# ── Storage Manager ───────────────────────────────────────────────────────


class _StorageManager:
    """Internal SQLite connection and operations manager."""

    def __init__(self, project_path: Path) -> None:
        self._project = project_path
        self._wiki = project_path / "wiki"
        self._raw_dir = project_path / "raw"
        self._conn = sqlite3.connect(str(project_path / "wikinow.db"))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.execute("PRAGMA journal_mode = WAL")
        self._create_tables()
        self._sync()

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()

    # ── Schema ────────────────────────────────────────────────────────────

    def _create_tables(self) -> None:
        for sql in ALL_TABLES:
            self._conn.execute(sql)
        for sql in CREATE_INDEXES:
            self._conn.execute(sql)
        self._conn.commit()

    # ── Write ─────────────────────────────────────────────────────────────

    def index_article(
        self,
        path: str,
        title: str,
        summary: str,
        tags: list[str],
        confidence: str,
        links: list[str],
        created: str = "",
        updated: str = "",
    ) -> int:
        now = _now()
        created = created or now
        updated = updated or now

        file_path = self._wiki / path
        content = ""
        if file_path.exists():
            content = _strip_frontmatter(file_path.read_text(encoding="utf-8"))

        self._conn.execute(
            """INSERT INTO articles (path, title, summary, confidence, created, updated, indexed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(path) DO UPDATE SET
                title=excluded.title, summary=excluded.summary,
                confidence=excluded.confidence, updated=excluded.updated,
                indexed_at=excluded.indexed_at""",
            (path, title, summary, confidence, created, updated, now),
        )
        article_id = self._conn.execute(
            "SELECT id FROM articles WHERE path = ?", (path,)
        ).fetchone()["id"]

        self._conn.execute("DELETE FROM fts WHERE rowid = ?", (article_id,))
        self._conn.execute(
            "INSERT INTO fts (rowid, title, content) VALUES (?, ?, ?)",
            (article_id, title, content),
        )

        self._conn.execute("DELETE FROM tags WHERE article_id = ?", (article_id,))
        for tag in tags:
            self._conn.execute(
                "INSERT INTO tags (article_id, tag) VALUES (?, ?)",
                (article_id, tag),
            )

        self._conn.execute("DELETE FROM links WHERE source_id = ?", (article_id,))
        for target in links:
            self._conn.execute(
                "INSERT INTO links (source_id, target_path) VALUES (?, ?)",
                (article_id, target),
            )

        self._conn.commit()
        return article_id

    def index_raw(self, path: str, source_url: str, content_hash: str) -> int:
        now = _now()
        self._conn.execute(
            """INSERT INTO raw (path, source_url, content_hash, ingested_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(path) DO UPDATE SET
                source_url=excluded.source_url, content_hash=excluded.content_hash""",
            (path, source_url, content_hash, now),
        )
        self._conn.commit()
        return self._conn.execute(
            "SELECT id FROM raw WHERE path = ?", (path,)
        ).fetchone()["id"]

    def mark_compiled(self, raw_path: str) -> None:
        self._conn.execute(
            "UPDATE raw SET compiled = 1, compiled_at = ? WHERE path = ?",
            (_now(), raw_path),
        )
        self._conn.commit()

    # ── Read ──────────────────────────────────────────────────────────────

    def search(self, query: str, max_results: int = 10) -> list[SearchResult]:
        safe_query = '"' + query.replace('"', '""') + '"'
        try:
            rows = self._conn.execute(
                """SELECT a.path, a.title, a.summary, a.confidence, rank
                   FROM fts f
                   JOIN articles a ON a.id = f.rowid
                   WHERE fts MATCH ?
                   ORDER BY rank
                   LIMIT ?""",
                (safe_query, max_results),
            ).fetchall()
        except Exception:
            return []
        return [SearchResult(**dict(r)) for r in rows]

    def list_articles(self) -> list[Article]:
        rows = self._conn.execute(
            "SELECT path, title, summary, confidence, created, updated FROM articles ORDER BY updated DESC"
        ).fetchall()
        return [Article(**dict(r)) for r in rows]

    def list_raw(self) -> list[RawSource]:
        rows = self._conn.execute(
            "SELECT path, source_url, content_hash, compiled, ingested_at FROM raw ORDER BY ingested_at DESC"
        ).fetchall()
        return [RawSource(**dict(r)) for r in rows]

    def list_tags(self) -> list[TagCount]:
        rows = self._conn.execute(
            "SELECT tag, COUNT(*) as count FROM tags GROUP BY tag ORDER BY count DESC"
        ).fetchall()
        return [TagCount(**dict(r)) for r in rows]

    def get_stats(self) -> Stats:
        return Stats(
            articles=self._count("articles"),
            raw_sources=self._count("raw"),
            raw_compiled=self._count("raw", "compiled = 1"),
            raw_pending=self._count("raw", "compiled = 0"),
            links=self._count("links"),
            tags=self._count("tags", distinct="tag"),
            contradictions=self._count("articles", "confidence = 'conflict'"),
        )

    def get_contradictions(self) -> list[Article]:
        rows = self._conn.execute(
            "SELECT path, title, summary, confidence, created, updated FROM articles WHERE confidence = 'conflict'"
        ).fetchall()
        return [Article(**dict(r)) for r in rows]

    # ── Lint ──────────────────────────────────────────────────────────────

    def find_orphans(self) -> list[Article]:
        rows = self._conn.execute(
            """SELECT a.path, a.title, a.summary, a.confidence, a.created, a.updated
               FROM articles a
               WHERE a.path NOT IN (SELECT target_path FROM links)"""
        ).fetchall()
        return [Article(**dict(r)) for r in rows]

    def find_dead_links(self) -> list[DeadLink]:
        rows = self._conn.execute(
            """SELECT DISTINCT l.target_path, a.path as source_path
               FROM links l
               JOIN articles a ON a.id = l.source_id
               WHERE l.target_path NOT IN (SELECT path FROM articles)"""
        ).fetchall()
        return [DeadLink(**dict(r)) for r in rows]

    def find_uncompiled(self) -> list[RawSource]:
        rows = self._conn.execute(
            "SELECT path, source_url, content_hash, compiled, ingested_at FROM raw WHERE compiled = 0"
        ).fetchall()
        return [RawSource(**dict(r)) for r in rows]

    # ── Self-Healing ──────────────────────────────────────────────────────

    def _sync(self) -> None:
        self._sync_articles()
        self._sync_raw()

    def _sync_articles(self) -> None:
        wiki_dirs = ["sources", "concepts", "comparisons", "queries"]
        disk_paths: set[str] = set()

        for subdir in wiki_dirs:
            folder = self._wiki / subdir
            if not folder.exists():
                continue
            for md_file in folder.glob("*.md"):
                rel = f"{subdir}/{md_file.name}"
                disk_paths.add(rel)
                self._sync_one_article(rel, md_file)

        db_paths = {
            r["path"]
            for r in self._conn.execute("SELECT path FROM articles").fetchall()
        }
        for deleted in db_paths - disk_paths:
            article = self._conn.execute(
                "SELECT id FROM articles WHERE path = ?", (deleted,)
            ).fetchone()
            if article:
                self._conn.execute(
                    "DELETE FROM articles WHERE id = ?", (article["id"],)
                )
                self._conn.execute("DELETE FROM fts WHERE rowid = ?", (article["id"],))
        self._conn.commit()

    def _sync_one_article(self, rel_path: str, file_path: Path) -> None:
        row = self._conn.execute(
            "SELECT indexed_at FROM articles WHERE path = ?", (rel_path,)
        ).fetchone()

        file_mtime = datetime.fromtimestamp(
            os.path.getmtime(file_path), tz=timezone.utc
        ).isoformat()

        if row and row["indexed_at"] >= file_mtime:
            return

        content = file_path.read_text(encoding="utf-8")
        fm = _parse_frontmatter(content)
        body = _strip_frontmatter(content)
        links = _extract_wikilinks(content)
        first_line = body.strip().split("\n")[0] if body.strip() else ""

        self.index_article(
            path=rel_path,
            title=fm.get("title") or file_path.stem.replace("-", " ").title(),
            summary=fm.get("summary") or first_line,
            tags=fm.get("tags") or [],
            confidence=fm.get("confidence") or "",
            links=links,
            created=str(fm.get("created") or ""),
            updated=str(fm.get("updated") or ""),
        )

    def _sync_raw(self) -> None:
        if not self._raw_dir.exists():
            return

        disk_paths: set[str] = set()
        for f in self._raw_dir.iterdir():
            if f.is_file() and not f.name.startswith("."):
                rel = f.name
                disk_paths.add(rel)

                if not self._conn.execute(
                    "SELECT id FROM raw WHERE path = ?", (rel,)
                ).fetchone():
                    content_hash = hashlib.sha256(f.read_bytes()).hexdigest()
                    compiled = (self._wiki / "sources" / f"{f.stem}.md").exists()
                    mtime = datetime.fromtimestamp(
                        os.path.getmtime(f), tz=timezone.utc
                    ).isoformat()
                    self._conn.execute(
                        """INSERT INTO raw (path, content_hash, compiled, ingested_at)
                        VALUES (?, ?, ?, ?)""",
                        (rel, content_hash, int(compiled), mtime),
                    )

        db_paths = {
            r["path"] for r in self._conn.execute("SELECT path FROM raw").fetchall()
        }
        for deleted in db_paths - disk_paths:
            self._conn.execute("DELETE FROM raw WHERE path = ?", (deleted,))

        self._conn.commit()

    # ── Helpers ────────────────────────────────────────────────────────────

    _VALID_TABLES = {"articles", "raw", "links", "tags"}
    _VALID_COLUMNS = {"tag", "*"}

    def _count(self, table: str, where: str = "", distinct: str = "") -> int:
        if table not in self._VALID_TABLES:
            raise ValueError(f"Invalid table: {table}")
        if distinct and distinct not in self._VALID_COLUMNS:
            raise ValueError(f"Invalid column: {distinct}")
        col = f"DISTINCT {distinct}" if distinct else "*"
        sql = f"SELECT COUNT({col}) as c FROM {table}"
        if where:
            sql += f" WHERE {where}"
        return self._conn.execute(sql).fetchone()["c"]


# ── Module-level singleton ────────────────────────────────────────────────

_manager: _StorageManager | None = None


def _get_manager() -> _StorageManager:
    """Get or create the StorageManager singleton."""
    global _manager
    if _manager is None:
        from wikinow.config import get_project_path

        _manager = _StorageManager(get_project_path())
    return _manager


def init_storage(project_path: Path) -> None:
    """Initialize storage for a specific project path."""
    global _manager
    if _manager is not None and _manager._project != project_path:
        _manager.close()
        _manager = None
    if _manager is None:
        _manager = _StorageManager(project_path)


def close_storage() -> None:
    """Close the storage connection."""
    global _manager
    if _manager:
        _manager.close()
        _manager = None


# ── Public accessors ──────────────────────────────────────────────────────


def index_article(
    path: str,
    title: str,
    summary: str,
    tags: list[str],
    confidence: str,
    links: list[str],
    created: str = "",
    updated: str = "",
) -> int:
    """Index a wiki article in the database."""
    return _get_manager().index_article(
        path, title, summary, tags, confidence, links, created, updated
    )


def index_raw(path: str, source_url: str, content_hash: str) -> int:
    """Index a raw source in the database."""
    return _get_manager().index_raw(path, source_url, content_hash)


def mark_compiled(raw_path: str) -> None:
    """Mark a raw source as compiled."""
    _get_manager().mark_compiled(raw_path)


def search(query: str, max_results: int = 10) -> list[SearchResult]:
    """FTS5 keyword search."""
    return _get_manager().search(query, max_results)


def list_articles() -> list[Article]:
    """List all wiki articles."""
    return _get_manager().list_articles()


def list_raw() -> list[RawSource]:
    """List all raw sources."""
    return _get_manager().list_raw()


def list_tags() -> list[TagCount]:
    """List all tags with counts."""
    return _get_manager().list_tags()


def get_stats() -> Stats:
    """Get project statistics."""
    return _get_manager().get_stats()


def get_contradictions() -> list[Article]:
    """Get articles with conflicting claims."""
    return _get_manager().get_contradictions()


def find_orphans() -> list[Article]:
    """Find articles with no inbound links."""
    return _get_manager().find_orphans()


def find_dead_links() -> list[DeadLink]:
    """Find wikilinks pointing to nonexistent articles."""
    return _get_manager().find_dead_links()


def find_uncompiled() -> list[RawSource]:
    """Find raw sources not yet compiled."""
    return _get_manager().find_uncompiled()


def has_content_hash(content_hash: str) -> bool:
    """Check if a content hash already exists in raw sources."""
    row = (
        _get_manager()
        ._conn.execute("SELECT id FROM raw WHERE content_hash = ?", (content_hash,))
        .fetchone()
    )
    return row is not None
