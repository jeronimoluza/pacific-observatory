"""Shared discovery helper for Burkina Faso INSD price publications.

INSD (Institut National de la Statistique et de la Démographie) publishes one
monthly workbook — "NOTE_IHPC_Base_2023_de_<MOIS>_<ANNEE>.xlsx" (or .xls) —
linked from the "statistiques-des-prix" page. That single workbook carries
BOTH tables this shard onboards as separate sources:

- Sheet with a "Libellé" / 4-digit NCOA-IHPC code column ("Tableau 5 :
  Évolution des indices nationaux suivant les groupes de la NCOA-IHPC") ->
  `insd_ihpc_cpi.py` (cpi_benchmark, IndexObservation).
- Sheet with a "PRODUITS" / "Unités" column and 13 region columns
  ("Tableau 4 : Prix moyens de quelques produits essentiels au niveau
  régional") -> `insd_avg_prices.py` (official_avg, PriceObservation).

Both fetchers call `find_latest_note_url()` independently (one extra GET of a
small HTML page is not worth a shared cache), then `open_workbook()` to parse
whichever sheet they need.

Discovery: the page lists monthly releases going back over a year, mixing
.pdf (most months) and .xlsx/.xls (available for the ~2 most recent months
only, at least as observed 2026-09-01). Only .xlsx/.xls links are matched —
this fetcher does not parse PDF, so in a month where only a PDF is published,
`find_latest_note_url()` returns the previous month's spreadsheet, and this
month's data is picked up automatically once next month's release goes out
in the runs after it. That is a real gap (not a bug to silently patch): a
month can be skipped if the .pdf-only window persists across two releases.
"""

from __future__ import annotations

import logging
import re

import pandas as pd
import requests

logger = logging.getLogger(__name__)

_LISTING_URL = (
    "https://www.insd.bf/fr/statistiques/statistiques-economiques/statistiques-des-prix"
)
_BASE = "https://www.insd.bf"

_FILE_RE = re.compile(
    r'href="\s*(/sites/default/files/[^"]+NOTE_IHPC[^"]*\.xlsx?)"',
    re.IGNORECASE,
)
_FOLDER_RE = re.compile(r"/sites/default/files/(\d{4})-(\d{2})/")

FR_MONTHS = {
    "janvier": 1,
    "fevrier": 2,
    "février": 2,
    "mars": 3,
    "avril": 4,
    "mai": 5,
    "juin": 6,
    "juillet": 7,
    "aout": 8,
    "août": 8,
    "septembre": 9,
    "octobre": 10,
    "novembre": 11,
    "decembre": 12,
    "décembre": 12,
}


def find_latest_note_url(session: requests.Session) -> str | None:
    try:
        r = session.get(_LISTING_URL, timeout=30)
        r.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.warning("insd_bfa: listing page fetch failed: %s", exc)
        return None
    matches = _FILE_RE.findall(r.text)
    if not matches:
        logger.warning("insd_bfa: no NOTE_IHPC .xlsx/.xls links found on listing page")
        return None

    def _sort_key(href: str) -> tuple[str, str]:
        m = _FOLDER_RE.search(href)
        return (m.group(1), m.group(2)) if m else ("0000", "00")

    latest = max(matches, key=_sort_key)
    return _BASE + latest.strip()


def open_workbook(session: requests.Session, url: str) -> pd.ExcelFile | None:
    try:
        resp = session.get(url, timeout=60)
        resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.warning("insd_bfa: workbook fetch failed for %s: %s", url, exc)
        return None
    from io import BytesIO

    try:
        return pd.ExcelFile(BytesIO(resp.content))
    except Exception as exc:  # noqa: BLE001
        logger.warning("insd_bfa: could not open workbook %s: %s", url, exc)
        return None
