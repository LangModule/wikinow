"""WikiNow ingestion package."""

from wikinow.ingestion.audio import (
    AudioResponse,
    transcribe as transcribe_audio,
    format_as_markdown as format_audio,
)
from wikinow.ingestion.epub import EpubResponse, extract as extract_epub
from wikinow.ingestion.jina import JinaResponse, fetch as fetch_url
from wikinow.ingestion.pdf import PDFResponse, extract as extract_pdf
from wikinow.ingestion.text import TextResponse, read as read_text
from wikinow.ingestion.youtube import (
    YouTubeResponse,
    fetch as fetch_youtube,
    format_as_markdown as format_youtube,
    is_youtube_url,
)

__all__ = [
    "AudioResponse",
    "EpubResponse",
    "JinaResponse",
    "PDFResponse",
    "TextResponse",
    "YouTubeResponse",
    "extract_epub",
    "extract_pdf",
    "fetch_url",
    "fetch_youtube",
    "format_audio",
    "format_youtube",
    "is_youtube_url",
    "read_text",
    "transcribe_audio",
]
