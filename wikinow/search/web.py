"""Web search client — search the internet via Ollama API."""

from dataclasses import dataclass

try:
    import ollama
except ImportError:
    ollama = None


# ── Dataclass ─────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class WebSearchResult:
    """Single web search result."""

    title: str
    url: str
    content: str


# ── Client ────────────────────────────────────────────────────────────────


def search(query: str, max_results: int = 5) -> list[WebSearchResult]:
    """Search the web via Ollama API. Requires OLLAMA_API_KEY env var."""
    if ollama is None:
        raise ImportError("ollama is required: pip install wikinow[ollama]")

    try:
        response = ollama.web_search(query, max_results=max_results)
    except Exception as e:
        raise ConnectionError(f"Ollama web search failed: {e}") from e

    return [
        WebSearchResult(
            title=r.title or "",
            url=r.url or "",
            content=r.content or "",
        )
        for r in response.results
    ]
