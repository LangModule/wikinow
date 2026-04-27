"""Text client — read local text and markdown files."""

from dataclasses import dataclass
from pathlib import Path


# ── Dataclass ─────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class TextResponse:
    """Response from text file read."""

    title: str
    content: str
    path: str


# ── Client ────────────────────────────────────────────────────────────────


def read(file_path: str | Path) -> TextResponse:
    """Read a local text or markdown file."""
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    content = file_path.read_text(encoding="utf-8")
    title = file_path.stem.replace("-", " ").replace("_", " ").title()

    return TextResponse(
        title=title,
        content=content,
        path=str(file_path),
    )
