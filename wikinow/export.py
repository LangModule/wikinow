"""Export wiki as a single markdown file."""

from datetime import datetime, timezone
from pathlib import Path

from wikinow.config import get_project_path


# ── Export ─────────────────────────────────────────────────────────────────


def export_single(project_name: str | None = None) -> Path:
    """Export entire wiki as a single markdown file."""
    project_path = get_project_path(project_name)
    wiki_path = project_path / "wiki"
    name = project_path.name

    parts: list[str] = []
    parts.append(f"# {name} — WikiNow Export")
    parts.append(
        f"*Exported {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}*\n"
    )

    # System files
    for filename in ["overview.md", "index.md"]:
        file_path = wiki_path / filename
        if file_path.exists():
            parts.append(file_path.read_text(encoding="utf-8").strip())
            parts.append("")

    # Article directories
    for subdir in ["sources", "concepts", "comparisons", "queries"]:
        folder = wiki_path / subdir
        if not folder.exists():
            continue
        files = sorted(folder.glob("*.md"))
        if not files:
            continue
        parts.append(f"---\n\n# {subdir.title()}\n")
        for f in files:
            parts.append(f.read_text(encoding="utf-8").strip())
            parts.append("")

    output = project_path / f"{name}-export.md"
    output.write_text("\n".join(parts).strip() + "\n", encoding="utf-8")

    return output
