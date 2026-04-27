"""Tests for wikinow.cli.

Verifies:
- Version and help output
- Project management (init, list, use)
- No-project error handling
- Data commands (stats, lint, config, export)
- Path traversal security
- Error UX panels

Usage:
    pytest tests/test_cli.py -v
"""

import pytest
from typer.testing import CliRunner

from wikinow.cli import app


runner = CliRunner()


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(autouse=True)
def isolated_env(tmp_path, monkeypatch):
    """Redirect WIKINOW_DIR to a temp directory for every test."""
    test_dir = tmp_path / ".wikinow"
    monkeypatch.setattr("wikinow.config.WIKINOW_DIR", test_dir)
    monkeypatch.setattr("wikinow.config.CONFIG_PATH", test_dir / "config.yaml")
    monkeypatch.setattr("wikinow.config._manager", None)
    monkeypatch.setattr("wikinow.project.WIKINOW_DIR", test_dir)
    monkeypatch.setattr("wikinow.db.storage._manager", None)
    yield test_dir


# =============================================================================
# Version / Help
# =============================================================================


class TestVersionHelp:
    """Verify version and help output."""

    def test_version_shows_number(self):
        result = runner.invoke(app, ["--version"])
        assert "0.1.0" in result.output

    def test_help_lists_all_commands(self):
        result = runner.invoke(app, ["--help"])
        commands = [
            "init",
            "use",
            "list",
            "serve",
            "ingest",
            "search",
            "read",
            "stats",
            "lint",
            "gaps",
            "config",
            "export",
        ]
        for cmd in commands:
            assert cmd in result.output


# =============================================================================
# Project Management
# =============================================================================


class TestProjectManagement:
    """Verify init, list, and use CLI commands."""

    def test_init_creates_project(self):
        result = runner.invoke(app, ["init", "test-proj"])
        assert result.exit_code == 0
        assert "Project Created" in result.output

    def test_init_duplicate_error_panel(self):
        runner.invoke(app, ["init", "test-proj"])
        result = runner.invoke(app, ["init", "test-proj"])
        assert result.exit_code == 1
        assert "Init Failed" in result.output

    def test_init_invalid_name_error_panel(self):
        result = runner.invoke(app, ["init", "bad name"])
        assert result.exit_code == 1
        assert "Init Failed" in result.output

    def test_list_shows_active_marker(self):
        runner.invoke(app, ["init", "my-proj"])
        result = runner.invoke(app, ["list"])
        assert "●" in result.output

    def test_use_switches_project(self):
        runner.invoke(app, ["init", "proj-a"])
        runner.invoke(app, ["init", "proj-b"])
        result = runner.invoke(app, ["use", "proj-a"])
        assert "Switched" in result.output


# =============================================================================
# No Project Errors
# =============================================================================


class TestNoProjectErrors:
    """Verify commands fail gracefully without an active project."""

    def test_all_commands_without_project_show_error(self):
        commands = [
            ["stats"],
            ["search", "test"],
            ["lint"],
            ["read", "concepts/ai.md"],
            ["gaps"],
            ["ingest", "https://example.com"],
        ]
        for cmd in commands:
            result = runner.invoke(app, cmd)
            assert "No Active Project" in result.output, f"Command {cmd} missing error"
            assert result.exit_code == 1, f"Command {cmd} should exit with code 1"

        # export uses a different error path
        result = runner.invoke(app, ["export"])
        assert result.exit_code == 1


# =============================================================================
# Data Commands
# =============================================================================


class TestDataCommands:
    """Verify stats, lint, config, and export commands."""

    def test_stats_shows_7_lines(self):
        runner.invoke(app, ["init", "test-proj"])
        result = runner.invoke(app, ["stats"])
        assert "📄" in result.output
        assert "📥" in result.output
        assert "✅" in result.output
        assert "⏳" in result.output
        assert "🔗" in result.output
        assert "🏷" in result.output
        assert "⚡" in result.output

    def test_lint_shows_health_bar(self):
        runner.invoke(app, ["init", "test-proj"])
        result = runner.invoke(app, ["lint"])
        assert "██" in result.output or "░░" in result.output

    def test_config_shows_yaml(self):
        result = runner.invoke(app, ["config"])
        assert "projects:" in result.output

    def test_config_set_updates_value(self):
        result = runner.invoke(app, ["config", "whisper.model", "large-v3"])
        assert "Config Updated" in result.output

    def test_export_creates_file(self):
        runner.invoke(app, ["init", "test-proj"])
        result = runner.invoke(app, ["export"])
        assert "Exported" in result.output


# =============================================================================
# Security
# =============================================================================


class TestSecurity:
    """Verify path traversal protection in CLI."""

    def test_read_path_traversal_error_panel(self):
        runner.invoke(app, ["init", "test-proj"])
        result = runner.invoke(app, ["read", "../../../etc/passwd"])
        assert "Invalid Path" in result.output


# =============================================================================
# Error UX
# =============================================================================


class TestErrorUX:
    """Verify error panels for bad input."""

    def test_use_nonexistent_error_panel(self):
        result = runner.invoke(app, ["use", "ghost"])
        assert "Not Found" in result.output

    def test_list_empty_shows_message(self):
        result = runner.invoke(app, ["list"])
        assert "No Projects" in result.output

    def test_config_key_without_value_error(self):
        result = runner.invoke(app, ["config", "whisper.model"])
        assert "Missing Value" in result.output

    def test_list_shows_inactive_marker(self):
        runner.invoke(app, ["init", "proj-a"])
        runner.invoke(app, ["init", "proj-b"])
        result = runner.invoke(app, ["list"])
        assert "○" in result.output
