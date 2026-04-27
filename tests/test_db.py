"""Tests for wikinow.db (schemas + storage).

Verifies:
- Schema creation (tables, FTS5, indexes, constraints)
- CRUD operations (index article/raw, mark compiled)
- Search (FTS5, porter stemming)
- List/stats queries
- Lint queries (orphans, dead links, uncompiled)
- Dedup (content hash)
- Self-healing (new, changed, deleted files)
- Cascade deletes
- Security (table/column whitelists)

Usage:
    pytest tests/test_db.py -v
"""

import sqlite3
import time

import pytest

from wikinow.db.schemas import ALL_TABLES, CREATE_INDEXES, CREATE_RAW
from wikinow.db.storage import (
    SearchResult,
    Stats,
    _StorageManager,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def project(tmp_path):
    """Create a minimal project structure for storage tests."""
    wiki = tmp_path / "wiki"
    for subdir in ["sources", "concepts", "comparisons", "queries"]:
        (wiki / subdir).mkdir(parents=True)
    (tmp_path / "raw").mkdir()
    return tmp_path


@pytest.fixture
def db(project):
    """Create a StorageManager connected to a temp project."""
    mgr = _StorageManager(project)
    yield mgr
    mgr.close()


# =============================================================================
# Schema Creation
# =============================================================================


class TestSchemaCreation:
    """Verify SQLite schema creates correctly."""

    def test_all_tables_create(self, tmp_path):
        conn = sqlite3.connect(str(tmp_path / "test.db"))
        for sql in ALL_TABLES:
            conn.execute(sql)
        conn.commit()

        tables = [
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' OR type='view'"
            ).fetchall()
        ]
        conn.close()

        assert "articles" in tables
        assert "links" in tables
        assert "tags" in tables
        assert "raw" in tables

    def test_fts5_with_porter_tokenizer(self, tmp_path):
        conn = sqlite3.connect(str(tmp_path / "test.db"))
        for sql in ALL_TABLES:
            conn.execute(sql)
        conn.commit()

        conn.execute(
            "INSERT INTO fts (rowid, title, content) VALUES (1, 'test', 'transformers architecture')"
        )
        results = conn.execute(
            "SELECT * FROM fts WHERE fts MATCH 'transformer'"
        ).fetchall()
        conn.close()

        assert len(results) == 1

    def test_indexes_create(self, tmp_path):
        conn = sqlite3.connect(str(tmp_path / "test.db"))
        for sql in ALL_TABLES:
            conn.execute(sql)
        for sql in CREATE_INDEXES:
            conn.execute(sql)
        conn.commit()

        indexes = [
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'"
            ).fetchall()
        ]
        conn.close()

        assert len(indexes) == 5

    def test_raw_content_hash_not_null(self, tmp_path):
        conn = sqlite3.connect(str(tmp_path / "test.db"))
        conn.execute(CREATE_RAW)
        conn.commit()

        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO raw (path, ingested_at) VALUES ('test.md', '2026-01-01')"
            )
        conn.close()

    def test_foreign_key_references_valid(self, db):
        article_id = db.index_article("concepts/test.md", "Test", "", [], "", [])
        db._conn.execute(
            "INSERT INTO tags (article_id, tag) VALUES (?, ?)", (article_id, "test")
        )
        db._conn.commit()

        tags = db._conn.execute(
            "SELECT tag FROM tags WHERE article_id = ?", (article_id,)
        ).fetchall()
        assert len(tags) == 1


# =============================================================================
# Index Article
# =============================================================================


class TestIndexArticle:
    """Verify article indexing CRUD operations."""

    def test_index_article_inserts(self, db):
        db.index_article(
            "concepts/ai.md", "AI", "Artificial intelligence", ["ml"], "high", []
        )
        articles = db.list_articles()
        assert len(articles) == 1
        assert articles[0].title == "AI"

    def test_index_article_upserts(self, db):
        db.index_article("concepts/ai.md", "AI v1", "Old", [], "", [])
        db.index_article("concepts/ai.md", "AI v2", "New", [], "", [])
        articles = db.list_articles()
        assert len(articles) == 1
        assert articles[0].title == "AI v2"
        assert articles[0].summary == "New"

    def test_index_article_stores_fts(self, db, project):
        (project / "wiki" / "concepts" / "transformers.md").write_text(
            "---\ntitle: Transformers\n---\nSelf-attention architecture",
            encoding="utf-8",
        )
        db.index_article("concepts/transformers.md", "Transformers", "", [], "", [])
        results = db.search("attention")
        assert len(results) == 1
        assert results[0].title == "Transformers"

    def test_index_article_stores_tags(self, db):
        db.index_article("concepts/ai.md", "AI", "", ["ml", "deep-learning"], "", [])
        tags = db.list_tags()
        assert len(tags) == 2
        tag_names = {t.tag for t in tags}
        assert tag_names == {"ml", "deep-learning"}

    def test_index_article_stores_links(self, db):
        db.index_article(
            "concepts/ai.md", "AI", "", [], "", ["concepts/ml.md", "concepts/nn.md"]
        )
        dead = db.find_dead_links()
        assert len(dead) == 2
        targets = {d.target_path for d in dead}
        assert targets == {"concepts/ml.md", "concepts/nn.md"}

    def test_index_article_accepts_dates(self, db):
        db.index_article(
            "concepts/ai.md",
            "AI",
            "",
            [],
            "",
            [],
            created="2026-01-01",
            updated="2026-04-25",
        )
        articles = db.list_articles()
        assert articles[0].created == "2026-01-01"
        assert articles[0].updated == "2026-04-25"

    def test_index_article_defaults_dates(self, db):
        db.index_article("concepts/ai.md", "AI", "", [], "", [])
        articles = db.list_articles()
        assert articles[0].created != ""
        assert articles[0].updated != ""
        assert "T" in articles[0].created


# =============================================================================
# Index Raw
# =============================================================================


class TestIndexRaw:
    """Verify raw source indexing and compilation tracking."""

    def test_index_raw_inserts(self, db):
        db.index_raw("paper.pdf", "https://arxiv.org/abs/123", "hash123")
        sources = db.list_raw()
        assert len(sources) == 1
        assert sources[0].path == "paper.pdf"
        assert sources[0].source_url == "https://arxiv.org/abs/123"

    def test_index_raw_upserts(self, db):
        db.index_raw("paper.pdf", "url-v1", "hash1")
        db.index_raw("paper.pdf", "url-v2", "hash2")
        sources = db.list_raw()
        assert len(sources) == 1
        assert sources[0].source_url == "url-v2"

    def test_mark_compiled_sets_flag(self, db):
        db.index_raw("paper.pdf", "", "hash123")
        assert len(db.find_uncompiled()) == 1

        db.mark_compiled("paper.pdf")
        assert len(db.find_uncompiled()) == 0


# =============================================================================
# Search
# =============================================================================


class TestSearch:
    """Verify FTS5 search functionality."""

    def test_search_returns_results(self, db, project):
        (project / "wiki" / "concepts" / "ai.md").write_text(
            "Machine learning is a subset of AI", encoding="utf-8"
        )
        db.index_article(
            "concepts/ai.md", "AI", "Artificial intelligence", [], "high", []
        )
        results = db.search("machine learning")
        assert len(results) == 1
        assert isinstance(results[0], SearchResult)

    def test_search_empty_for_no_match(self, db):
        db.index_article("concepts/ai.md", "AI", "", [], "", [])
        results = db.search("quantum physics")
        assert results == []

    def test_search_porter_stemming(self, db, project):
        (project / "wiki" / "concepts" / "t.md").write_text(
            "The transformer architecture uses attention", encoding="utf-8"
        )
        db.index_article("concepts/t.md", "Transformer", "", [], "", [])

        assert len(db.search("transformers")) == 1
        assert len(db.search("transformer")) == 1


# =============================================================================
# List / Stats
# =============================================================================


class TestListAndStats:
    """Verify listing and statistics queries."""

    def test_list_articles_sorted_by_updated(self, db):
        db.index_article("a.md", "First", "", [], "", [], updated="2026-01-01")
        db.index_article("b.md", "Second", "", [], "", [], updated="2026-04-01")
        articles = db.list_articles()
        assert articles[0].title == "Second"
        assert articles[1].title == "First"

    def test_list_raw_sorted_by_ingested(self, db):
        db.index_raw("old.pdf", "", "h1")
        time.sleep(0.01)
        db.index_raw("new.pdf", "", "h2")
        sources = db.list_raw()
        assert sources[0].path == "new.pdf"

    def test_list_tags_grouped_counts(self, db):
        db.index_article("a.md", "A", "", ["ml", "ai"], "", [])
        db.index_article("b.md", "B", "", ["ml"], "", [])
        tags = db.list_tags()
        ml_tag = next(t for t in tags if t.tag == "ml")
        assert ml_tag.count == 2

    def test_get_stats_all_fields(self, db):
        db.index_article("a.md", "A", "", ["ml"], "high", ["b.md"])
        db.index_raw("paper.pdf", "", "h1")
        db.mark_compiled("paper.pdf")
        db.index_raw("pending.pdf", "", "h2")

        stats = db.get_stats()
        assert isinstance(stats, Stats)
        assert stats.articles == 1
        assert stats.raw_sources == 2
        assert stats.raw_compiled == 1
        assert stats.raw_pending == 1
        assert stats.links == 1
        assert stats.tags == 1
        assert stats.contradictions == 0


# =============================================================================
# Lint
# =============================================================================


class TestLint:
    """Verify lint queries find issues correctly."""

    def test_find_orphans(self, db):
        db.index_article("concepts/orphan.md", "Orphan", "", [], "", [])
        orphans = db.find_orphans()
        assert len(orphans) == 1
        assert orphans[0].path == "concepts/orphan.md"

    def test_find_dead_links(self, db):
        db.index_article("a.md", "A", "", [], "", ["concepts/nonexistent.md"])
        dead = db.find_dead_links()
        assert len(dead) == 1
        assert dead[0].target_path == "concepts/nonexistent.md"
        assert dead[0].source_path == "a.md"

    def test_find_uncompiled(self, db):
        db.index_raw("uncompiled.pdf", "", "hash1")
        uncompiled = db.find_uncompiled()
        assert len(uncompiled) == 1
        assert uncompiled[0].path == "uncompiled.pdf"


# =============================================================================
# Dedup
# =============================================================================


class TestDedup:
    """Verify content hash deduplication."""

    def test_has_content_hash_true(self, db, monkeypatch):
        db.index_raw("test.pdf", "", "abc123")
        from wikinow.db.storage import has_content_hash

        monkeypatch.setattr("wikinow.db.storage._manager", db)
        assert has_content_hash("abc123") is True

    def test_has_content_hash_false(self, db, monkeypatch):
        from wikinow.db.storage import has_content_hash

        monkeypatch.setattr("wikinow.db.storage._manager", db)
        assert has_content_hash("nonexistent") is False


# =============================================================================
# Self-Healing
# =============================================================================


class TestSelfHealing:
    """Verify DB auto-syncs with filesystem on startup."""

    def test_sync_new_article(self, project):
        (project / "wiki" / "concepts" / "new.md").write_text(
            "---\ntitle: New Page\ntags: [test]\nconfidence: high\n"
            "created: 2026-04-25\nupdated: 2026-04-25\n---\nContent here",
            encoding="utf-8",
        )
        mgr = _StorageManager(project)
        articles = mgr.list_articles()
        mgr.close()

        assert len(articles) == 1
        assert articles[0].title == "New Page"

    def test_sync_changed_article(self, project):
        md_path = project / "wiki" / "concepts" / "changing.md"
        md_path.write_text("---\ntitle: Version 1\n---\nOld content", encoding="utf-8")

        mgr = _StorageManager(project)
        assert mgr.list_articles()[0].title == "Version 1"
        mgr.close()

        time.sleep(0.1)
        md_path.write_text("---\ntitle: Version 2\n---\nNew content", encoding="utf-8")

        mgr2 = _StorageManager(project)
        assert mgr2.list_articles()[0].title == "Version 2"
        mgr2.close()

    def test_sync_deleted_article(self, project):
        md_path = project / "wiki" / "concepts" / "temp.md"
        md_path.write_text("---\ntitle: Temp\n---\nContent", encoding="utf-8")

        mgr = _StorageManager(project)
        assert len(mgr.list_articles()) == 1
        mgr.close()

        md_path.unlink()

        mgr2 = _StorageManager(project)
        assert len(mgr2.list_articles()) == 0
        mgr2.close()

    def test_sync_new_raw(self, project):
        (project / "raw" / "source.md").write_text("Some content", encoding="utf-8")

        mgr = _StorageManager(project)
        sources = mgr.list_raw()
        mgr.close()

        assert len(sources) == 1
        assert sources[0].path == "source.md"

    def test_sync_deleted_raw(self, project):
        raw_path = project / "raw" / "temp.md"
        raw_path.write_text("Content", encoding="utf-8")

        mgr = _StorageManager(project)
        assert len(mgr.list_raw()) == 1
        mgr.close()

        raw_path.unlink()

        mgr2 = _StorageManager(project)
        assert len(mgr2.list_raw()) == 0
        mgr2.close()


# =============================================================================
# Cascade
# =============================================================================


class TestCascade:
    """Verify CASCADE delete removes child records."""

    def test_cascade_delete_removes_tags(self, db):
        aid = db.index_article("a.md", "A", "", ["ml", "ai"], "", [])
        assert len(db.list_tags()) == 2

        db._conn.execute("PRAGMA foreign_keys = ON")
        db._conn.execute("DELETE FROM articles WHERE id = ?", (aid,))
        db._conn.commit()

        assert len(db.list_tags()) == 0

    def test_cascade_delete_removes_links(self, db):
        aid = db.index_article("a.md", "A", "", [], "", ["b.md", "c.md"])
        dead = db.find_dead_links()
        assert len(dead) == 2

        db._conn.execute("PRAGMA foreign_keys = ON")
        db._conn.execute("DELETE FROM articles WHERE id = ?", (aid,))
        db._conn.commit()

        assert len(db.find_dead_links()) == 0


# =============================================================================
# Contradictions
# =============================================================================


class TestContradictions:
    """Verify contradictions query."""

    def test_get_contradictions_returns_conflict_articles(self, db):
        db.index_article("a.md", "Normal", "", [], "high", [])
        db.index_article("b.md", "Conflicting", "", [], "conflict", [])
        result = db.get_contradictions()
        assert len(result) == 1
        assert result[0].title == "Conflicting"
        assert result[0].confidence == "conflict"

    def test_get_contradictions_empty_when_none(self, db):
        db.index_article("a.md", "A", "", [], "high", [])
        assert db.get_contradictions() == []


# =============================================================================
# Security
# =============================================================================


class TestSecurity:
    """Verify SQL injection protections."""

    def test_invalid_table_raises(self, db):
        with pytest.raises(ValueError, match="Invalid table"):
            db._count("; DROP TABLE articles; --")

    def test_invalid_column_raises(self, db):
        with pytest.raises(ValueError, match="Invalid column"):
            db._count("articles", distinct="; DROP TABLE articles; --")
