"""Epub client — extract text from local epub files via ebooklib."""

from dataclasses import dataclass
from pathlib import Path

try:
    import ebooklib
    from ebooklib import epub

    from bs4 import BeautifulSoup
except ImportError:
    ebooklib = None


# ── Dataclass ─────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class EpubResponse:
    """Response from epub extraction."""

    title: str
    author: str
    content: str
    chapters: int
    path: str


# ── Client ────────────────────────────────────────────────────────────────


def extract(file_path: str | Path) -> EpubResponse:
    """Extract text from a local epub file."""
    if ebooklib is None:
        raise ImportError(
            "ebooklib and beautifulsoup4 are required: pip install wikinow[epub]"
        )

    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"Epub not found: {file_path}")

    book = epub.read_epub(str(file_path), options={"ignore_ncx": True})

    title = book.get_metadata("DC", "title")
    title = (
        title[0][0]
        if title
        else file_path.stem.replace("-", " ").replace("_", " ").title()
    )

    author = book.get_metadata("DC", "creator")
    author = author[0][0] if author else ""

    chapters = []
    for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
        html = item.get_content().decode("utf-8", errors="ignore")
        text = BeautifulSoup(html, "html.parser").get_text(separator="\n").strip()
        if text:
            chapters.append(text)

    return EpubResponse(
        title=title,
        author=author,
        content="\n\n---\n\n".join(chapters),
        chapters=len(chapters),
        path=str(file_path),
    )
