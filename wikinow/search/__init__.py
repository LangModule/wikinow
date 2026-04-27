"""WikiNow search package."""

from wikinow.search.web import WebSearchResult, search as search_web
from wikinow.search.wiki import search as search_wiki

__all__ = [
    "WebSearchResult",
    "search_web",
    "search_wiki",
]
