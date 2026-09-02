"""Algemeen Bureau voor de Statistiek (ABS) Suriname -- monthly CPI.

ABS publishes one PDF per month at statistics-suriname.org (confirmed live
2026-09-01: continuous monthly releases from 2008 through Jul 2026,
released ~21st of the following month). Each release's own historical
table ("Prijsindexcijfers / Index Numbers ... Hoofdgroepen / Major Groups
(Divisions)") carries a ROLLING ~24-MONTH window of national index values
per division, not just the current month -- so downloading only the
single most-recently-published PDF is enough to backfill roughly two
years of history in one run; subsequent runs re-download the (new)
latest PDF and the cutoff filter naturally picks up only the newly
published month(s).

The listing page at `_LISTING_URL` links every historical PDF under
/wp-content/uploads/<year>/<month>/ -- "latest" is picked by the max
(upload-year, upload-month) folder in the URL path, which tracks
publish date for a strictly-recurring monthly report.

Division-level table parsing gotcha (confirmed live 2026-09-01,
pdfplumber `extract_tables()`): the table occasionally renders a
two-month period label in ONE cell as "Feb\\nMrt" (a PDF text-layout
merge) while that row's own values actually belong to the FIRST of the
two labels (Feb); the values for the second label (Mrt) appear on the
*next* row, whose own period cell is None. Handled by queuing the
second+ line of any multi-line period cell for the following None-
labelled row(s).

Suriname's own "Hoofdgroepen" numbering follows COICOP-2018 division
numbering directly for 10 of its 11 groups (1-8, 11, 12). Group "9/10"
(Recreatie, Cultuur en Onderwijs) bundles COICOP 09 (Recreation &
Culture) and 10 (Education) into one published value with no way to
split it -- dropped, following the SingStat precedent in this skill's
fetcher_pattern.md (a bundled group that doesn't cleanly map to a single
COICOP code is left unmapped, not sentinel-coded). The "Totaal"
(all-items headline) column is also dropped: IndexObservation has no
sanctioned sentinel for headline CPI yet (open design question in
SKILL.md).
"""

from __future__ import annotations

import io
import logging
import re
from datetime import date

import pandas as pd
import pdfplumber

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_LISTING_URL = (
    "https://statistics-suriname.org/consumenten-prijs-indexcijfers-en-inflatie/"
)
_COUNTRY = "Suriname"
_SOURCE_KEY = "sr_abs_cpi"
_BASE_PERIOD = "Apr-Jun 2016=100"
_IDENT = ["source_key", "observation_date", "coicop_code"]

# Suriname's own division numbering IS the COICOP-2018 division number for
# every group except the bundled "9/10" (dropped -- see module docstring).
_DIVISION_TO_COICOP = {
    "1": "01",
    "2": "02",
    "3": "03",
    "4": "04",
    "5": "05",
    "6": "06",
    "7": "07",
    "8": "08",
    "11": "11",
    "12": "12",
}

_MONTH_NUM = {
    "jan": 1,
    "feb": 2,
    "mrt": 3,
    "apr": 4,
    "mei": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "sept": 9,
    "okt": 10,
    "nov": 11,
    "dec": 12,
}

_PDF_RE = re.compile(
    r'href="(https?://[^"]*?/wp-content/uploads/(\d{4})/(\d{2})/[^"]*\.pdf)"',
    re.IGNORECASE,
)


def _latest_pdf_url(session) -> str | None:
    resp = session.get(_LISTING_URL, timeout=30)
    resp.raise_for_status()
    candidates = [(int(y), int(m), url) for url, y, m in _PDF_RE.findall(resp.text)]
    if not candidates:
        return None
    candidates.sort()
    return candidates[-1][2]


def _month_year(label: str, current_year: list[int]) -> tuple[int, int] | None:
    """Parse a period label like "Aug '24" or "Sept" into (year, month).

    `current_year` is a 1-element list used as a mutable box so this
    function can update the running year when a label carries an explicit
    "'YY" marker (which happens at least once per calendar year in this
    table).
    """
    label = label.strip().lstrip("*").strip()
    if not label:
        return None
    if "'" in label:
        name_part, yy = label.split("'", 1)
        yy_digits = re.match(r"\d+", yy.strip())
        if not yy_digits:
            return None
        current_year[0] = 2000 + int(yy_digits.group())
        name_part = name_part.strip().lower()
    else:
        name_part = label.lower()
    month = _MONTH_NUM.get(name_part)
    if month is None:
        return None
    return current_year[0], month


def _find_division_table(pdf: "pdfplumber.PDF") -> list[list] | None:
    for page in pdf.pages:
        for table in page.extract_tables():
            for row in table:
                if row and row[0] == "Period(e)":
                    return table
    return None


def _coicop_columns(header_row: list) -> dict[int, str]:
    """Map column index -> COICOP code from the header row's own labels.

    Reads column identity from the header text itself (not fixed
    positions) so a future column reorder wouldn't silently mismap
    values.
    """
    out = {}
    for c, label in enumerate(header_row):
        if label is None:
            continue
        label = str(label).strip()
        coicop = _DIVISION_TO_COICOP.get(label)
        if coicop:
            out[c] = coicop
        elif label == "9/10":
            logger.info(
                "[%s] Dropping bundled Recreation+Education column ('9/10') "
                "-- no single COICOP code applies",
                _SOURCE_KEY,
            )
    return out


def _parse_division_table(table: list[list]) -> list[dict]:
    header_row = table[1]
    col_to_coicop = _coicop_columns(header_row)
    if not col_to_coicop:
        logger.warning("[%s] No mappable division columns in header row", _SOURCE_KEY)
        return []

    current_year = [0]
    pending_labels: list[str] = []
    out = []

    for row in table[2:]:
        period_cell = row[0]
        if period_cell is not None and "\n" in str(period_cell):
            parts = [p for p in str(period_cell).split("\n") if p.strip()]
            label, pending_labels = parts[0], parts[1:] + pending_labels
        elif period_cell is None or not str(period_cell).strip():
            if not pending_labels:
                continue
            label, pending_labels = pending_labels[0], pending_labels[1:]
        else:
            label = str(period_cell)

        parsed = _month_year(label, current_year)
        if parsed is None:
            continue
        year, month = parsed
        obs_date = date(year, month, 1)

        for col, coicop in col_to_coicop.items():
            if col >= len(row):
                continue
            raw = row[col]
            if raw is None:
                continue
            try:
                value = float(str(raw).strip())
            except ValueError:
                continue
            out.append(
                {
                    "observation_date": obs_date,
                    "coicop_code": coicop,
                    "index_value": value,
                }
            )

    return out


def fetch_sr_abs_cpi(cutoff: date) -> pd.DataFrame | None:
    session = get_session()

    try:
        pdf_url = _latest_pdf_url(session)
    except Exception:
        logger.exception(
            "[%s] Failed to list releases from %s", _SOURCE_KEY, _LISTING_URL
        )
        return None
    if not pdf_url:
        logger.warning(
            "[%s] No CPI release PDFs found on %s", _SOURCE_KEY, _LISTING_URL
        )
        return None

    try:
        pdf_resp = session.get(pdf_url, timeout=60)
        pdf_resp.raise_for_status()
        with pdfplumber.open(io.BytesIO(pdf_resp.content)) as pdf:
            table = _find_division_table(pdf)
    except Exception:
        logger.exception("[%s] Failed to fetch/parse %s", _SOURCE_KEY, pdf_url)
        return None

    if table is None:
        logger.warning("[%s] Division table not found in %s", _SOURCE_KEY, pdf_url)
        return None

    parsed = _parse_division_table(table)
    if not parsed:
        return None

    rows = []
    for entry in parsed:
        if entry["observation_date"] <= cutoff:
            continue
        row = {
            "observation_date": entry["observation_date"].isoformat(),
            "period_kind": "monthly_avg",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "coicop_code": entry["coicop_code"],
            "index_value": entry["index_value"],
            "index_base_period": _BASE_PERIOD,
            "source_url": pdf_url,
            "scrape_ts": get_scrape_ts(),
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)

    return pd.DataFrame(rows) if rows else None
