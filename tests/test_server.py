"""Tests for wikinow.server.

Verifies:
- 21 MCP tools registered
- Read/write with path traversal protection
- Ingest with dedup
- Index/compile operations
- Search returns dicts
- Stats/lint structure
- List tools (articles, raw, tags)
- Contradictions, gaps, re-ingest
- Maintenance tools (log, schema update, schema append, export)
- Slugify utility

Usage:
    pytest tests/test_server.py -v
"""

import asyncio

import pytest

import wikinow.server as server_mod
from wikinow.server import (
    mcp,
    read,
    write,
    index_article,
    mark_compiled,
    search,
    get_project_stats,
    get_all_contradictions,
    get_gaps,
    list_all_articles,
    list_all_raw,
    list_all_tags,
    lint,
    append_log,
    update_schema,
    re_ingest,
    export,
    ingest_text,
    _slugify,
)
from wikinow.db import init_storage, close_storage


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(autouse=True)
def project(tmp_path, monkeypatch):
    """Create a project structure and point server at it."""
    wiki = tmp_path / "wiki"
    for subdir in ["sources", "concepts", "comparisons", "queries"]:
        (wiki / subdir).mkdir(parents=True)
    (tmp_path / "raw").mkdir()

    # Write required files
    (wiki / "log.md").write_text("# Log\n", encoding="utf-8")
    (wiki / "gaps.md").write_text("# Gaps\n\n- Need more on X\n", encoding="utf-8")
    (wiki / "overview.md").write_text("# Overview\n", encoding="utf-8")
    (wiki / "index.md").write_text("# Index\n", encoding="utf-8")
    (tmp_path / "CLAUDE.md").write_text(
        "# WikiNow Schema\n\n## Tools\n\nTool list here\n\n## Rules\n\nRule list here\n",
        encoding="utf-8",
    )

    # Point server at our temp project
    monkeypatch.setattr(server_mod, "_project_path", tmp_path)
    monkeypatch.setattr("wikinow.export.get_project_path", lambda name=None: tmp_path)

    init_storage(tmp_path)
    yield tmp_path
    close_storage()


# =============================================================================
# Tool Registration
# =============================================================================


class TestToolRegistration:
    """Verify all 21 MCP tools are registered."""

    def test_21_tools_registered(self):
        tools = asyncio.run(mcp.list_tools())
        assert len(tools) == 21


# =============================================================================
# Read / Write
# =============================================================================


class TestReadWrite:
    """Verify read/write with path traversal protection."""

    def test_read_returns_content(self, project):
        (project / "wiki" / "concepts" / "ai.md").write_text(
            "# AI\n\nArtificial intelligence.", encoding="utf-8"
        )
        result = read("concepts/ai.md")
        assert "# AI" in result
        assert "Artificial intelligence." in result

    def test_read_path_traversal_dotdot(self, project):
        result = read("../../../etc/passwd")
        assert "Invalid path" in result

    def test_read_path_traversal_prefix_bypass(self, project):
        result = read("../wiki-evil/hack")
        assert "Invalid path" in result

    def test_read_nonexistent(self, project):
        result = read("concepts/nonexistent.md")
        assert "Article not found" in result

    def test_write_creates_file(self, project):
        result = write("concepts/new.md", "# New\n\nContent here.")
        assert "Written" in result
        assert (project / "wiki" / "concepts" / "new.md").exists()
        content = (project / "wiki" / "concepts" / "new.md").read_text(encoding="utf-8")
        assert "Content here." in content


# =============================================================================
# Write Security
# =============================================================================


class TestWriteSecurity:
    """Verify write path traversal protection."""

    def test_write_path_traversal_blocked(self, project):
        result = write("../../../tmp/hack", "pwned")
        assert "Invalid path" in result


# =============================================================================
# Ingest
# =============================================================================


class TestIngest:
    """Verify ingest text and dedup."""

    def test_ingest_text_saves_and_indexes(self, project):
        result = ingest_text("my notes", "Some important content here")
        assert "Some important content here" in result

        # File should exist in raw/
        raw_files = list((project / "raw").glob("*.md"))
        assert len(raw_files) == 1

    def test_ingest_text_dedup_skips(self, project):
        ingest_text("first", "Duplicate content test")
        result = ingest_text("second", "Duplicate content test")
        assert "Already ingested" in result

        # Only one file in raw/
        raw_files = list((project / "raw").glob("*.md"))
        assert len(raw_files) == 1

    def test_ingest_text_indexes_in_db(self, project):
        from wikinow.db import list_raw

        ingest_text("research paper", "Content about neural networks")
        sources = list_raw()
        assert len(sources) == 1
        assert not sources[0].compiled


# =============================================================================
# Index / Compile
# =============================================================================


class TestIndexCompile:
    """Verify index and mark_compiled operations."""

    def test_index_article_returns_id(self, project):
        result = index_article(
            "concepts/ai.md",
            "AI",
            "Artificial intelligence",
            ["ml"],
            "high",
            [],
        )
        assert "Indexed: concepts/ai.md" in result
        assert "id=" in result

    def test_mark_compiled_updates(self, project):
        from wikinow.db import index_raw

        index_raw("paper.pdf", "https://example.com", "hash123")
        result = mark_compiled("paper.pdf")
        assert "Marked compiled: paper.pdf" in result


# =============================================================================
# Search
# =============================================================================


class TestSearch:
    """Verify search returns dicts."""

    def test_search_returns_dicts(self, project):
        (project / "wiki" / "concepts" / "ai.md").write_text(
            "Machine learning is great", encoding="utf-8"
        )
        index_article("concepts/ai.md", "AI", "ML stuff", [], "high", [])
        results = search("machine learning")
        assert isinstance(results, list)
        assert len(results) > 0
        assert isinstance(results[0], dict)
        assert "title" in results[0]
        assert "path" in results[0]


# =============================================================================
# Stats / List
# =============================================================================


class TestStatsAndLint:
    """Verify stats and lint structure."""

    def test_get_project_stats_structure(self, project):
        stats = get_project_stats()
        assert isinstance(stats, dict)
        expected_keys = [
            "articles",
            "raw_sources",
            "raw_compiled",
            "raw_pending",
            "links",
            "tags",
            "contradictions",
        ]
        for key in expected_keys:
            assert key in stats

    def test_lint_returns_health_score(self, project):
        result = lint()
        assert isinstance(result, dict)
        assert "health_score" in result
        assert "orphan_pages" in result
        assert "dead_links" in result
        assert "uncompiled_sources" in result
        assert isinstance(result["health_score"], int)


# =============================================================================
# Maintenance
# =============================================================================


class TestMaintenance:
    """Verify log, schema, and export tools."""

    def test_append_log_adds_entry(self, project):
        result = append_log("Added new source on transformers")
        assert "Logged" in result

        log_content = (project / "wiki" / "log.md").read_text(encoding="utf-8")
        assert "Added new source on transformers" in log_content

    def test_update_schema_modifies_section(self, project):
        result = update_schema("Tools", "Updated tool list content")
        assert "Updated schema section: Tools" in result

        claude_content = (project / "CLAUDE.md").read_text(encoding="utf-8")
        assert "Updated tool list content" in claude_content

    def test_export_returns_path(self, project):
        result = export()
        assert "Exported to:" in result


# =============================================================================
# Utility
# =============================================================================


class TestSlugify:
    """Verify slugify utility."""

    def test_slugify_special_chars(self):
        assert _slugify("Hello World!") == "hello-world"

    def test_slugify_empty(self):
        assert _slugify("") == "source.md"


# =============================================================================
# List Tools
# =============================================================================


class TestListTools:
    """Verify list tools return dicts."""

    def test_list_all_articles_returns_dicts(self, project):
        index_article("concepts/ai.md", "AI", "Summary", [], "high", [])
        result = list_all_articles()
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["title"] == "AI"

    def test_list_all_raw_returns_dicts(self, project):
        ingest_text("notes", "Some content")
        result = list_all_raw()
        assert isinstance(result, list)
        assert len(result) == 1
        assert "path" in result[0]

    def test_list_all_tags_returns_dicts(self, project):
        index_article("a.md", "A", "", ["ml", "ai"], "", [])
        result = list_all_tags()
        assert isinstance(result, list)
        assert len(result) == 2
        assert "tag" in result[0]
        assert "count" in result[0]


# =============================================================================
# Contradictions
# =============================================================================


class TestContradictions:
    """Verify contradictions tool."""

    def test_get_all_contradictions_returns_conflict_articles(self, project):
        index_article("a.md", "Claim A", "", [], "conflict", [])
        index_article("b.md", "Claim B", "", [], "high", [])
        result = get_all_contradictions()
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["title"] == "Claim A"
        assert result[0]["confidence"] == "conflict"


# =============================================================================
# Gaps
# =============================================================================


class TestGaps:
    """Verify gaps tool."""

    def test_get_gaps_returns_content(self, project):
        result = get_gaps()
        assert "# Gaps" in result

    def test_get_gaps_missing_file(self, project):
        (project / "wiki" / "gaps.md").unlink()
        result = get_gaps()
        assert "No gaps file found" in result


# =============================================================================
# Re-Ingest
# =============================================================================


class TestReIngest:
    """Verify re_ingest tool."""

    def test_re_ingest_returns_content(self, project):
        (project / "raw" / "source.md").write_text("Original content", encoding="utf-8")
        result = re_ingest("source.md")
        assert result == "Original content"

    def test_re_ingest_not_found(self, project):
        result = re_ingest("nonexistent.md")
        assert "Source not found" in result


# =============================================================================
# Update Schema — New Section
# =============================================================================


class TestUpdateSchemaNewSection:
    """Verify update_schema appends when section doesn't exist."""

    def test_update_schema_appends_new_section(self, project):
        result = update_schema("New Section", "Brand new content")
        assert "Updated schema section: New Section" in result

        claude_content = (project / "CLAUDE.md").read_text(encoding="utf-8")
        assert "## New Section" in claude_content
        assert "Brand new content" in claude_content
