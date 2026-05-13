"""
Pre-seed a source's failed_urls_seen.csv with all currently-pending URLs.

This is a TEMPLATE. The skill copies it to /tmp/seed_<source>_ledger.py and
fills in CONFIG_REGION_PATH and the human-readable LAST_ERROR before running.

Why this exists: when a stuck source's pending URLs are diagnosed as
permanently unscrapeable (live site renders no body — pattern 1 in
known_stuck_patterns.md), the only durable fix is to mark them as known-bad
in the failure ledger so future runs skip them. Live-run failures don't
persist to the ledger reliably (project_text_failure_ledger_bug). Pre-seeding
sidesteps that entirely.

Properties:
- Idempotent: re-running won't double-seed (existing rows preserved).
- Preserves any pre-existing operator-curated entries — those rows survive
  unchanged, only their key URL set is checked for duplicates.
- Atomic-ish: writes to LEDGER_CSV directly with a complete header. If the
  script is interrupted partway, the result is partial but well-formed.

Usage:
    poetry run python /tmp/seed_<source>_ledger.py

Run from repo root.
"""
import csv
from datetime import datetime, timezone
from pathlib import Path

# === FILL IN BEFORE RUNNING ==================================================

# Repo root.
REPO = Path("/Users/jeronimoluza/wb/pacificobservatory/repo/template-repo")

# Path under data/text/ from REPO root, e.g. "lac/caribbean/cuba/cubanet"
SRC_REL = "<region>/<subregion>/<country>/<source>"

# Human-readable cause for the operator's later forensic eyes.
# Examples used in past seeds:
#   "live site renders no article body (excerpt-only / image-only post)"
#   "theme-post-content widget missing on live site (excerpt-only)"
#   "post deprecated; HTML returns only footer textwidget"
LAST_ERROR = "<one-line description of why these URLs are permanently broken>"

# === END FILL-IN ============================================================

SRC_DIR = REPO / "data" / "text" / SRC_REL
NEWS_CSV = SRC_DIR / "news.csv"
URLS_CSV = SRC_DIR / "urls.csv"
LEDGER_CSV = SRC_DIR / "failed_urls_seen.csv"

LEDGER_COLUMNS = [
    "url",
    "first_failed_at",
    "last_failed_at",
    "attempts",
    "last_status",
    "last_error",
]


def main() -> None:
    # Preserve any existing ledger entries (don't clobber operator-curated rows).
    existing: dict[str, dict] = {}
    if LEDGER_CSV.exists():
        with LEDGER_CSV.open() as f:
            for row in csv.DictReader(f):
                u = row.get("url", "")
                if u:
                    existing[u] = row
        print(f"existing ledger entries: {len(existing)}")

    news = set()
    with NEWS_CSV.open() as f:
        for row in csv.DictReader(f):
            u = row.get("url", "")
            if u:
                news.add(u)

    pending = []
    seen = set()
    with URLS_CSV.open() as f:
        for row in csv.DictReader(f):
            u = row.get("url", "")
            if u and u not in news and u not in seen:
                pending.append(u)
                seen.add(u)

    print(f"news.csv URLs:    {len(news)}")
    print(f"urls.csv pending: {len(pending)}")

    ts = datetime.now(timezone.utc).isoformat()
    last_error = f"pre-seeded: {LAST_ERROR}"

    with LEDGER_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=LEDGER_COLUMNS)
        w.writeheader()
        # Existing rows first (preserved verbatim).
        for url, row in existing.items():
            w.writerow({k: row.get(k, "") for k in LEDGER_COLUMNS})
        # New pending rows (skipped if already in existing).
        added = 0
        for u in pending:
            if u in existing:
                continue
            w.writerow(
                {
                    "url": u,
                    "first_failed_at": ts,
                    "last_failed_at": ts,
                    "attempts": "1",
                    "last_status": "NO_BODY",
                    "last_error": last_error,
                }
            )
            added += 1

    total = len(existing) + added
    print(f"Existing kept:    {len(existing)}")
    print(f"Newly seeded:     {added}")
    print(f"Total in ledger:  {total}")
    print(f"Wrote {LEDGER_CSV} ({LEDGER_CSV.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
