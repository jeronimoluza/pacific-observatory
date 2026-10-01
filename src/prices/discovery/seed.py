"""Load what we already know into the store before spending any search budget.

Two sources of prior knowledge:

1. The config tree. Every domain a YAML already scrapes becomes an `onboarded`
   candidate, so a search hit on it is dropped for free instead of re-triaged.
2. The skill inventories (`references/inventories/<region>/<country>.md`): free
   text tables written by past onboarding passes. A domain a past pass found
   dead must not come back as "new" the first time a search returns it.

Seeding is re-runnable. Config rows always win (a candidate that has since
been onboarded flips to `onboarded`); inventory rows only fill domains the
store has never seen, so re-seeding never overwrites a later triage verdict.
"""

from __future__ import annotations

import re
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import yaml

from prices.discovery.db import registrable_domain

REPO_ROOT = Path(__file__).resolve().parents[3]
CONFIGS_DIR = REPO_ROOT / "src" / "prices" / "configs"
INVENTORIES_DIR = (
    REPO_ROOT / ".claude" / "skills" / "onboard-price-sources" / "references" / "inventories"
)

# Daily caps from the spec. Engines at 0 are re-probed weekly with one query,
# not run: from 191.80.83.234 they returned silent empties on 2026-09-30.
ENGINE_CAPS = {
    "yahoo": 150,
    "duckduckgo": 30,
    "websearch": 100,
    "brave": 0,
    "google": 0,
    "mojeek": 0,
    "startpage": 0,
    "yandex": 0,
}

# Inventory status words -> store status. Checked in this order, first hit
# wins, so "DEAD END" lands in rejected before anything looser can claim it.
# Everything unmatched (NOT PURSUED, NOT PROBED, CONFIRMED VIABLE, PARKED,
# INCONCLUSIVE, ...) becomes `discovered`: a past pass looked but did not
# finish, so triage should look again. The original wording stays in notes.
_STATUS_RULES = (
    ("onboarded", ("SHIPPED", "ONBOARDED")),
    ("blocked_plain", ("BLOCKED",)),
    (
        "rejected",
        (
            "DEAD",
            "NOT FOUND",
            "NXDOMAIN",
            "UNREACHABLE",
            "NOT REACHABLE",
            "OUT OF SCOPE",
            "FACEBOOK",
            "NOT APPLICABLE",
            "STRUCTURAL",
            "BROCHURE",
            "BELOW SHIP GATE",
            "INFEASIBLE",
            "SKIP",
        ),
    ),
)

_URL_RE = re.compile(r"https?://[^\s|)<>\]`'\"]+")
_BARE_DOMAIN_RE = re.compile(r"\b(?:[a-z0-9-]+\.)+[a-z]{2,}\b", re.IGNORECASE)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _country_dirs() -> list[Path]:
    """`configs/<region>/<subregion>/<country>/`, skipping `_examples` and friends."""
    return sorted(
        p
        for p in CONFIGS_DIR.glob("*/*/*")
        if p.is_dir() and not any(part.startswith("_") for part in p.relative_to(CONFIGS_DIR).parts)
    )


def seed_countries_and_configs(con: sqlite3.Connection) -> dict:
    now = _now()
    empty, n_configs = [], 0
    onboarded: dict[tuple[str, str], list[str]] = {}
    best_url: dict[tuple[str, str], str] = {}

    # A country can sit under two subregions (angola, libya and pakistan do as
    # of 2026-10-01), so stats are summed per country before the upsert; the
    # subregion with more YAMLs is recorded as the country's home.
    stats: dict[str, dict] = {}
    for cdir in _country_dirs():
        region, subregion, country = cdir.relative_to(CONFIGS_DIR).parts
        yamls = sorted(cdir.glob("*.yaml"))
        if not yamls:
            empty.append(country)
        s = stats.setdefault(
            country, {"homes": Counter(), "currencies": Counter(), "languages": set(), "n": 0}
        )
        s["homes"][(region, subregion)] += len(yamls)
        s["n"] += len(yamls)
        for path in yamls:
            raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            n_configs += 1
            if raw.get("currency"):
                s["currencies"][raw["currency"]] += 1
            if raw.get("language"):
                s["languages"].add(raw["language"])
            for url in [raw.get("url"), *(raw.get("start_urls") or [])]:
                domain = url and registrable_domain(url)
                if not domain:
                    continue
                key = (country, domain)
                onboarded.setdefault(key, [])
                if path.stem not in onboarded[key]:
                    onboarded[key].append(path.stem)
                best_url.setdefault(key, url)

    for country, s in stats.items():
        region, subregion = s["homes"].most_common(1)[0][0]
        con.execute(
            """INSERT INTO countries (country, region, subregion, currency, languages, n_sources)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT (country) DO UPDATE SET
                 region = excluded.region, subregion = excluded.subregion,
                 currency = excluded.currency, languages = excluded.languages,
                 n_sources = excluded.n_sources""",
            (
                country,
                region,
                subregion,
                s["currencies"].most_common(1)[0][0] if s["currencies"] else None,
                ",".join(sorted(s["languages"])) or None,
                s["n"],
            ),
        )

    for (country, domain), sources in onboarded.items():
        con.execute(
            """INSERT INTO candidates (country, domain, status, best_url, source_config, updated_at)
               VALUES (?, ?, 'onboarded', ?, ?, ?)
               ON CONFLICT (country, domain) DO UPDATE SET
                 status = 'onboarded', source_config = excluded.source_config,
                 updated_at = excluded.updated_at""",
            (country, domain, best_url[(country, domain)], ",".join(sources), now),
        )

    for engine, cap in ENGINE_CAPS.items():
        con.execute(
            "INSERT OR IGNORE INTO engines (engine, daily_cap) VALUES (?, ?)", (engine, cap)
        )

    return {
        "country_dirs": len(_country_dirs()),
        "countries": len(stats),
        "configs": n_configs,
        "empty_countries": empty,
        "onboarded_pairs": len(onboarded),
    }


def _map_status(cell: str) -> str:
    upper = cell.upper()
    for status, words in _STATUS_RULES:
        if any(w in upper for w in words):
            return status
    return "discovered"


def _split_row(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _domains_in(cell: str) -> list[tuple[str, str]]:
    """(domain, url) pairs from a URL cell; bare `example.com` mentions count too."""
    found, seen = [], set()
    urls = _URL_RE.findall(cell) or [f"https://{d}" for d in _BARE_DOMAIN_RE.findall(cell)]
    for url in urls:
        domain = registrable_domain(url)
        if domain and domain not in seen:
            seen.add(domain)
            found.append((domain, url.rstrip(".,;")))
    return found


def parse_inventory(path: Path) -> list[dict]:
    """Rows of every markdown table in one inventory that has a URL and a status column."""
    rows, cols = [], None
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.lstrip().startswith("|"):
            cols = None
            continue
        cells = _split_row(line)
        if cols is None:
            lower = [c.lower() for c in cells]
            url_i = next((i for i, c in enumerate(lower) if "url" in c), None)
            status_i = next(
                (i for i, c in enumerate(lower) if c in ("status", "verdict", "result")), None
            )
            cols = (url_i, status_i, lower) if url_i is not None and status_i is not None else False
            continue
        if not cols or set(line.replace("|", "").strip()) <= set("-: "):
            continue
        url_i, status_i, header = cols
        if max(url_i, status_i) >= len(cells):
            continue
        status_cell = cells[status_i].replace("**", "").strip()
        notes_i = next((i for i, c in enumerate(header) if "note" in c), None)
        note = cells[notes_i] if notes_i is not None and notes_i < len(cells) else ""
        for domain, url in _domains_in(cells[url_i]):
            rows.append(
                {
                    "domain": domain,
                    "url": url,
                    "status": _map_status(status_cell),
                    "status_text": status_cell,
                    "note": note,
                }
            )
    return rows


def seed_inventories(con: sqlite3.Connection) -> dict:
    now = _now()
    known = {r[0] for r in con.execute("SELECT country FROM countries")}
    inserted, by_status, unmatched = 0, Counter(), []
    for path in sorted(INVENTORIES_DIR.glob("*/*.md")):
        if path.name.startswith("_") or path.name == "README.md":
            continue
        country = path.stem
        if country not in known:
            unmatched.append(str(path.relative_to(INVENTORIES_DIR)))
            continue
        for row in parse_inventory(path):
            note = f"inventory: {row['status_text']} | {row['note']}"[:1000]
            reason = (
                row["status_text"][:200] if row["status"] in ("rejected", "blocked_plain") else None
            )
            cur = con.execute(
                """INSERT OR IGNORE INTO candidates
                   (country, domain, status, best_url, reason, notes, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (country, row["domain"], row["status"], row["url"], reason, note, now),
            )
            if cur.rowcount:
                inserted += 1
                by_status[row["status"]] += 1
    return {"inventory_inserted": inserted, "by_status": dict(by_status), "unmatched": unmatched}
