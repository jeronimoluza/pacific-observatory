"""The discovery store: one SQLite file holding queries, the run ledger, hits and candidates.

SQLite rather than parquet because the daily loop is all small writes -- a run
row per query, a status flip per candidate -- and the question asked before
every search ("has this (query, engine) pair run?") is a primary-key lookup.

The file lives under the production tree, not the worktree, so every checkout
and the cron jobs share one ledger. A second copy would re-spend search budget
on queries the first copy already ran.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import tldextract

DEFAULT_DB = Path.home() / "po" / "data" / "prices" / "_discovery" / "discovery.sqlite"

STATUSES = (
    "discovered",
    "ambiguous",
    "verified",
    "scaffolded",
    "live",
    "onboarded",
    "rejected",
    "blocked_plain",
    "blocked_hard",
)

SCHEMA = f"""
CREATE TABLE IF NOT EXISTS countries (
    country        TEXT PRIMARY KEY,
    region         TEXT NOT NULL,
    subregion      TEXT NOT NULL,
    currency       TEXT,
    languages      TEXT,
    n_sources      INTEGER NOT NULL,
    pass1_done_at  TEXT,
    pass1_verified INTEGER
);
CREATE TABLE IF NOT EXISTS queries (
    query_id   TEXT PRIMARY KEY,
    country    TEXT NOT NULL REFERENCES countries(country),
    text       TEXT NOT NULL,
    lang       TEXT NOT NULL,
    template   TEXT,
    tier       TEXT NOT NULL CHECK (tier IN ('top20', 'deep', 'followup')),
    origin     TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS engines (
    engine        TEXT PRIMARY KEY,
    daily_cap     INTEGER NOT NULL,
    parked_until  TEXT,
    last_block_at TEXT,
    last_probe_at TEXT
);
CREATE TABLE IF NOT EXISTS runs (
    run_id   TEXT PRIMARY KEY,
    query_id TEXT NOT NULL REFERENCES queries(query_id),
    engine   TEXT NOT NULL REFERENCES engines(engine),
    ran_at   TEXT NOT NULL,
    status   TEXT NOT NULL CHECK (status IN ('ok', 'empty', 'blocked', 'error')),
    n_hits   INTEGER NOT NULL,
    UNIQUE (query_id, engine)
);
CREATE TABLE IF NOT EXISTS hits (
    run_id  TEXT NOT NULL REFERENCES runs(run_id),
    rank    INTEGER NOT NULL,
    url     TEXT NOT NULL,
    domain  TEXT NOT NULL,
    title   TEXT,
    snippet TEXT,
    PRIMARY KEY (run_id, rank)
);
CREATE TABLE IF NOT EXISTS candidates (
    country        TEXT NOT NULL,
    domain         TEXT NOT NULL,
    status         TEXT NOT NULL CHECK (status IN ({", ".join(f"'{s}'" for s in STATUSES)})),
    kind           TEXT,
    best_url       TEXT,
    currency_seen  TEXT,
    price_evidence TEXT,
    platform       TEXT,
    robots_ok      TEXT,
    n_items_est    INTEGER,
    reason         TEXT,
    first_run_id   TEXT,
    source_config  TEXT,
    notes          TEXT,
    updated_at     TEXT NOT NULL,
    PRIMARY KEY (country, domain)
);
CREATE INDEX IF NOT EXISTS candidates_status ON candidates (status);
CREATE INDEX IF NOT EXISTS hits_domain ON hits (domain);
"""

# The bundled suffix-list snapshot, never a network fetch: a cron job that
# silently re-downloads the PSL on first use is one more thing that can hang.
# Private suffixes on, or every `*.myshopify.com` / `*.wixsite.com` shop in a
# country collapses into one candidate.
_extract = tldextract.TLDExtract(suffix_list_urls=(), include_psl_private_domains=True)


def connect(db_path: Path = DEFAULT_DB) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript(SCHEMA)
    return con


def registrable_domain(url: str) -> str | None:
    """`https://shop.warrani.com/x` -> `warrani.com`; `jumia.com.ng` stays whole.

    One candidate per (country, registrable domain), so `www.` and `shop.`
    variants of one shop collapse, while per-country marketplace domains
    (jumia.com.ng vs jumia.cm) stay separate because the suffix differs.
    """
    ext = _extract(url.strip())
    if not ext.domain or not ext.suffix:
        return None
    return f"{ext.domain}.{ext.suffix}".lower()
