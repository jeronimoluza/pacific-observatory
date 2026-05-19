#!/usr/bin/env python3
"""Re-run the date cleaner on existing news.csv files, in place.

Use when handle_mixed_dates (or another cleaner) was updated to parse a format
that the original scrape couldn't. Avoids re-scraping by normalizing the raw
`date` column using the updated cleaner.

Usage:
    poetry run python scripts/reclean_dates.py <path_to_news.csv> [...]

The script preserves the raw value if the cleaner returns empty.
"""

from __future__ import annotations

import csv
import logging
import re
import shutil
import sys
from pathlib import Path

# Add src/ to path so imports work
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "src"))

# Silence the warn-per-failure flood from the cleaner
logging.getLogger("text.scrapers.pipelines.cleaning.common").setLevel(logging.ERROR)

from text.scrapers.pipelines.cleaning.common import handle_mixed_dates  # noqa: E402

# Common URL-embedded date pattern: /YYYY/MM/DD/
_URL_DATE_RE = re.compile(r"/(\d{4})/(\d{2})/(\d{2})/")
# e.g. epravda: /date_DDMMYYYY/
_URL_DATE2_RE = re.compile(r"/date_(\d{2})(\d{2})(\d{4})/")


def _fallback_url_date(url: str) -> str:
    if not url:
        return ""
    m = _URL_DATE_RE.search(url)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    m = _URL_DATE2_RE.search(url)
    if m:
        return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    return ""


_ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _looks_iso(s: str) -> bool:
    return bool(_ISO_RE.match(s or ""))


def reclean(path: Path) -> tuple[int, int]:
    """Return (rows_changed, rows_total)."""
    if not path.exists():
        raise FileNotFoundError(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    changed = 0
    total = 0
    with path.open(newline="", encoding="utf-8") as fin, tmp.open(
        "w", newline="", encoding="utf-8"
    ) as fout:
        reader = csv.DictReader(fin)
        if "date" not in (reader.fieldnames or []):
            raise ValueError(f"{path}: no 'date' column")
        writer = csv.DictWriter(fout, fieldnames=reader.fieldnames)
        writer.writeheader()
        for row in reader:
            total += 1
            raw = row.get("date", "")
            url = row.get("url", "")
            if raw and not _looks_iso(raw):
                new = handle_mixed_dates(raw)
                if not _looks_iso(new):
                    # Cleaner couldn't normalise — fall back to URL-embedded date
                    new = _fallback_url_date(url) or new
                if new and new != raw:
                    row["date"] = new
                    changed += 1
            elif not raw:
                # Missing date: try URL extraction
                new = _fallback_url_date(url)
                if new:
                    row["date"] = new
                    changed += 1
            writer.writerow(row)
    shutil.move(str(tmp), str(path))
    return changed, total


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 1
    for p in argv:
        path = Path(p)
        try:
            changed, total = reclean(path)
            print(f"{path}: {changed:,}/{total:,} rows updated")
        except Exception as e:
            print(f"{path}: ERROR {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
