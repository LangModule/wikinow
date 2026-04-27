"""Tests for wikinow.templates.

Verifies:
- Schema contains all 21 MCP tool names and key sections
- Wiki file templates have correct headers and content
- Obsidian config files are valid JSON with correct settings

Usage:
    pytest tests/test_templates.py -v
"""

import json

import pytest

from wikinow import templates


# =============================================================================
# Schema Content
# =============================================================================


class TestSchemaContent:
    """Verify CLAUDE.md schema contains all required sections and tool names."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.schema = templates.schema("test-project")

    def test_schema_contains_all_21_tools(self):
        tool_names = [
            "ingest_url",
            "ingest_text",
            "ingest_file",
            "read",
            "write",
            "index_article",
            "index_raw",
            "mark_compiled",
            "search",
            "search_web",
            "list_all_articles",
            "list_all_raw",
            "list_all_tags",
            "get_project_stats",
            "get_all_contradictions",
            "get_gaps",
            "lint",
            "append_log",
            "update_schema",
            "re_ingest",
            "export",
        ]
        for tool in tool_names:
            assert tool in self.schema, f"Missing tool in schema: {tool}"

    def test_schema_contains_project_name(self):
        assert "# WikiNow Schema — test-project" in self.schema

    def test_schema_contains_frontmatter_block(self):
        assert "title: Page Title" in self.schema
        assert "tags: [tag1, tag2]" in self.schema
        assert "confidence: high | medium | low | conflict" in self.schema
        assert "created: YYYY-MM-DD" in self.schema

    def test_schema_contains_confidence_levels(self):
        assert "**high**" in self.schema
        assert "**medium**" in self.schema
        assert "**low**" in self.schema
        assert "**conflict**" in self.schema

    def test_schema_contains_13_ingest_steps(self):
        assert "1. Read wiki/index.md" in self.schema
        assert "13. When you're done processing" in self.schema


# =============================================================================
# Wiki Files
# =============================================================================


class TestWikiFiles:
    """Verify wiki file templates have correct headers and references."""

    def test_index_has_4_categories(self):
        content = templates.index("test")
        assert "## Sources" in content
        assert "## Concepts" in content
        assert "## Comparisons" in content
        assert "## Queries" in content

    def test_log_mentions_append_log(self):
        content = templates.log("test")
        assert "append_log()" in content


# =============================================================================
# Obsidian Config
# =============================================================================


class TestObsidianConfig:
    """Verify Obsidian config files are valid JSON with correct settings."""

    def test_obsidian_app_is_valid_json(self):
        data = json.loads(templates.obsidian_app())
        assert isinstance(data, dict)

    def test_obsidian_app_uses_wikilinks(self):
        data = json.loads(templates.obsidian_app())
        assert data["useMarkdownLinks"] is False
        assert data["newLinkFormat"] == "shortest"

    def test_obsidian_hotkeys_is_valid_json(self):
        data = json.loads(templates.obsidian_hotkeys())
        assert "editor:download-attachments" in data

    def test_obsidian_core_plugins_has_8(self):
        plugins = json.loads(templates.obsidian_core_plugins())
        assert len(plugins) == 8
        assert "graph" in plugins
        assert "backlink" in plugins


# =============================================================================
# Sanity
# =============================================================================


class TestSanity:
    """Verify all template functions return non-empty strings."""

    def test_all_templates_return_nonempty(self):
        funcs_with_name = [
            templates.schema,
            templates.index,
            templates.overview,
            templates.log,
            templates.contradictions,
            templates.gaps,
            templates.tags,
        ]
        for fn in funcs_with_name:
            assert len(fn("test")) > 0, f"{fn.__name__} returned empty"

        funcs_no_args = [
            templates.obsidian_app,
            templates.obsidian_hotkeys,
            templates.obsidian_core_plugins,
        ]
        for fn in funcs_no_args:
            assert len(fn()) > 0, f"{fn.__name__} returned empty"
