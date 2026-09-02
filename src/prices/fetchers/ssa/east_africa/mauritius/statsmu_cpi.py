"""Statistics Mauritius — monthly Consumer Price Index, 13-division breakdown.

Statistics Mauritius (statsmauritius.govmu.org) publishes a monthly CPI
press release as a PDF, linked from
`/Pages/Statistics/Monthly/Monthly-CPI.aspx` (current year only -- prior
years live behind a separate "Archive Collections 2014-2025" page with
145+ PDFs in inconsistent naming/format across a decade and are out of
scope for this fetcher; see notes below). Re-verified live 2026-09-01:
HTTP 200, 7 PDFs linked for 2026 (Jan-Jul), each a clean, text-extractable
PDF (unlike CEB's Government Gazette PDFs, which embed a non-standard
font) -- confirmed with `pdfplumber`.

Each release's page 2 (the page whose text contains "All Divisions")
carries a "Sub-indices for the thirteen divisions of consumption
expenditure" table: two month columns (prior, current) plus a % change
column, for COICOP-2018 divisions 1-13. The table only degrades cleanly
into these three numbers per division, not into (name, value, value,
change) tuples -- pdfplumber's text order interleaves the two-line
division names (5, 13) with the number line, e.g.:
    "5. Furnishings, household equipment and routine\\n113.6 113.9 +0.3\\nhousehold maintenance"
So this fetcher does not attempt to read the division NAME text at all;
division identity comes only from the leading "N. " marker matched at
line-start, in fixed 1-13 order, and the (prior, current, change) values
are pulled from the first "value value change" pattern found inside the
chunk between one division marker and the next.

The headline "All Divisions" row is dropped -- there is no sanctioned
COICOP sentinel for the all-items index (see the skill's open design
question); "All Divisions, excluding Alcoholic beverages and tobacco" is
dropped for the same reason.

DISCOVERY SCOPE: only the current-year listing page is walked -- the
archive page exists back to 2014 but mixes "Core_<month><year>.pdf"
(a different, narrower core-inflation bulletin, not this 13-division
table) with the main CPI release under wildly inconsistent filenames
(spaces, %20-encoded, "cpijan14.pdf" vs "CPI_M_Jul24_070824.pdf") across
a decade -- a full historical backfill parser for that archive is a real,
documented follow-up, not attempted here. `fallback_date` is therefore
set to just before the current year's first release so run 1 picks up
the full 2026 series that IS reliably discoverable.

Currency/units: none -- this is an index (base "January - December 2023
= 100"), not a price level. analytical_role: cpi_benchmark (IndexObservation).
coicop_classification: publisher_labeled (Statistics Mauritius's own
13-division COICOP-2018 numbering is used directly, division N -> "0N").
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

_COUNTRY = "Mauritius"
_SOURCE_KEY = "statsmu_cpi"
_BASE_PERIOD = "Jan-Dec 2023=100"
_IDENT = ["source_key", "observation_date", "coicop_code"]
_LISTING_URL = (
    "https://statsmauritius.govmu.org/Pages/Statistics/Monthly/Monthly-CPI.aspx"
)
_SITE_ROOT = "https://statsmauritius.govmu.org"

_PDF_LINK_RE = re.compile(
    r'href="(/Documents/Statistics/Monthly/CPI/\d{4}/[^"]+\.pdf)"', re.IGNORECASE
)
_MONTHS = {
    "JANUARY": 1,
    "FEBRUARY": 2,
    "MARCH": 3,
    "APRIL": 4,
    "MAY": 5,
    "JUNE": 6,
    "JULY": 7,
    "AUGUST": 8,
    "SEPTEMBER": 9,
    "OCTOBER": 10,
    "NOVEMBER": 11,
    "DECEMBER": 12,
}
_HEADER_RE = re.compile(r"CONSUMER PRICE INDEX FOR\s+([A-Z]+)\s+(\d{4})", re.IGNORECASE)
# Fallback for releases whose title omits "FOR <MONTH> <YEAR>" (seen on the
# January 2026 release, titled just "CONSUMER PRICE INDEX") -- the opening
# paragraph's "... to <value>\nin <Month> <Year>." always names the report
# month, so this is used as a second lookup rather than failing the PDF.
_PERIOD_FALLBACK_RE = re.compile(
    r"to\s+[\d.]+\s*\n?\s*in\s+([A-Za-z]+)\s+(\d{4})", re.IGNORECASE
)
_DIVISION_START_RE = re.compile(r"(?:^|\n)(\d{1,2})\.\s")
_VALUE_RE = re.compile(r"([\d]+\.[\d]+)\s+([\d]+\.[\d]+)\s+([+\-]?[\d]+\.[\d]+|-)")


def _discover_pdf_urls(session) -> list[str]:
    resp = session.get(_LISTING_URL, timeout=30)
    if resp.status_code != 200:
        logger.warning(
            "[%s] HTTP %s for %s", _SOURCE_KEY, resp.status_code, _LISTING_URL
        )
        return []
    hrefs = sorted(set(_PDF_LINK_RE.findall(resp.text)))
    return [_SITE_ROOT + h for h in hrefs]


def _find_division_page_text(pdf: "pdfplumber.PDF") -> str | None:
    for page in pdf.pages:
        text = page.extract_text() or ""
        if "All Divisions" in text and "1. Food and non-alcoholic beverages" in text:
            return text
    return None


def _extract_period(all_text: str) -> date | None:
    m = _HEADER_RE.search(all_text)
    if not m:
        m = _PERIOD_FALLBACK_RE.search(all_text)
    if not m:
        return None
    month_name, year = m.group(1).upper(), int(m.group(2))
    month = _MONTHS.get(month_name)
    if month is None:
        return None
    return date(year, month, 1)


def _extract_division_rows(page_text: str) -> dict[int, float]:
    start = page_text.index("1. Food and non-alcoholic beverages")
    end = page_text.index("All Divisions", start)
    sub = page_text[start:end]

    matches = list(_DIVISION_START_RE.finditer(sub))
    bounds = [(int(m.group(1)), m.start()) for m in matches]
    out: dict[int, float] = {}
    for i, (num, pos) in enumerate(bounds):
        chunk_end = bounds[i + 1][1] if i + 1 < len(bounds) else len(sub)
        chunk = sub[pos:chunk_end]
        vm = _VALUE_RE.search(chunk)
        if not vm:
            continue
        try:
            out[num] = float(vm.group(2))  # current-month index value
        except ValueError:
            continue
    return out


def _rows_for_pdf(pdf_bytes: bytes, url: str, cutoff: date) -> list[dict]:
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        full_text = "\n".join(p.extract_text() or "" for p in pdf.pages)
        obs_date = _extract_period(full_text)
        if obs_date is None:
            logger.warning(
                "[%s] could not parse period header from %s", _SOURCE_KEY, url
            )
            return []
        if obs_date <= cutoff:
            return []
        page_text = _find_division_page_text(pdf)
        if page_text is None:
            logger.warning("[%s] no 13-division table found in %s", _SOURCE_KEY, url)
            return []

    division_values = _extract_division_rows(page_text)
    if len(division_values) != 13:
        logger.warning(
            "[%s] expected 13 divisions, parsed %d from %s",
            _SOURCE_KEY,
            len(division_values),
            url,
        )
    ts = get_scrape_ts()
    rows: list[dict] = []
    for num, value in sorted(division_values.items()):
        coicop = f"{num:02d}"
        row = {
            "observation_date": obs_date.isoformat(),
            "period_kind": "monthly_avg",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "coicop_code": coicop,
            "index_value": round(value, 2),
            "index_base_period": _BASE_PERIOD,
            "source_url": url,
            "notes": f"COICOP-2018 division {num}",
            "scrape_ts": ts,
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)
    return rows


def fetch_statsmu_cpi(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    pdf_urls = _discover_pdf_urls(session)
    if not pdf_urls:
        logger.info("[%s] no PDFs discovered on %s", _SOURCE_KEY, _LISTING_URL)
        return None

    all_rows: list[dict] = []
    for url in pdf_urls:
        try:
            resp = session.get(url, timeout=30)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[%s] fetch failed for %s: %s", _SOURCE_KEY, url, exc)
            continue
        if resp.status_code != 200 or not resp.content.startswith(b"%PDF"):
            logger.warning(
                "[%s] HTTP %s / non-PDF for %s", _SOURCE_KEY, resp.status_code, url
            )
            continue
        try:
            all_rows.extend(_rows_for_pdf(resp.content, url, cutoff))
        except Exception as exc:  # noqa: BLE001
            logger.warning("[%s] parse failed for %s: %s", _SOURCE_KEY, url, exc)
            continue

    if not all_rows:
        logger.info("[%s] no new rows past cutoff=%s", _SOURCE_KEY, cutoff)
        return None

    logger.info(
        "[%s] %d rows across %d PDF(s) (cutoff=%s)",
        _SOURCE_KEY,
        len(all_rows),
        len(pdf_urls),
        cutoff,
    )
    return pd.DataFrame(all_rows)
