"""EWURA (Energy and Water Utilities Regulatory Authority) -- Tanzania
monthly INDICATIVE CAP retail petroleum prices, by town/region.

Confirmed live 2026-09-01. EWURA publishes a monthly "Public Notice on
Cap Prices for Petroleum Products" PDF at
https://www.ewura.go.tz/publications/petroleum-price, listing (page 1 of
the listing carries ~11 months back to Nov 2025 at fetch time):

    en-1788293771-Cap Prices for Petroleum Products for the Month of
    September 2026.pdf
    en-1786102239-Cap Prices for the Month of August 2026.pdf
    ...

Each PDF's page 0 states the effective date in a fixed phrase:
"...EFFECTIVE\nWEDNESDAY, 2nd SEPTEMBER 2026" -- parsed with
_EFFECTIVE_RE. "Table 3: Retail Cap Prices - TZS/Litre" (later pages)
lists one row per town/district ("S.No. Town Petrol Diesel Kerosene",
~186-190 towns per month) -- these are the prices retailers are legally
required to sell at (Table 1 is a 3-port summary, Table 2 is wholesale;
neither is used here). Row format varies slightly month to month
("1 Dar es Salaam 3,796 ..." vs "1. Dar es Salaam 3,898 ..." -- with or
without a trailing period after the row number) -- _ROW_RE tolerates
both.

THESE ARE CAPS, NOT OBSERVED TRANSACTION PRICES. EWURA sets a ceiling;
retailers may (and per the notice's own OMC-competition language,
sometimes do) sell below it. Do not treat these as retail transaction
prices in PPP analysis -- see the YAML notes.

Prices are plain-integer TZS per litre with comma thousands separators
(e.g. "3,796" -> 3796) -- comma stripped, no decimal invented.

subnational_area = town/district name, taken verbatim from the PDF. Note:
EWURA's own PDF text extraction occasionally splits a single town name
across two tokens with a stray space (e.g. "Pangani" renders as
"P angani" in the August 2026 PDF, "N ewala" for "Newala" in a different
month) -- a cosmetic artifact of EWURA's PDF generator/font, not a
fetcher bug. It does not cause duplicate observation_hash rows (each
month's own table has each town exactly once), but it does mean the same
real town can carry a differently-spaced name across different months;
downstream consumers matching towns across months should normalise
whitespace.

The `_IDENT` list below deliberately includes `subnational_area` -- this
fetcher publishes ~186-190 towns per product per month, so omitting it
would collapse the whole country into one row per (date, item) and
silently drop >99% of rows, exactly the wave-9 Mali defect referenced in
the onboarding brief.
"""

import logging
import re
from datetime import date
from io import BytesIO

import pandas as pd
import pdfplumber
from curl_cffi import requests as curl_requests

from prices.fetchers.utils import get_scrape_ts, make_hash

logger = logging.getLogger(__name__)

_LISTING_URL = "https://www.ewura.go.tz/publications/petroleum-price"
_SOURCE_URL = "https://www.ewura.go.tz/publications/petroleum-price"
_COUNTRY = "Tanzania"
_CURRENCY = "TZS"
_SOURCE_KEY = "tz_ewura_fuel_caps"
_UNIT = "L"
_IDENT = ["source_key", "observation_date", "item_name", "subnational_area"]

_ITEM_COICOP = {
    "Petrol": "07.2.2",
    "Diesel": "07.2.2",
    "Kerosene": "04.5.4",
}

_PDF_LINK_RE = re.compile(r'href="([^"]*/uploads/documents/[^"]*\.pdf)"', re.I)
_DOC_ID_RE = re.compile(r"en-(\d+)-")
_EFFECTIVE_RE = re.compile(
    r"EFFECTIVE\s*\n\s*[A-Z]+,\s*(\d{1,2})(?:ST|ND|RD|TH)?\s+([A-Z]+)\s+(\d{4})",
    re.I,
)
# Row format tolerates an optional "." after the row number (varies by
# month) and comma-grouped integer prices, e.g.:
#   "1 Dar es Salaam 3,796 3,877 3,713"
#   "15. Kibiti 3,928 4,008 4,034"
_ROW_RE = re.compile(
    r"^\s*\d{1,3}\.?\s+(.+?)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s*$", re.M
)

_MONTHS = {
    "january": 1,
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


def _list_cap_pdf_urls() -> list[str]:
    resp = curl_requests.get(_LISTING_URL, impersonate="chrome124", timeout=30)
    resp.raise_for_status()
    urls = []
    for m in _PDF_LINK_RE.finditer(resp.text):
        url = m.group(1)
        fname = url.rsplit("/", 1)[-1].lower()
        if "batch" in fname:
            continue  # e.g. "Public Notice Batch 30" -- not a cap-price schedule
        if "cap" not in fname:
            continue
        urls.append(url)
    return urls


def _parse_effective_date(text: str) -> date | None:
    m = _EFFECTIVE_RE.search(text)
    if not m:
        return None
    day, month_name, year = m.groups()
    month = _MONTHS.get(month_name.lower())
    if month is None:
        return None
    try:
        return date(int(year), month, int(day))
    except ValueError:
        return None


def _parse_retail_table(full_text: str) -> list[tuple[str, float, float, float]]:
    idx = full_text.find("Table 3")
    section = full_text[idx:] if idx >= 0 else full_text
    rows = []
    for town, petrol, diesel, kerosene in _ROW_RE.findall(section):
        try:
            rows.append(
                (
                    town.strip(),
                    float(petrol.replace(",", "")),
                    float(diesel.replace(",", "")),
                    float(kerosene.replace(",", "")),
                )
            )
        except ValueError:
            continue
    return rows


def fetch_tz_ewura_fuel_caps(cutoff: date) -> pd.DataFrame | None:
    scrape_ts = get_scrape_ts()
    try:
        pdf_urls = _list_cap_pdf_urls()
    except Exception:
        logger.exception("[%s] failed to list publications page", _SOURCE_KEY)
        return None

    # Keep the highest-doc-id PDF per effective date -- EWURA has
    # re-uploaded an identical duplicate under a second doc id at least
    # once (December 2025: en-1764709274 and en-1764709278, byte-identical
    # PDFs); a genuine correction would also land here and the higher id
    # (the later upload) wins, mirroring za_dmre_fuel.py's convention.
    best_by_date: dict[date, tuple[int, str]] = {}
    rows_by_date: dict[date, list[dict]] = {}

    for url in pdf_urls:
        doc_id_m = _DOC_ID_RE.search(url)
        doc_id = int(doc_id_m.group(1)) if doc_id_m else 0

        try:
            resp = curl_requests.get(url, impersonate="chrome124", timeout=30)
        except Exception:
            logger.warning(
                "[%s] request failed for %s", _SOURCE_KEY, url, exc_info=True
            )
            continue
        if resp.status_code != 200:
            logger.warning(
                "[%s] HTTP %s for %s -- skipping (link may be dead on EWURA's side)",
                _SOURCE_KEY,
                resp.status_code,
                url,
            )
            continue

        try:
            with pdfplumber.open(BytesIO(resp.content)) as pdf:
                full_text = "\n".join(p.extract_text() or "" for p in pdf.pages)
        except Exception:
            logger.warning("[%s] unreadable PDF at %s", _SOURCE_KEY, url, exc_info=True)
            continue

        eff_date = _parse_effective_date(full_text)
        if eff_date is None:
            logger.warning(
                "[%s] could not parse effective date from %s", _SOURCE_KEY, url
            )
            continue

        if eff_date in best_by_date and best_by_date[eff_date][0] >= doc_id:
            continue  # an equal-or-newer doc already covers this date

        if eff_date <= cutoff:
            best_by_date[eff_date] = (doc_id, url)
            continue  # idempotent skip, but still record so a stale dup doesn't reprocess

        town_rows = _parse_retail_table(full_text)
        if not town_rows:
            logger.warning("[%s] no Table 3 rows parsed from %s", _SOURCE_KEY, url)
            continue

        month_rows = []
        for town, petrol, diesel, kerosene in town_rows:
            for item_name, price in (
                ("Petrol", petrol),
                ("Diesel", diesel),
                ("Kerosene", kerosene),
            ):
                if price <= 0:
                    continue
                row = {
                    "observation_date": eff_date.isoformat(),
                    "period_kind": "effective_from",
                    "country": _COUNTRY,
                    "subnational_area": town,
                    "source_key": _SOURCE_KEY,
                    "coicop_code": _ITEM_COICOP[item_name],
                    "item_name": item_name,
                    "price_local": price,
                    "currency": _CURRENCY,
                    "unit": _UNIT,
                    "source_url": url,
                    "notes": "EWURA indicative CAP price, not an observed transaction price.",
                    "scrape_ts": scrape_ts,
                    "observation_hash": None,
                }
                row["observation_hash"] = make_hash(row, _IDENT)
                month_rows.append(row)

        best_by_date[eff_date] = (doc_id, url)
        rows_by_date[eff_date] = month_rows

    all_rows: list[dict] = []
    for eff_date, (doc_id, url) in best_by_date.items():
        all_rows.extend(rows_by_date.get(eff_date, []))

    if not all_rows:
        return None
    return pd.DataFrame(all_rows)
