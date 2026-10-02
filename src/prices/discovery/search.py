"""Spend the daily search budgets: pick queries, run them, keep the hits.

One function decides what runs next for any engine (`next_queries`), so the
ddgs cron job and the Claude WebSearch session draw from the same ledger:

1. Follow-up queries first, up to ~10% of the batch (they come from fresh finds).
2. Pass 1: `top20` queries, countries with the fewest existing sources first.
   Top-20 queries run on yahoo AND websearch, to measure each engine's yield;
   other engines skip them.
3. Pass 2: `deep` queries, countries whose pass 1 verified the most first.
   Deep and follow-up queries run once, on whichever engine reaches them first.

A search engine that blocks us is parked for 24 h and its cap halved; it is
never retried with tricks. ddgs reports some blocks as an empty page, so after
three empties in a row one unrecorded canary query decides: empty too means blocked.
"""

from __future__ import annotations

import math
import sqlite3
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from prices.discovery.db import registrable_domain

HERE = Path(__file__).resolve().parent
BLOCKLIST = frozenset(
    line.strip()
    for line in (HERE / "blocklist.txt").read_text(encoding="utf-8").splitlines()
    if line.strip() and not line.startswith("#")
)

# Engines whose top-20 queries are re-run even when another engine ran them.
OVERLAP_ENGINES = ("yahoo", "yandex", "websearch")
DDGS_ENGINES = ("yahoo", "duckduckgo", "yandex", "google")
# Seconds between queries; yahoo held at ~16 s from 191.80.83.234 on 2026-09-30.
# yandex and google joined on 2026-10-02 after a 1-query probe; untested pace.
SPACING = {"yahoo": 16, "duckduckgo": 20, "yandex": 20, "google": 20}
EMPTIES_MEAN_BLOCK = 3
CANARY = "weather forecast"
MAX_RESULTS = 20

# Template prefix -> candidate kind. Unlisted templates are retail.
_KIND_PREFIXES = (
    (
        "tariff",
        (
            "fuel_price",
            "electricity_tariff",
            "water_tariff",
            "mobile_data_plans",
            "transport_fares",
        ),
    ),
    ("bulletin", ("market_prices", "consumer_price_index")),
    ("classifieds", ("classifieds",)),
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


def kind_of(template: str | None) -> str:
    for kind, prefixes in _KIND_PREFIXES:
        if template and template.startswith(prefixes):
            return kind
    return "retail"


def budget_left(con: sqlite3.Connection, engine: str) -> int:
    """Queries this engine may still run today (UTC); 0 while parked."""
    row = con.execute(
        "SELECT daily_cap, parked_until FROM engines WHERE engine = ?", (engine,)
    ).fetchone()
    if row is None:
        raise KeyError(f"unknown engine {engine!r}")
    if row["parked_until"] and row["parked_until"] > _iso(_now()):
        return 0
    used = con.execute(
        "SELECT COUNT(*) FROM runs WHERE engine = ? AND ran_at >= ?",
        (engine, _now().strftime("%Y-%m-%d")),
    ).fetchone()[0]
    return max(0, row["daily_cap"] - used)


def next_queries(
    con: sqlite3.Connection, engine: str, n: int, country: str | None = None
) -> list[sqlite3.Row]:
    """The next `n` queries for `engine`, in pass order, never repeating a run."""
    if n <= 0:
        return []
    where_country = "AND q.country = :country" if country else ""
    # Top-20 queries belong to the overlap engines and count as done per
    # engine; everything else is done once it ran anywhere. Errors are retried.
    done_here = "EXISTS (SELECT 1 FROM runs r WHERE r.query_id = q.query_id AND r.engine = :engine AND r.status != 'error')"
    done_anywhere = (
        "EXISTS (SELECT 1 FROM runs r WHERE r.query_id = q.query_id AND r.status != 'error')"
    )
    pass1_verified = """(SELECT COUNT(*) FROM candidates c
         JOIN runs r ON r.run_id = c.first_run_id
         JOIN queries q1 ON q1.query_id = r.query_id
         WHERE c.country = q.country AND q1.tier = 'top20'
           AND c.status IN ('verified', 'scaffolded', 'live'))"""
    params = {"engine": engine, "country": country}

    def pick(tier_sql: str, done: str, order: str, limit: int) -> list[sqlite3.Row]:
        return con.execute(
            f"""SELECT q.* FROM queries q JOIN countries k ON k.country = q.country
                WHERE {tier_sql} AND NOT {done} {where_country}
                ORDER BY {order} LIMIT :limit""",
            {**params, "limit": limit},
        ).fetchall()

    out = pick("q.tier = 'followup'", done_anywhere, "q.created_at, q.query_id", math.ceil(n / 10))
    if engine in OVERLAP_ENGINES:
        out += pick("q.tier = 'top20'", done_here, "k.n_sources, q.country, q.rowid", n - len(out))
    out += pick(
        "q.tier = 'deep'",
        done_anywhere,
        f"{pass1_verified} DESC, k.n_sources, q.country, q.rowid",
        n - len(out),
    )
    if len(out) < n:
        # Follow-ups beyond the 10% share, once everything else is spent.
        seen = {q["query_id"] for q in out}
        more = pick("q.tier = 'followup'", done_anywhere, "q.created_at, q.query_id", n)
        out += [q for q in more if q["query_id"] not in seen][: n - len(out)]
    return out


def park(con: sqlite3.Connection, engine: str) -> None:
    now = _now()
    con.execute(
        """UPDATE engines SET parked_until = ?, last_block_at = ?,
               daily_cap = MAX(1, daily_cap / 2)
           WHERE engine = ?""",
        (_iso(now + timedelta(hours=24)), _iso(now), engine),
    )


def record_run(
    con: sqlite3.Connection, query: sqlite3.Row, engine: str, status: str, results: list[dict]
) -> dict:
    """Write one run and its hits; promote unseen domains to `discovered`.

    Existing candidates are never touched (INSERT OR IGNORE), so an onboarded or
    rejected domain stays what it is however often a search returns it.
    """
    run_id = uuid.uuid4().hex[:16]
    now = _iso(_now())
    con.execute(
        """INSERT OR REPLACE INTO runs (run_id, query_id, engine, ran_at, status, n_hits)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (run_id, query["query_id"], engine, now, status, len(results)),
    )
    new = blocked = 0
    for rank, res in enumerate(results, 1):
        url = res.get("href") or res.get("url") or ""
        domain = registrable_domain(url) if url else None
        if not domain:
            continue
        con.execute(
            "INSERT OR IGNORE INTO hits (run_id, rank, url, domain, title, snippet) VALUES (?, ?, ?, ?, ?, ?)",
            (run_id, rank, url, domain, res.get("title"), res.get("body") or res.get("snippet")),
        )
        if domain in BLOCKLIST:
            blocked += 1
            continue
        cur = con.execute(
            """INSERT OR IGNORE INTO candidates
               (country, domain, status, kind, best_url, first_run_id, updated_at)
               VALUES (?, ?, 'discovered', ?, ?, ?, ?)""",
            (query["country"], domain, kind_of(query["template"]), url, run_id, now),
        )
        new += cur.rowcount
    return {"run_id": run_id, "new": new, "blocklisted": blocked}


def _ddgs_search(engine: str, text: str) -> tuple[str, list[dict]]:
    from ddgs import DDGS
    from ddgs.exceptions import DDGSException, RatelimitException, TimeoutException

    try:
        return "ok", DDGS(timeout=20).text(text, backend=engine, max_results=MAX_RESULTS)
    except RatelimitException:
        return "blocked", []
    except TimeoutException:
        return "error", []
    except DDGSException as exc:
        return ("empty", []) if "no results" in str(exc).lower() else ("error", [])


def mark_pass1(con: sqlite3.Connection) -> None:
    """Stamp countries whose top-20 ran on yahoo, with their pass-1 verified count."""
    con.execute(
        """UPDATE countries SET pass1_done_at = ? WHERE pass1_done_at IS NULL
           AND EXISTS (SELECT 1 FROM queries q WHERE q.country = countries.country AND q.tier = 'top20')
           AND NOT EXISTS (SELECT 1 FROM queries q WHERE q.country = countries.country AND q.tier = 'top20'
               AND NOT EXISTS (SELECT 1 FROM runs r WHERE r.query_id = q.query_id
                               AND r.engine = 'yahoo' AND r.status != 'error'))""",
        (_iso(_now()),),
    )
    con.execute("""UPDATE countries SET pass1_verified = (
               SELECT COUNT(*) FROM candidates c
               JOIN runs r ON r.run_id = c.first_run_id
               JOIN queries q ON q.query_id = r.query_id
               WHERE c.country = countries.country AND q.tier = 'top20'
                 AND c.status IN ('verified', 'scaffolded', 'live'))
           WHERE pass1_done_at IS NOT NULL""")


def run_ddgs(
    con: sqlite3.Connection,
    engines: list[str],
    country: str | None = None,
    limit: int | None = None,
    echo=print,
) -> dict:
    """Run each engine until its cap, a block, or `limit`. Engines run in turn."""
    totals = {}
    for engine in engines:
        if engine not in DDGS_ENGINES:
            raise ValueError(f"{engine} is not a ddgs engine; use {DDGS_ENGINES}")
        left = budget_left(con, engine)
        queue = next_queries(con, engine, min(left, limit or left), country)
        echo(f"{engine}: {left} left today, {len(queue)} queued")
        stats = {"ok": 0, "empty": 0, "error": 0, "blocked": 0, "new": 0}
        empty_streak: list[str] = []
        for i, q in enumerate(queue):
            if i:
                time.sleep(SPACING[engine])
            status, results = _ddgs_search(engine, q["text"])
            stats[status] += 1
            if status == "empty" and len(empty_streak) + 1 >= EMPTIES_MEAN_BLOCK:
                # Small-town queries are often truly empty ("téléphones Bimbo"
                # parked yahoo on 2026-10-01). One query that always has
                # results tells a thin niche from a silent block.
                time.sleep(SPACING[engine])
                canary, _ = _ddgs_search(engine, CANARY)
                if canary == "ok":
                    empty_streak = []
                    with con:
                        record_run(con, q, engine, "empty", [])
                    echo(f"  [{i + 1}/{len(queue)}] empty, canary ok  {q['country']}: {q['text']}")
                    continue
            if status == "blocked" or (
                status == "empty" and len(empty_streak) + 1 >= EMPTIES_MEAN_BLOCK
            ):
                # A block is not a run. Neither were the empties before it:
                # drop them so those queries run again once the engine is back.
                with con:
                    con.executemany(
                        "DELETE FROM runs WHERE run_id = ?", [(r,) for r in empty_streak]
                    )
                    park(con, engine)
                echo(
                    f"  {engine} parked 24h after {'block' if status == 'blocked' else 'repeated empties'}"
                )
                break
            with con:
                res = record_run(con, q, engine, status, results)
            empty_streak = empty_streak + [res["run_id"]] if status == "empty" else []
            stats["new"] += res["new"]
            echo(
                f"  [{i + 1}/{len(queue)}] {status:<5} {len(results):>2} hits {res['new']:>2} new  {q['country']}: {q['text']}"
            )
        with con:
            mark_pass1(con)
        totals[engine] = stats
    return totals
