"""SQLite schema definitions for WikiNow."""

# ── Articles ──────────────────────────────────────────────────────────────

CREATE_ARTICLES = """\
CREATE TABLE IF NOT EXISTS articles (
    id          INTEGER PRIMARY KEY,
    path        TEXT UNIQUE NOT NULL,
    title       TEXT,
    summary     TEXT,
    confidence  TEXT,
    created     TEXT,
    updated     TEXT,
    indexed_at  TEXT NOT NULL
)"""

# ── Full Text Search ─────────────────────────────────────────────────────

CREATE_FTS = """\
CREATE VIRTUAL TABLE IF NOT EXISTS fts USING fts5(
    title,
    content,
    tokenize='porter unicode61'
)"""

# ── Backlinks ─────────────────────────────────────────────────────────────

CREATE_LINKS = """\
CREATE TABLE IF NOT EXISTS links (
    source_id   INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    target_path TEXT NOT NULL,
    UNIQUE(source_id, target_path)
)"""

# ── Tags ──────────────────────────────────────────────────────────────────

CREATE_TAGS = """\
CREATE TABLE IF NOT EXISTS tags (
    article_id  INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    tag         TEXT NOT NULL,
    UNIQUE(article_id, tag)
)"""

# ── Raw Sources ───────────────────────────────────────────────────────────

CREATE_RAW = """\
CREATE TABLE IF NOT EXISTS raw (
    id           INTEGER PRIMARY KEY,
    path         TEXT UNIQUE NOT NULL,
    source_url   TEXT,
    content_hash TEXT NOT NULL,
    compiled     INTEGER DEFAULT 0,
    compiled_at  TEXT,
    ingested_at  TEXT NOT NULL
)"""

# ── Indexes ───────────────────────────────────────────────────────────────

CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_articles_confidence ON articles(confidence)",
    "CREATE INDEX IF NOT EXISTS idx_links_target ON links(target_path)",
    "CREATE INDEX IF NOT EXISTS idx_tags_tag ON tags(tag)",
    "CREATE INDEX IF NOT EXISTS idx_raw_compiled ON raw(compiled)",
    "CREATE INDEX IF NOT EXISTS idx_raw_hash ON raw(content_hash)",
]

# ── All Tables ────────────────────────────────────────────────────────────

ALL_TABLES = [
    CREATE_ARTICLES,
    CREATE_FTS,
    CREATE_LINKS,
    CREATE_TAGS,
    CREATE_RAW,
]
