"""Tests for wikinow.export.

Verifies:
- Export creates file at correct path
- Export includes overview, index, and articles
- Empty directories are skipped
- UTF-8 content survives round-trip

Usage:
    pytest tests/test_export.py -v
"""

import pytest

from wikinow.export import export_single


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(autouse=True)
def isolated_project(tmp_path, monkeypatch):
    """Create a minimal project and redirect config to it."""
    project = tmp_path / ".wikinow" / "projects" / "test-proj"
    wiki = project / "wiki"
    for subdir in ["sources", "concepts", "comparisons", "queries"]:
        (wiki / subdir).mkdir(parents=True)
    (project / "raw").mkdir()

    (wiki / "overview.md").write_text(
        "# Overview\n\nProject overview.", encoding="utf-8"
    )
    (wiki / "index.md").write_text("# Index\n\n- [[concepts/ai.md]]", encoding="utf-8")

    monkeypatch.setattr("wikinow.export.get_project_path", lambda name=None: project)
    return project


# =============================================================================
# Core
# =============================================================================


class TestExportCore:
    """Verify export creates correct output file."""

    def test_export_creates_file(self, isolated_project):
        output = export_single()
        assert output.exists()
        assert output.name == "test-proj-export.md"

    def test_export_includes_overview(self, isolated_project):
        output = export_single()
        content = output.read_text(encoding="utf-8")
        assert "# Overview" in content

    def test_export_includes_index(self, isolated_project):
        output = export_single()
        content = output.read_text(encoding="utf-8")
        assert "# Index" in content

    def test_export_includes_articles(self, isolated_project):
        (isolated_project / "wiki" / "concepts" / "ai.md").write_text(
            "---\ntitle: AI\n---\nArtificial intelligence content.",
            encoding="utf-8",
        )
        output = export_single()
        content = output.read_text(encoding="utf-8")
        assert "Artificial intelligence content." in content
        assert "# Concepts" in content

    def test_export_skips_empty_dirs(self, isolated_project):
        output = export_single()
        content = output.read_text(encoding="utf-8")
        assert "# Sources" not in content
        assert "# Concepts" not in content

    def test_export_uses_utf8(self, isolated_project):
        (isolated_project / "wiki" / "concepts" / "unicode.md").write_text(
            "# Ünïcödé\n\nCafé résumé naïve",
            encoding="utf-8",
        )
        output = export_single()
        content = output.read_text(encoding="utf-8")
        assert "Ünïcödé" in content
        assert "Café résumé naïve" in content
