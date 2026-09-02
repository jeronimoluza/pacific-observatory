"""CEB (Central Electricity Board) — residential electricity tariff, Mauritius.

CEB's "Electricity Tariffs and Applicable Rates" page
(https://ceb.mu/customer-corner/electricity-tariffs-and-applicable-rates)
links a static PDF (`files/files/tariffs/CEBTARIFFS.pdf`) issued by the
Utility Regulatory Authority, an 8-page table of every consumer/tariff
class. This fetcher scopes to page 1 only: "Residential consumers -
Tariffs 110A, 110, 120 and 140" -- the standard household block tariff,
12 consumption bands (0-24 kWh/month up to 2,001+), Rs/kWh. Same narrow-
scope convention as cie_tariff.py (Cote d'Ivoire) and
seeg_electricity_tariff.py (Gabon): commercial/industrial/sugar-factory/
street-lighting/irrigation tariffs on the later pages are out of scope.

PDF text quirk: pdfplumber's extract_text() splits some cells across a
stray space, e.g. "8.77" renders as two tokens "8" ".77" (confirmed on
every band from 301-500 kWh upward). Fixed with a regex merge
(`re.sub(r"(\\d)\\s+(\\.\\d+)", r"\\1\\2", ...)`) before tokenizing --
without it the row has 4 numeric tokens instead of 3 and the wrong one
gets picked up as the price.

Each data row carries three numbers: the tariff effective 01 February
2023, the tariff effective 01 February 2024, and a final "Rate" column
that in every observed row equals the Feb-2024 figure. This fetcher takes
the LAST number on the row (the "Rate" column) as `price_local` -- the
schedule's own statement of what currently applies -- and the header's
"Effective 01 February 2024" as `observation_date`.

STALENESS (found, not fixed): CEB has since published a further increase
via Government Gazette General Notice No. 473 of 2026 ("30 April 2026"),
effective 1 May 2026, adjusting rates by up to 15% -- confirmed by reading
the notice text via OCR page-render (`pdftoppm` + inspection), which
states "the revised tariffs shall take effect as from 1 May 2026" and
explicitly "no restructuring of existing tariffs is effected" (same band
structure). However the notice's own PDF
(files/files/publications/regulations/electricity_tariff_2026.pdf) embeds
a non-standard font with no usable ToUnicode map: both pdfplumber and
`pdftotext -layout` return CID/private-use-area garbage instead of text,
and OCR of the actual Appendix rate tables was out of scope for this
onboarding pass. CEBTARIFFS.pdf (Feb 2024 rates) is shipped instead as the
last machine-readable published schedule; the May-2026 revision is a known
gap for a follow-up run, not a silent staleness.

Currency: MUR (Mauritius; matches countries.yaml, and the PDF's own "Rs"
header).

COICOP: 04.5.1 (electricity), narrow.
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

_TARIFF_PAGE_URL = (
    "https://ceb.mu/customer-corner/electricity-tariffs-and-applicable-rates"
)
_PDF_URL = "https://ceb.mu/files/files/tariffs/CEBTARIFFS.pdf"
_COUNTRY = "Mauritius"
_CURRENCY = "MUR"
_SOURCE_KEY = "ceb_electricity_tariff"
_COICOP_CODE = "04.5.1"
_IDENT = ["source_key", "observation_date", "item_name"]

_SPLIT_DECIMAL_RE = re.compile(r"(\d)\s+(\.\d+)")
_ROW_RE = re.compile(
    r"^(?P<band>\d[\d,]*\s+to\s+[\d,]+|\d[\d,]*\s+and\s+Above)\s+(?P<tail>[\d.,\s]+)$"
)
_MONTH_NAMES = (
    "January|February|March|April|May|June|July|August|"
    "September|October|November|December"
)
# Header prints BOTH effective dates on one line, e.g.
# "February 2023 February 2024" -- NOT "Effective 01 <month> <year>"
# adjacent (that literal text is split across the PREVIOUS line, "Effective
# 01 Effective 01"). Matching on "Effective 01" directly only ever finds the
# first (stale) date, so this pattern matches the two month/year pairs on
# their own shared line and takes the SECOND (newer) one instead.
_EFFECTIVE_HEADER_RE = re.compile(
    rf"({_MONTH_NAMES})\s+(\d{{4}})\s+({_MONTH_NAMES})\s+(\d{{4}})"
)
_MONTHS = {
    "January": 1,
    "February": 2,
    "March": 3,
    "April": 4,
    "May": 5,
    "June": 6,
    "July": 7,
    "August": 8,
    "September": 9,
    "October": 10,
    "November": 11,
    "December": 12,
}


def _extract_effective_date(page1_text: str) -> date | None:
    m = _EFFECTIVE_HEADER_RE.search(page1_text)
    if not m:
        return None
    _, _, month_name, year = m.groups()  # second pair = the newer column
    return date(int(year), _MONTHS[month_name], 1)


def _residential_block(page1_text: str) -> list[str]:
    lines = page1_text.split("\n")
    rows: list[str] = []
    in_block = False
    for line in lines:
        if "Residential consumers" in line:
            in_block = True
            continue
        if in_block and ("Domestics Prosumers" in line or "Commercial" in line):
            break
        if in_block:
            rows.append(line)
    return rows


def fetch_ceb_electricity_tariff(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    resp = session.get(_PDF_URL, timeout=30)
    if resp.status_code != 200 or not resp.content.startswith(b"%PDF"):
        logger.warning(
            "[%s] HTTP %s / non-PDF response from %s",
            _SOURCE_KEY,
            resp.status_code,
            _PDF_URL,
        )
        return None

    with pdfplumber.open(io.BytesIO(resp.content)) as pdf:
        page1_text = pdf.pages[0].extract_text() or ""

    effective_date = _extract_effective_date(page1_text)
    if effective_date is None:
        logger.warning(
            "[%s] Could not find 'Effective 01 <Month> <Year>' header", _SOURCE_KEY
        )
        return None
    if effective_date <= cutoff:
        logger.info(
            "[%s] effective_date=%s <= cutoff=%s, skipping",
            _SOURCE_KEY,
            effective_date,
            cutoff,
        )
        return None

    rows: list[dict] = []
    for raw_line in _residential_block(page1_text):
        fixed = _SPLIT_DECIMAL_RE.sub(r"\1\2", raw_line)
        m = _ROW_RE.match(fixed.strip())
        if not m:
            continue
        band = m.group("band").strip()
        numbers = re.findall(r"[\d,]+\.\d+", m.group("tail"))
        if not numbers:
            continue
        price = float(numbers[-1].replace(",", ""))
        item_name = f"CEB residential tariff (110A/110/120/140), {band} kWh/month"
        row = {
            "observation_date": effective_date.isoformat(),
            "period_kind": "effective_from",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "coicop_code": _COICOP_CODE,
            "item_name": item_name,
            "price_local": price,
            "currency": _CURRENCY,
            "unit": "kWh",
            "source_url": _TARIFF_PAGE_URL,
            "notes": f"Residential block tariff, band {band} kWh/month",
            "scrape_ts": get_scrape_ts(),
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)

    if not rows:
        logger.warning("[%s] No residential tariff rows parsed", _SOURCE_KEY)
        return None

    logger.info(
        "[%s] %d residential tariff rows (effective %s)",
        _SOURCE_KEY,
        len(rows),
        effective_date,
    )
    return pd.DataFrame(rows)
