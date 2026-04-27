"""Wiki search client — search the local wiki via FTS5."""

from wikinow.db import SearchResult, search as db_search


# ── Client ────────────────────────────────────────────────────────────────


def search(query: str, max_results: int = 10) -> list[SearchResult]:
    """Search the wiki using FTS5 keyword search."""
    return db_search(query, max_results)
