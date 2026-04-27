"""Tests for wikinow.project.

Verifies:
- Project init creates correct directory structure, files, and symlinks
- Name validation rejects invalid names
- Switch and list operations
- Error handling for duplicates and nonexistent projects

Usage:
    pytest tests/test_project.py -v
"""

import os

import pytest

from wikinow.project import init_project, switch_project, list_projects


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(autouse=True)
def isolated_wikinow(tmp_path, monkeypatch):
    """Redirect WIKINOW_DIR to a temp directory for every test."""
    test_dir = tmp_path / ".wikinow"
    monkeypatch.setattr("wikinow.config.WIKINOW_DIR", test_dir)
    monkeypatch.setattr("wikinow.config.CONFIG_PATH", test_dir / "config.yaml")
    monkeypatch.setattr("wikinow.config._manager", None)
    monkeypatch.setattr("wikinow.project.WIKINOW_DIR", test_dir)
    yield test_dir


# =============================================================================
# Init — Structure
# =============================================================================


class TestInitStructure:
    """Verify init_project creates the complete project structure."""

    def test_init_creates_8_directories(self, isolated_wikinow):
        path = init_project("test")
        expected_dirs = [
            "raw",
            "wiki/sources",
            "wiki/concepts",
            "wiki/comparisons",
            "wiki/queries",
            "images",
            ".github",
            ".obsidian",
        ]
        for d in expected_dirs:
            assert (path / d).is_dir(), f"Missing directory: {d}"

    def test_init_creates_claude_md(self, isolated_wikinow):
        path = init_project("my-research")
        claude = path / "CLAUDE.md"
        assert claude.exists()
        content = claude.read_text(encoding="utf-8")
        assert "# WikiNow Schema — my-research" in content

    def test_init_creates_agents_md_symlink(self, isolated_wikinow):
        path = init_project("test")
        agents = path / "AGENTS.md"
        assert agents.is_symlink()
        assert os.readlink(str(agents)) == "CLAUDE.md"

    def test_init_creates_copilot_symlink(self, isolated_wikinow):
        path = init_project("test")
        copilot = path / ".github" / "copilot-instructions.md"
        assert copilot.is_symlink()
        assert os.readlink(str(copilot)) == "../CLAUDE.md"

    def test_init_creates_6_wiki_files(self, isolated_wikinow):
        path = init_project("test")
        wiki_files = [
            "wiki/index.md",
            "wiki/overview.md",
            "wiki/log.md",
            "wiki/contradictions.md",
            "wiki/gaps.md",
            "wiki/tags.md",
        ]
        for f in wiki_files:
            assert (path / f).exists(), f"Missing wiki file: {f}"

    def test_init_creates_3_obsidian_files(self, isolated_wikinow):
        path = init_project("test")
        obsidian_files = [
            ".obsidian/app.json",
            ".obsidian/hotkeys.json",
            ".obsidian/core-plugins.json",
        ]
        for f in obsidian_files:
            assert (path / f).exists(), f"Missing obsidian file: {f}"

    def test_init_creates_gitignore(self, isolated_wikinow):
        path = init_project("test")
        gitignore = path / ".gitignore"
        assert gitignore.exists()
        content = gitignore.read_text(encoding="utf-8")
        assert "wikinow.db" in content
        assert "wikinow.db-wal" in content
        assert "wikinow.db-shm" in content
        assert ".obsidian/*" in content
        assert "!.obsidian/app.json" in content
        assert ".DS_Store" in content

    def test_init_runs_git_init(self, isolated_wikinow):
        path = init_project("test")
        assert (path / ".git").is_dir()

    def test_init_sets_active_project(self, isolated_wikinow):
        from wikinow.config import get_config

        init_project("my-project")
        # Reset singleton to reload from disk
        import wikinow.config

        wikinow.config._manager = None
        assert get_config().projects.active == "my-project"


# =============================================================================
# Init — Errors
# =============================================================================


class TestInitErrors:
    """Verify init_project rejects invalid inputs."""

    def test_init_rejects_duplicate(self, isolated_wikinow):
        init_project("test")
        with pytest.raises(FileExistsError, match="already exists"):
            init_project("test")

    def test_init_rejects_spaces(self, isolated_wikinow):
        with pytest.raises(ValueError, match="Must start with"):
            init_project("bad name")

    def test_init_rejects_special_chars(self, isolated_wikinow):
        with pytest.raises(ValueError, match="Must start with"):
            init_project("bad!name")

    def test_init_rejects_leading_hyphen(self, isolated_wikinow):
        with pytest.raises(ValueError, match="Must start with"):
            init_project("-test")

    def test_init_rejects_empty_name(self, isolated_wikinow):
        with pytest.raises(ValueError, match="Must start with"):
            init_project("")


# =============================================================================
# Switch / List
# =============================================================================


class TestSwitchAndList:
    """Verify project switching and listing."""

    def test_switch_changes_active(self, isolated_wikinow):
        from wikinow.config import get_config
        import wikinow.config

        init_project("project-a")
        init_project("project-b")

        switch_project("project-a")
        wikinow.config._manager = None
        assert get_config().projects.active == "project-a"

    def test_switch_rejects_nonexistent(self, isolated_wikinow):
        with pytest.raises(FileNotFoundError, match="does not exist"):
            switch_project("ghost")

    def test_list_returns_sorted_names(self, isolated_wikinow):
        init_project("charlie")
        init_project("alpha")
        init_project("bravo")
        assert list_projects() == ["alpha", "bravo", "charlie"]

    def test_list_returns_empty_when_none(self, isolated_wikinow):
        assert list_projects() == []
