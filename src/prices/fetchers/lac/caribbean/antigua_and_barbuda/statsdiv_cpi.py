"""Statistics Division of Antigua and Barbuda -- monthly Consumer Price Index.

The CPI landing page (`_LISTING_URL`) links one PDF per month, filed under
`/wp-content/uploads/<upload-year>/<upload-month>/Monthly-CPI-<Month>-<Year>.pdf`.
The upload folder is NOT the report period -- several recent reports (e.g.
April 2026) are filed under a stale 2022/11 folder, so the report's real
period is read from the filename only, never the URL path. Filenames are
inconsistent: some omit the dash before the year ("Monthly-CPI-September2013.pdf"),
one carries a confirmed typo ("Monthly-CPI-Janaury-2026.pdf" for January),
and several carry a disambiguating numeric/letter suffix before ".pdf"
("-1", "-2", "-R"). The fetcher parses every linked filename, keeps only
ones matching "Monthly-CPI-<Month><Year>", and picks the max by
(year, month) rather than trusting listing order or the upload path.

`statistics.gov.ag` (*.gov.ag, Sectigo-issued) serves an incomplete
certificate chain -- confirmed with `openssl s_client -showcerts` (1
certificate returned, no intermediate) -- the same "NSO portal SSL
certificate failures" class as vnso_cpi.py/known_blockers.md, not a bot
block. verify=False is that class's documented workaround.

Each PDF's Table 2 ("CPI and Inflation Rate for Main Categories, Sub-groups
and Sections") lists, per row: category name, Jan-2006 weight, then three
CPI index levels for [report month, prior month, same month last year], then
year-on-year and month-to-month % change. Only the 12 ALL-CAPS main-category
rows are extracted (sub-group/section rows below them are ignored); the
report-month index (first of the three index columns) is the value emitted.
"All Items" (the headline row) is dropped -- no sanctioned headline sentinel,
per onboarding doctrine.

Antigua and Barbuda's 12 main categories are, in the PDF's own order, the
*standard* (pre-2018) COICOP divisions 01-12 verbatim -- Restaurants and
Hotels is already its own division 11 and Miscellaneous Goods and Services
is division 12, unlike sibling Pacific CPI fetchers (Fiji/Vanuatu) that had
to fold a missing division into COICOP 13. No such remapping is needed here;
confirmed by matching all 12 category labels 1:1 against Table 1's own
"Main Expenditure Categories" list on the PDF's second page.

Long sub-group category names (e.g. "Furnishings, Household Equipment and
Routine Household Maintenance") wrap across two visual lines in the PDF with
the numeric row sandwiched between them; the main-category regex only
anchors on the first line of the label, which is enough to disambiguate
against every other row.

Smoke run: 12/12 rows extracted from the June 2026 release (the latest
at fetch time, released 22 Jul 2026), single currency n/a (index series,
not priced), values cross-checked by hand against the source PDF text.
"""

from __future__ import annotations

import io
import logging
import re
from datetime import date

import pandas as pd
import pdfplumber
import urllib3

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

# statistics.gov.ag serves an incomplete cert chain -- see module docstring.
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_LISTING_URL = "https://statistics.gov.ag/subjects/consumer-price-index/"
_COUNTRY = "Antigua and Barbuda"
_SOURCE_KEY = "ag_statsdiv_cpi"
_BASE_PERIOD = "Jan2006=100"
_IDENT = ["source_key", "observation_date", "coicop_code"]

_MONTH_NUM = {
    "january": 1,
    "janaury": 1,  # typo confirmed in "Monthly-CPI-Janaury-2026.pdf"
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}

# (regex label as it appears in Table 2, COICOP division)
_CATEGORY_COICOP = [
    ("FOOD AND NON-ALCOHOLIC BEVERAGES", "01"),
    ("ALCOHOLIC BEVERAGES, TOBACCO AND NARCOTICS", "02"),
    ("CLOTHING AND FOOTWEAR", "03"),
    ("HOUSING, WATER, ELECTRICITY, GAS AND OTHER FUELS", "04"),
    ("FURNISHINGS, HOUSEHOLD EQUIPMENT AND ROUTINE", "05"),
    ("HEALTH", "06"),
    ("TRANSPORT", "07"),
    ("COMMUNICATION", "08"),
    ("RECREATION AND CULTURE", "09"),
    ("EDUCATION", "10"),
    ("RESTAURANTS AND HOTELS", "11"),
    ("MISCELLANEOUS GOODS AND SERVICES", "12"),
]

_NUM = r"\(?-?[\d,]+\.\d+\)?"
_LINK_RE = re.compile(
    r'href="([^"]*Monthly-CPI-([A-Za-z]+)-?(\d{4})[^"]*\.pdf)"', re.IGNORECASE
)


def _find_latest_pdf_url(session) -> str | None:
    resp = session.get(_LISTING_URL, timeout=30, verify=False)
    resp.raise_for_status()
    matches = [
        (href, month.lower(), int(year))
        for href, month, year in _LINK_RE.findall(resp.text)
        if month.lower() in _MONTH_NUM
    ]
    if not matches:
        return None
    best = max(matches, key=lambda m: (m[2], _MONTH_NUM[m[1]]))
    href, month, year = best
    return href, date(year, _MONTH_NUM[month], 1)


def _parse_table2(text: str) -> list[tuple[str, float]]:
    results = []
    for label, coicop in _CATEGORY_COICOP:
        pat = re.compile(
            re.escape(label) + r"\s+(" + _NUM + r")\s+(" + _NUM + r")",
        )
        m = pat.search(text)
        if not m:
            continue
        # first captured number is the Jan-2006 weight, second is the
        # report-month CPI index level -- the value to emit.
        try:
            idx_val = float(m.group(2).strip("()"))
        except ValueError:
            continue
        results.append((coicop, idx_val))
    return results


def fetch_ag_statsdiv_cpi(cutoff: date) -> pd.DataFrame | None:
    session = get_session()

    found = _find_latest_pdf_url(session)
    if not found:
        logger.warning("[%s] Could not find a CPI PDF on %s", _SOURCE_KEY, _LISTING_URL)
        return None
    pdf_url, obs_date = found

    if obs_date <= cutoff:
        logger.info(
            "[%s] Latest release %s is not newer than cutoff", _SOURCE_KEY, obs_date
        )
        return None

    resp = session.get(pdf_url, timeout=60, verify=False)
    resp.raise_for_status()
    with pdfplumber.open(io.BytesIO(resp.content)) as pdf:
        # Table 2 is on page index 2 (0-based) in every release checked;
        # fall back to scanning all pages if that ever shifts.
        text = "\n".join(p.extract_text() or "" for p in pdf.pages)

    parsed = _parse_table2(text)
    if not parsed:
        logger.warning("[%s] No Table 2 rows parsed from %s", _SOURCE_KEY, pdf_url)
        return None

    rows = []
    for coicop, idx_val in parsed:
        row = {
            "observation_date": obs_date.isoformat(),
            "period_kind": "monthly_avg",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "coicop_code": coicop,
            "index_value": idx_val,
            "index_base_period": _BASE_PERIOD,
            "source_url": pdf_url,
            "scrape_ts": get_scrape_ts(),
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)

    return pd.DataFrame(rows) if rows else None
