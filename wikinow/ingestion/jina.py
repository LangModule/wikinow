"""Jina Reader client — fetch any URL as clean markdown."""

from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


JINA_READER_URL = "https://r.jina.ai/"


# ── Dataclass ─────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class JinaResponse:
    """Response from Jina Reader."""

    title: str
    content: str
    url: str


# ── Client ────────────────────────────────────────────────────────────────


def fetch(url: str, api_key: str = "", timeout: int = 30) -> JinaResponse:
    """Fetch a URL via Jina Reader and return clean markdown."""
    reader_url = JINA_READER_URL + quote(url, safe=":/?&=#")

    headers = {
        "Accept": "text/markdown",
        "X-Return-Format": "markdown",
        "User-Agent": "WikiNow/0.1",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    req = Request(reader_url, headers=headers)

    try:
        with urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
    except HTTPError as e:
        raise ConnectionError(f"Jina Reader returned {e.code} for {url}") from e
    except URLError as e:
        raise ConnectionError(f"Failed to reach Jina Reader: {e.reason}") from e

    title, content = _parse_response(body)

    return JinaResponse(title=title, content=content, url=url)


# ── Parser ────────────────────────────────────────────────────────────────


def _parse_response(body: str) -> tuple[str, str]:
    """Extract title and content from Jina Reader markdown response."""
    lines = body.strip().split("\n")

    title = ""
    content_start = 0

    for i, line in enumerate(lines):
        if line.startswith("# "):
            title = line[2:].strip()
            content_start = i + 1
            break

    content = "\n".join(lines[content_start:]).strip()

    if not title and lines:
        title = lines[0][:100].strip()

    return title, content
