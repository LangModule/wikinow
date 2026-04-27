"""
Project management for WikiNow.

Handles init, switch, and list operations.
Each project lives in ~/.wikinow/<name>/ with its own wiki, raw sources, and schema.
"""

import re
import subprocess
from pathlib import Path

from wikinow import templates
from wikinow.config import WIKINOW_DIR, set_config, list_projects as _list_projects


# ── Validation ────────────────────────────────────────────────────────────

_VALID_NAME = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]*$")


def _validate_name(name: str) -> None:
    """Validate project name. Must start with letter/number, then letters/numbers/hyphens/underscores."""
    if not _VALID_NAME.match(name):
        raise ValueError(
            f"Invalid project name '{name}'. "
            "Must start with a letter or number, followed by letters, numbers, hyphens, or underscores."
        )


# ── Init ──────────────────────────────────────────────────────────────────


def init_project(name: str) -> Path:
    """Create a new WikiNow project."""
    _validate_name(name)

    project_dir = WIKINOW_DIR / name
    if project_dir.exists():
        raise FileExistsError(f"Project '{name}' already exists at {project_dir}")

    # Directories
    for subdir in [
        "raw",
        "wiki/sources",
        "wiki/concepts",
        "wiki/comparisons",
        "wiki/queries",
        "images",
        ".github",
        ".obsidian",
    ]:
        (project_dir / subdir).mkdir(parents=True)

    # Schema — real file + symlinks
    (project_dir / "CLAUDE.md").write_text(templates.schema(name), encoding="utf-8")
    (project_dir / "AGENTS.md").symlink_to("CLAUDE.md")
    (project_dir / ".github" / "copilot-instructions.md").symlink_to("../CLAUDE.md")

    # Wiki files
    (project_dir / "wiki" / "index.md").write_text(
        templates.index(name), encoding="utf-8"
    )
    (project_dir / "wiki" / "overview.md").write_text(
        templates.overview(name), encoding="utf-8"
    )
    (project_dir / "wiki" / "log.md").write_text(templates.log(name), encoding="utf-8")
    (project_dir / "wiki" / "contradictions.md").write_text(
        templates.contradictions(name), encoding="utf-8"
    )
    (project_dir / "wiki" / "gaps.md").write_text(
        templates.gaps(name), encoding="utf-8"
    )
    (project_dir / "wiki" / "tags.md").write_text(
        templates.tags(name), encoding="utf-8"
    )

    # Obsidian config
    (project_dir / ".obsidian" / "app.json").write_text(
        templates.obsidian_app(), encoding="utf-8"
    )
    (project_dir / ".obsidian" / "hotkeys.json").write_text(
        templates.obsidian_hotkeys(), encoding="utf-8"
    )
    (project_dir / ".obsidian" / "core-plugins.json").write_text(
        templates.obsidian_core_plugins(), encoding="utf-8"
    )

    # Gitignore
    (project_dir / ".gitignore").write_text(_gitignore(), encoding="utf-8")

    # Git init
    subprocess.run(["git", "init"], cwd=project_dir, capture_output=True, check=True)

    # Set as active project
    set_config("projects.active", name)

    return project_dir


# ── Switch ────────────────────────────────────────────────────────────────


def switch_project(name: str) -> Path:
    """Switch the active project."""
    project_dir = WIKINOW_DIR / name
    if not project_dir.exists():
        raise FileNotFoundError(f"Project '{name}' does not exist.")

    set_config("projects.active", name)
    return project_dir


# ── List ──────────────────────────────────────────────────────────────────


def list_projects() -> list[str]:
    """List all project names."""
    return _list_projects()


# ── Gitignore ─────────────────────────────────────────────────────────────


def _gitignore() -> str:
    """Generate .gitignore content."""
    return """\
# WikiNow — self-healing cache, auto-rebuilt from .md files
wikinow.db
wikinow.db-wal
wikinow.db-shm

# Obsidian — ignore personal state, keep shared config
.obsidian/*
!.obsidian/app.json
!.obsidian/hotkeys.json
!.obsidian/core-plugins.json

# OS
.DS_Store
"""
