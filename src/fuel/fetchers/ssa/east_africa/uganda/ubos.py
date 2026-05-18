"""UBOS Uganda — monthly Consumer Price Index PDF retail-prices table.

UBOS publishes a monthly CPI PDF at
``https://www.ubos.org/wp-content/uploads/publications/CPI-PUBLICATION-<MONTH>-<YEAR>.pdf``
that includes the table "National Average Retail Prices of Selected
Commodities". Each row carries three monthly figures:
    Petrol 1 Litre <current> <prev_month> <same_month_prev_year>
    Diesel 1 Litre <current> <prev_month> <same_month_prev_year>

We probe a small list of URL filename variants (the canonical form, the
older ``CPI-PUBLICATION-FOR-...`` variant, and a pre-2022 ``Press_Release``
form) for each month between the cutoff and today. PDF text is extracted
with pdfplumber and parsed by regex. The site's TLS chain is incomplete,
so SSL verification is disabled.
"""

import io
import logging
import re
import time
import warnings
from datetime import date

import pandas as pd
import requests
import urllib3

logger = logging.getLogger(__name__)

_BASE_URL = "https://www.ubos.org"
_COUNTRY = "Uganda"
_CURRENCY = "UGX"
_SOURCE_KEY = "ubos_ug_monthly"

_THROTTLE_S = 1.0

_MONTHS = [
    "JANUARY",
    "FEBRUARY",
    "MARCH",
    "APRIL",
    "MAY",
    "JUNE",
    "JULY",
    "AUGUST",
    "SEPTEMBER",
    "OCTOBER",
    "NOVEMBER",
    "DECEMBER",
]

# Each row: 'Petrol 1 Litre 5,074 5,064 5,048' (current, prev_month, year_ago)
_ROW_RE = re.compile(
    r"^\s*(Petrol|Diesel)\s+1\s+Litre\s+" r"([0-9,]+)\s+([0-9,]+)\s+([0-9,]+)\s*$",
    re.MULTILINE | re.IGNORECASE,
)


def _candidate_urls(year: int, month_idx: int) -> list[str]:
    month_upper = _MONTHS[month_idx - 1]
    month_title = month_upper.title()
    base = f"{_BASE_URL}/wp-content/uploads/publications"
    return [
        f"{base}/CPI-PUBLICATION-{month_upper}-{year}.pdf",
        f"{base}/CPI-PUBLICATION-{month_title}-{year}.pdf",
        f"{base}/CPI-PUBLICATION-FOR-{month_upper}-{year}.pdf",
        f"{base}/CPI-PUBLICATION-FOR-{month_title}-{year}.pdf",
        f"{base}/CPI-Publication-{month_title}-{year}.pdf",
    ]


def _get(url: str, timeout: int = 60) -> requests.Response | None:
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", urllib3.exceptions.InsecureRequestWarning)
            return requests.get(
                url,
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=timeout,
                verify=False,
            )
    except Exception:
        return None


def _parse_price(text: str) -> float | None:
    cleaned = text.replace(",", "").strip()
    if not cleaned:
        return None
    try:
        v = float(cleaned)
    except ValueError:
        return None
    return v if v > 0 else None


def _extract_prices(pdf_bytes: bytes) -> dict[str, float]:
    try:
        import pdfplumber
    except ImportError:
        logger.error("[ubos_ug] pdfplumber not installed")
        return {}

    out: dict[str, float] = {}
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                if "1 Litre" not in text:
                    continue
                for match in _ROW_RE.finditer(text):
                    label = match.group(1).capitalize()
                    # Column 2 = current month
                    price = _parse_price(match.group(2))
                    if price is None:
                        continue
                    out.setdefault(label, price)
                if out:
                    return out
    except Exception:
        logger.exception("[ubos_ug] PDF parse failed")
    return out


def _iter_months(start: date, end: date):
    """Yield (year, month_index) tuples from start to end, inclusive."""
    y, m = start.year, start.month
    while date(y, m, 1) <= end:
        yield y, m
        m += 1
        if m > 12:
            m = 1
            y += 1


def fetch_ubos_ug(cutoff: date) -> pd.DataFrame | None:
    today = date.today()
    rows: list[dict] = []
    # Walk forward from the month immediately after cutoff to today
    start_year = cutoff.year + (1 if cutoff.month == 12 else 0)
    start_month = 1 if cutoff.month == 12 else cutoff.month + 1
    start = date(start_year, start_month, 1)

    for year, month_idx in _iter_months(start, today):
        for url in _candidate_urls(year, month_idx):
            time.sleep(_THROTTLE_S)
            resp = _get(url)
            if resp is None or resp.status_code != 200:
                continue
            if resp.content[:4] != b"%PDF":
                continue
            prices = _extract_prices(resp.content)
            if not prices:
                logger.info(
                    "[ubos_ug] %s → PDF found but no row matched",
                    url.rsplit("/", 1)[-1],
                )
                break  # PDF resolved; don't try sibling variants
            obs_date = date(year, month_idx, 1)
            iso = obs_date.strftime("%Y-%m-%d")
            for label, price in prices.items():
                rows.append(
                    {
                        "observation_date": iso,
                        "country": _COUNTRY,
                        "fuel_product": label,
                        "price_local": price,
                        "currency": _CURRENCY,
                        "unit": "L",
                        "source_key": _SOURCE_KEY,
                    }
                )
            logger.info(
                "[ubos_ug] %s → %d products (date %s)",
                url.rsplit("/", 1)[-1],
                len(prices),
                obs_date,
            )
            break  # success — skip remaining filename variants
        else:
            logger.info("[ubos_ug] no PDF found for %d-%02d", year, month_idx)

    if not rows:
        logger.info("[ubos_ug] No rows after cutoff %s", cutoff)
        return None

    df = (
        pd.DataFrame(rows)
        .drop_duplicates(subset=["observation_date", "fuel_product"])
        .sort_values(["observation_date", "fuel_product"])
        .reset_index(drop=True)
    )
    logger.info(
        "[ubos_ug] %d rows (%s → %s, %d months × %d products)",
        len(df),
        df["observation_date"].iloc[0],
        df["observation_date"].iloc[-1],
        df["observation_date"].nunique(),
        df["fuel_product"].nunique(),
    )
    return df


__all__ = ["fetch_ubos_ug"]
