"""PDF client — extract text from local PDF files via pymupdf."""

from dataclasses import dataclass
from pathlib import Path

try:
    import pymupdf
except ImportError:
    pymupdf = None


# ── Dataclass ─────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class PDFResponse:
    """Response from PDF extraction."""

    title: str
    content: str
    pages: int
    path: str


# ── Client ────────────────────────────────────────────────────────────────


def extract(file_path: str | Path) -> PDFResponse:
    """Extract text from a local PDF file."""
    if pymupdf is None:
        raise ImportError("pymupdf is required: pip install wikinow[pdf]")

    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"PDF not found: {file_path}")

    doc = pymupdf.open(str(file_path))
    title = doc.metadata.get("title", "") if doc.metadata else ""
    pages = []
    for page in doc:
        text = page.get_text().strip()
        if text:
            pages.append(text)
    doc.close()

    content = "\n\n".join(pages)
    if not title:
        title = file_path.stem.replace("-", " ").replace("_", " ").title()

    return PDFResponse(
        title=title,
        content=content,
        pages=len(pages),
        path=str(file_path),
    )
