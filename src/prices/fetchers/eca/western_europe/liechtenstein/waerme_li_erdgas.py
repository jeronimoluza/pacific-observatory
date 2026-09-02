"""Liechtenstein Waerme (formerly branded LGV / Liechtensteinische
Gasversorgung) -- domestic household natural-gas tariff catalogue.

Liechtenstein Waerme is Liechtenstein's domestic gas/district-heating
utility. lgv.li now canonicalises to waerme.li (same TYPO3 site, rebranded
"LIECHTENSTEIN WAERME"). Verified live 2026-09-01: the /downloads page
(https://www.waerme.li/downloads) links a set of dated PDF price sheets
under /fileadmin/user_upload/ -- this fetcher discovers them from that page
rather than hardcoding filenames, so it keeps picking up new periods as
Liechtenstein Waerme publishes them.

Two tariff PRODUCTS are captured (both real, both published, genuinely
different contracts a household chooses between -- not duplicates of one
series):

* **Festpreis** ("Erdgas-Festpreis Jahr") -- one composite CHF/kWh price
  per calendar year, built from an EEX gas-futures price plus a
  structuring/currency factor, a service fee, and levies. pdfplumber's
  `extract_text()` recovers a single labelled line:
  "Erdgas-Festpreis in CHF/kWh: 0.049572" (2026); 0.066537 for 2025.
* **Floatpreis** ("Erdgas-Floatpreis") -- a rolling 3-month table (current
  + 2 preceding months) republished roughly bimonthly, each PDF carrying up
  to 3 dated monthly CHF/kWh prices alongside historical min/max reference
  values (NOT dated observations -- excluded). The trailing month in a
  given PDF is sometimes still blank (not yet closed) -- the parser counts
  real price values and pairs them with the FIRST that-many month labels
  from the header row, since blanks are always the trailing/most-recent
  column, not an interior gap.

Both are `analytical_role: tariff`, COICOP 04.5.2 -- ENERGY-COMPONENT
prices only: network usage fee ("Netzbenutzung"), CO2 levy, and 8.10% VAT
are explicitly excluded on the source PDFs, so this is not a fully-loaded
delivered price. The Basispreis/Biogas sheet on the same downloads page
(mixed excl./incl.-CO2 rows across 4 product columns) was probed but not
parsed -- its 2-row-per-column layout does not extract reliably as text and
would need bespoke per-cell coordinates; Festpreis + Floatpreis alone
already clear the 5-row shipping gate with genuine historical periods.

Complementary to (not a duplicate of) `eurostat_gas` (Eurostat dataset
nrg_pc_202, cross-country household gas STATISTIC, band D2, half-yearly) --
this is the utility's own published rate schedule at monthly/annual grain.

period_kind: effective_from for both products (Festpreis: Jan 1 of the
stated year; Floatpreis: the 1st of the stated month).
"""

from __future__ import annotations

import logging
import re
from datetime import date
from io import BytesIO

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_COUNTRY = "Liechtenstein"
_SOURCE_KEY = "waerme_li_erdgas"
_DOWNLOADS_PAGE = "https://www.waerme.li/downloads"
_COICOP_CODE = "04.5.2"
_IDENT = ["source_key", "observation_date", "item_name"]
_FALLBACK_DATE = date(2015, 1, 1)

_FESTPREIS_RE = re.compile(
    r"/fileadmin/user_upload/(\d{4}_Festpreis_Erdgas[^\"'\s]*\.pdf)"
)
_FLOATPREIS_RE = re.compile(
    r"/fileadmin/user_upload/(\d{4}_Floatpreis_Erdgas[^\"'\s]*\.pdf)"
)
_FESTPREIS_YEAR_RE = re.compile(r"Erdgas-Festpreis in CHF/kWh:\s*([0-9]+(?:\.[0-9]+)?)")
_FESTPREIS_JAHR_RE = re.compile(r"Erdgas-Festpreis Jahr\s*\n?\s*(\d{4})")

_MONTHS_DE = {
    "januar": 1,
    "februar": 2,
    "märz": 3,
    "maerz": 3,
    "april": 4,
    "mai": 5,
    "juni": 6,
    "juli": 7,
    "august": 8,
    "september": 9,
    "oktober": 10,
    "november": 11,
    "dezember": 12,
}
_MONTH_YEAR_RE = re.compile(
    r"(" + "|".join(_MONTHS_DE.keys()) + r")\s+(\d{4})", re.IGNORECASE
)
_NUMBER_RE = re.compile(r"\d+\.\d+")


def _discover_pdfs(session) -> tuple[list[str], list[str]]:
    resp = session.get(_DOWNLOADS_PAGE, timeout=30)
    resp.raise_for_status()
    fest = sorted(set(_FESTPREIS_RE.findall(resp.text)))
    float_ = sorted(set(_FLOATPREIS_RE.findall(resp.text)))
    base = "https://www.waerme.li/fileadmin/user_upload/"
    return [base + f for f in fest], [base + f for f in float_]


def _pdf_text(session, url: str) -> str | None:
    import pdfplumber

    try:
        resp = session.get(url, timeout=60)
        resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] PDF fetch failed for %s: %s", _SOURCE_KEY, url, exc)
        return None
    try:
        with pdfplumber.open(BytesIO(resp.content)) as pdf:
            return "\n".join((p.extract_text() or "") for p in pdf.pages)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] PDF parse failed for %s: %s", _SOURCE_KEY, url, exc)
        return None


def _parse_festpreis(text: str, url: str) -> list[dict]:
    price_m = _FESTPREIS_YEAR_RE.search(text)
    year_m = _FESTPREIS_JAHR_RE.search(text)
    if not price_m or not year_m:
        logger.warning("[%s] Festpreis fields not found in %s", _SOURCE_KEY, url)
        return []
    price = float(price_m.group(1))
    year = int(year_m.group(1))
    if price <= 0:
        return []
    obs_date = date(year, 1, 1)
    return [
        {
            "observation_date": obs_date,
            "item_name": f"Erdgas Festpreis {year}",
            "price_local": price,
            "source_url": url,
            "notes": (
                "Liechtenstein Waerme fixed-price ('Festpreis') gas tariff, "
                f"calendar year {year} -- energy component only, excludes "
                "network fee/CO2 levy/VAT."
            ),
        }
    ]


def _parse_floatpreis(text: str, url: str) -> list[dict]:
    lines = text.splitlines()
    header_idx = None
    for i, line in enumerate(lines):
        if "Erdgas-Floatpreis" in line and "Monat" in line:
            header_idx = i
            break
    if header_idx is None:
        logger.warning("[%s] Floatpreis header not found in %s", _SOURCE_KEY, url)
        return []
    n_months_declared = lines[header_idx].count("Monat")

    # The month/year labels sit on the next non-empty line.
    dates_line = None
    for line in lines[header_idx + 1 : header_idx + 4]:
        if line.strip():
            dates_line = line
            break
    if dates_line is None:
        return []
    month_matches = _MONTH_YEAR_RE.findall(dates_line)[:n_months_declared]

    price_line = None
    for line in lines:
        if line.strip().startswith("Erdgas-Floatpreis in CHF/kWh"):
            price_line = line
            break
    if price_line is None:
        logger.warning("[%s] Floatpreis price line not found in %s", _SOURCE_KEY, url)
        return []
    values = [float(v) for v in _NUMBER_RE.findall(price_line)]
    # Last two numeric values on this line are the historical Minimalwert /
    # Maximalwert reference prices, not dated observations for this PDF.
    n_real = len(values) - 2
    if n_real <= 0:
        return []
    real_prices = values[:n_real]
    real_months = month_matches[:n_real]
    if len(real_months) != len(real_prices):
        logger.warning(
            "[%s] Floatpreis month/price count mismatch in %s (%d months, %d prices)",
            _SOURCE_KEY,
            url,
            len(real_months),
            len(real_prices),
        )
        n = min(len(real_months), len(real_prices))
        real_months, real_prices = real_months[:n], real_prices[:n]

    out = []
    for (month_name, year_str), price in zip(real_months, real_prices):
        if price <= 0:
            continue
        month_num = _MONTHS_DE[month_name.lower()]
        obs_date = date(int(year_str), month_num, 1)
        out.append(
            {
                "observation_date": obs_date,
                "item_name": f"Erdgas Floatpreis {obs_date.strftime('%B %Y')}",
                "price_local": price,
                "source_url": url,
                "notes": (
                    "Liechtenstein Waerme floating-price ('Floatpreis') gas "
                    "tariff, monthly EEX-indexed -- energy component only, "
                    "excludes network fee/CO2 levy/VAT."
                ),
            }
        )
    return out


def fetch_waerme_li_erdgas(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    try:
        fest_urls, float_urls = _discover_pdfs(session)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] downloads page fetch failed: %s", _SOURCE_KEY, exc)
        return None

    if not fest_urls and not float_urls:
        logger.warning("[%s] no Festpreis/Floatpreis PDFs discovered", _SOURCE_KEY)
        return None

    parsed: list[dict] = []
    for url in fest_urls:
        text = _pdf_text(session, url)
        if text:
            parsed.extend(_parse_festpreis(text, url))
    for url in float_urls:
        text = _pdf_text(session, url)
        if text:
            parsed.extend(_parse_floatpreis(text, url))

    if not parsed:
        logger.warning("[%s] no tariff rows parsed", _SOURCE_KEY)
        return None

    ts = get_scrape_ts()
    rows: list[dict] = []
    for p in parsed:
        if p["observation_date"] <= cutoff:
            continue
        row = {
            "observation_date": p["observation_date"].isoformat(),
            "period_kind": "effective_from",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "coicop_code": _COICOP_CODE,
            "item_name": p["item_name"],
            "price_local": p["price_local"],
            "currency": "CHF",
            "unit": "kWh",
            "source_url": p["source_url"],
            "notes": p["notes"],
            "scrape_ts": ts,
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)

    if not rows:
        logger.info("[%s] no new rows past cutoff=%s", _SOURCE_KEY, cutoff)
        return None

    logger.info("[%s] %d rows (cutoff=%s)", _SOURCE_KEY, len(rows), cutoff)
    return pd.DataFrame(rows)
