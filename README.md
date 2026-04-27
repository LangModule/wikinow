# WikiNow

> *Know it now. Keep it forever.*

A local-first personal knowledge base that you feed sources into, an LLM compiles into a structured wiki, and you query through any AI tool via MCP.

Inspired by Andrej Karpathy's [LLM Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) pattern.

```
You collect stuff → LLM organizes it → You query it → Knowledge compounds
```

## How It Works

Instead of RAG (re-derive knowledge every query), the LLM **incrementally builds and maintains a persistent wiki**. When you add a source, it reads it, extracts key information, and integrates it into the existing wiki — updating entity pages, revising topic summaries, noting contradictions, strengthening the evolving synthesis.

The wiki is a **persistent, compounding artifact**. A single ingest can touch 10-15 wiki pages. You never write the wiki yourself — the LLM does all the bookkeeping.

```
┌─────────────────────────────────────────────────┐
│  You (human)           │  LLM (via MCP)         │
├────────────────────────┼────────────────────────┤
│  Curate sources        │  Summarize             │
│  Ask good questions    │  Cross-reference       │
│  Think about meaning   │  Flag contradictions   │
│                        │  Maintain consistency  │
│                        │  Update 15 files/ingest│
└────────────────────────┴────────────────────────┘
```

## Features

- **One-command capture** — `wn ingest <url>` fetches any URL, YouTube video, PDF, epub, or audio file
- **Ripple effect** — one source touches 10-15 wiki pages (source summary + concepts + index + overview + tags + log)
- **AI-native query** — host AI reads index.md, finds relevant pages, synthesizes answers with citations
- **Compounding queries** — valuable answers filed back into the wiki as new pages
- **Self-healing database** — SQLite FTS5 cache auto-syncs with .md files, no manual rebuild
- **Obsidian-compatible** — wikilinks, frontmatter, graph view, backlinks work out of the box
- **Schema co-evolution** — CLAUDE.md instructions evolve through conversation
- **Multi-project** — separate knowledge bases for different topics
- **21 MCP tools** — full toolkit for the host AI to manage the wiki
- **Professional CLI** — rich terminal UI with panels, colors, health bars

## Installation

```bash
# pip
pip install wikinow

# uv
uv tool install wikinow
```

### Optional Dependencies

```bash
# Install with specific extras
pip install wikinow[ollama]     # Ollama web search
pip install wikinow[pdf]        # PDF extraction
pip install wikinow[youtube]    # YouTube transcripts
pip install wikinow[epub]       # Epub parsing
pip install wikinow[whisper]    # Audio transcription (Whisper)
pip install wikinow[watch]      # Auto-ingest on file drop (watchdog)

# Install everything
pip install wikinow[all]
# or
uv tool install wikinow[all]
```

## Quick Start

```bash
# Create a project
wn init my-research

# Start the MCP server
wn serve

# Connect to your AI tool (pick one)
claude mcp add wikinow -- wn serve          # Claude Code
codex mcp add wikinow -- wn serve           # Codex
```

For Cursor / VS Code, add to `.vscode/mcp.json`:

```json
{
  "mcpServers": {
    "wikinow": {
      "command": "wn",
      "args": ["serve"]
    }
  }
}
```

Then tell the AI: *"Ingest this URL and compile it into the wiki"* — and watch it work.

## CLI Commands

```
wn init <name>           Create a new project
wn use <name>            Switch active project
wn list                  List all projects
wn serve                 Start MCP server
wn ingest <url|file>     Ingest a URL or local file
wn search "query"        Search the wiki (FTS5)
wn read <article>        Read a wiki article
wn stats                 Project statistics
wn lint                  Health check
wn gaps                  Knowledge gaps
wn config                Show configuration
wn config <key> <value>  Update configuration
wn export                Export as single markdown file
wn --version             Show version
```

## MCP Tools

WikiNow exposes 21 tools to the host AI:

| Category | Tools |
|---|---|
| **Ingest** | `ingest_url`, `ingest_text`, `ingest_file` |
| **Read/Write** | `read`, `write`, `index_article`, `index_raw`, `mark_compiled` |
| **Search** | `search`, `search_web` |
| **List/Stats** | `list_all_articles`, `list_all_raw`, `list_all_tags`, `get_project_stats`, `get_all_contradictions`, `get_gaps` |
| **Maintenance** | `lint`, `append_log`, `update_schema`, `re_ingest`, `export` |

## Source Types

| Source | How it works |
|---|---|
| **Web URLs** | Jina Reader — free, no API key, handles JavaScript |
| **YouTube** | yt-dlp subtitles, Whisper fallback for audio |
| **PDFs (web)** | Jina Reader handles PDF URLs natively |
| **PDFs (local)** | pymupdf extraction |
| **Epub books** | ebooklib + BeautifulSoup |
| **Audio/video** | Whisper `turbo` model (local, free) |
| **Text/Markdown** | Direct read |

> **Note:** WikiNow only supports **English** content. Non-English audio is automatically detected and skipped. YouTube subtitles are fetched in English only.

## Project Structure

Each project lives in `~/.wikinow/<name>/`:

```
~/.wikinow/my-research/
├── raw/                    ← immutable sources (never modified)
├── wiki/
│   ├── index.md            ← master catalog
│   ├── overview.md         ← evolving synthesis
│   ├── log.md              ← append-only history
│   ├── contradictions.md   ← conflict tracker
│   ├── gaps.md             ← open questions
│   ├── tags.md             ← tag index
│   ├── sources/            ← one page per raw source
│   ├── concepts/           ← concept and entity pages
│   ├── comparisons/        ← X vs Y analysis
│   └── queries/            ← filed query answers
├── images/                 ← downloaded images
├── CLAUDE.md               ← schema (Claude Code + Cursor)
├── AGENTS.md               ← symlink (Codex + Copilot)
├── .obsidian/              ← pre-configured vault
└── wikinow.db              ← self-healing FTS5 index
```

## Configuration

```yaml
# ~/.wikinow/config.yaml

projects:
  active: my-research

ollama:
  api_key: ""              # OLLAMA_API_KEY env var — for web search

whisper:
  model: turbo             # Whisper model for audio transcription

ingestion:
  jina_api_key: ""         # Optional — 20 RPM free, 500 RPM with key
  auto_compile: true
  auto_watch: false

search:
  max_results: 10
```

## Obsidian Integration

`wn init` creates a pre-configured `.obsidian/` vault:

- **Wikilinks** enabled — `[[page]]` links work natively
- **Graph view** — see how pages connect
- **Backlinks** — see what links to each page
- **Cmd+Shift+D** — download remote images locally
- **Dataview compatible** — YAML frontmatter on every article

Open `~/.wikinow/<project>/` in Obsidian and browse your wiki in real time.

## The Karpathy Pattern

WikiNow implements the [LLM Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) pattern by Andrej Karpathy:

> *"The tedious part of maintaining a knowledge base is not the reading or the thinking — it's the bookkeeping. LLMs don't get bored, don't forget to update a cross-reference, and can touch 15 files in one pass."*

Three layers:
1. **Raw sources** — immutable, curated by you
2. **The wiki** — compiled and maintained by the LLM
3. **The schema** — co-evolved by you and the LLM over time

Three operations:
1. **Ingest** — add a source, wiki ripples with updates
2. **Query** — ask questions, answers compound back into wiki
3. **Lint** — health check, find contradictions, suggest gaps to fill

## Requirements

- Python >= 3.11
- [ffmpeg](https://ffmpeg.org) — required if using audio transcription or YouTube Whisper fallback

### Installing ffmpeg

```bash
# macOS
brew install ffmpeg

# Ubuntu / Debian
sudo apt install ffmpeg

# Fedora
sudo dnf install ffmpeg
```

## Testing

```bash
# Install dev dependencies
uv sync --group dev

# Run all tests
uv run pytest tests/ -v

# Run a single test file
uv run pytest tests/test_server.py -v
```

## License

MIT

## Acknowledgments

This project implements the [LLM Wiki pattern](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) by [Andrej Karpathy](https://github.com/karpathy). The core architecture — three layers (raw, wiki, schema), three operations (ingest, query, lint), and the philosophy that humans curate while LLMs maintain — comes directly from his work.
