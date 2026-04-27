"""Template content for WikiNow project files."""

import json


# ── Schema ────────────────────────────────────────────────────────────────


def schema(name: str) -> str:
    """CLAUDE.md content. Symlinked to AGENTS.md and .github/copilot-instructions.md."""
    return f"""\
# WikiNow Schema — {name}

## Your Role

You are the maintainer of this knowledge base. Your job is the bookkeeping —
summarizing, cross-referencing, filing, and keeping everything consistent.
The human curates sources, asks questions, and thinks about what it all means.
You do everything else.

You own all files in wiki/. You never modify files in raw/ — those are immutable sources.

## Tools

ingest_url(url), ingest_text(name, content), ingest_file(path)
read(path), write(path, content)
index_article(path, title, summary, tags, confidence, links, created, updated)
index_raw(path, source_url, content_hash), mark_compiled(raw_path)
search(query), search_web(query)
list_all_articles(), list_all_raw(), list_all_tags()
get_project_stats(), get_all_contradictions(), get_gaps()
lint(), append_log(entry), update_schema(section, content)
re_ingest(source), export()

## On Every Ingest

When you receive new content to process:

1. Read wiki/index.md to understand what already exists in the wiki
2. Read any existing pages that might be related to the new source
3. Write a source summary page in wiki/sources/ — capture key facts, arguments, data
4. Create or update concept pages in wiki/concepts/ — each major idea, entity, or topic
   deserves its own page. If a concept is mentioned across 3+ sources, it needs a dedicated page.
5. Check if the new source contradicts anything in existing pages. If so, note it
   in both the relevant page (set confidence to "conflict") and wiki/contradictions.md
6. Update wiki/index.md — add new pages with one-line summaries, organized by category
7. Update wiki/overview.md — this is the evolving thesis, the big picture synthesis
   of everything in the wiki. Every ingest should refine it.
8. Update wiki/tags.md with any new tags
9. Log the ingest with append_log()
10. Every page you write must have [[wikilinks]] to related pages and a ## Related section
11. A single source should ripple across many pages — don't just write one summary and stop
12. After writing each page, call index_article() with title, summary, tags, confidence, and links
13. When you're done processing the source, call mark_compiled() on it

## On Every Query

When the user asks a question:

1. Read wiki/index.md to find which pages are relevant
2. Read those pages to gather information
3. Synthesize a clear answer with citations back to source pages
4. If the answer is substantial or reusable, file it as wiki/queries/<topic>.md
   and call index_article() — queries compound into the knowledge base
5. If your answer reveals new connections or insights, update the relevant concept pages
6. Match your output format to the question — tables for comparisons,
   bullet points for lists, full pages for deep analysis
7. Log the query with append_log()

## On Lint

Run lint() to discover issues. Then fix what you can:
- Orphan pages with no inbound links — add [[wikilinks]] from related pages
- Dead [[wikilinks]] pointing to pages that don't exist — create the page or fix the link
- Raw sources not yet compiled — process them
- Concepts mentioned frequently but lacking their own page — create the page
- Pages missing from index.md — add them
- Contradictions between pages — flag with confidence: conflict
- Stale claims superseded by newer sources — update or note the conflict
- Knowledge gaps — suggest what to research next and update wiki/gaps.md

## On Web Search

1. Use search_web() first — it uses Ollama API and preserves your native search quota
2. If it fails (rate limit or no API key), fall back to your built-in web search

## Confidence Levels

- **high** — well-supported by multiple sources, no contradictions
- **medium** — supported but limited sources, or minor uncertainties
- **low** — single source, unverified, or speculative
- **conflict** — contradicts other sources in the wiki. Detail the conflict in the page body.

## Frontmatter

You MUST include this at the top of every wiki article:

```yaml
---
title: Page Title
tags: [tag1, tag2]
sources: [source-file.md]
confidence: high | medium | low | conflict
created: YYYY-MM-DD
updated: YYYY-MM-DD
---
```

## Wiki Structure

- wiki/index.md          — master catalog, organized by category
- wiki/overview.md       — evolving thesis and high-level synthesis
- wiki/log.md            — append-only (use append_log() tool)
- wiki/contradictions.md — tracks active conflicts between sources
- wiki/gaps.md           — open questions and suggested sources to find
- wiki/tags.md           — tag index with article counts
- wiki/sources/          — one summary page per raw source
- wiki/concepts/         — concept and entity pages (the core of the wiki)
- wiki/comparisons/      — X vs Y analysis pages
- wiki/queries/          — filed answers to valuable questions

## Domain-Specific Notes

(Add notes here as you learn what works for this project.
Use update_schema() to modify this section during conversation.)
"""


# ── Wiki Files ────────────────────────────────────────────────────────────


def index(name: str) -> str:
    """wiki/index.md content."""
    return f"""\
# Index — {name}

> Master catalog of all wiki pages. Updated on every ingest.

## Sources

## Concepts

## Comparisons

## Queries
"""


def overview(name: str) -> str:
    """wiki/overview.md content."""
    return f"""\
# Overview — {name}

> Evolving high-level synthesis. Updated on every ingest.
"""


def log(name: str) -> str:
    """wiki/log.md content."""
    return f"""\
# Log — {name}

> Append-only. Use append_log() tool to add entries.
"""


def contradictions(name: str) -> str:
    """wiki/contradictions.md content."""
    return f"""\
# Contradictions — {name}

> Active conflicts between sources. Updated on every ingest.
"""


def gaps(name: str) -> str:
    """wiki/gaps.md content."""
    return f"""\
# Knowledge Gaps — {name}

> Open questions and suggested sources. Updated on lint.
"""


def tags(name: str) -> str:
    """wiki/tags.md content."""
    return f"""\
# Tags — {name}

> Tag index with article counts. Updated on every ingest.
"""


# ── Obsidian ──────────────────────────────────────────────────────────────


def obsidian_app() -> str:
    """.obsidian/app.json content."""
    return json.dumps(
        {
            "useMarkdownLinks": False,
            "newLinkFormat": "shortest",
            "attachmentFolderPath": "./images",
            "showFrontmatter": True,
            "readableLineLength": True,
        },
        indent=2,
    )


def obsidian_hotkeys() -> str:
    """.obsidian/hotkeys.json content."""
    return json.dumps(
        {
            "editor:download-attachments": [
                {"modifiers": ["Mod", "Shift"], "key": "D"},
            ],
        },
        indent=2,
    )


def obsidian_core_plugins() -> str:
    """.obsidian/core-plugins.json content."""
    return json.dumps(
        [
            "file-explorer",
            "global-search",
            "graph",
            "backlink",
            "tag-pane",
            "page-preview",
            "outgoing-link",
            "canvas",
        ]
    )
