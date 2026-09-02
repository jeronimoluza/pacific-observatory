"""Energy Regulation Board (ERB) uniform pump fuel prices, Zambia.

The ERB (erb.org.zm) publishes a monthly "<Month> <Year> Petroleum Pump
Prices, Press Statement and Price Build-ups" post carrying several PDFs.
Two are image-only scans (the press-statement PDF and the "Current..."
alias — both 0 chars of extractable text, confirmed via pdfplumber and a
manual OCR pass); one is a clean, text-native "<MONTH>-<YEAR>-PUMP-PRICE-
BUILD-UP.pdf" with a "UNIFORM PUMP PRICE BUILD-UP" cost breakdown ending
in a "Uniform Pump Price" row (ZMW per cubic metre) for Petrol, Diesel,
Kerosene. This fetcher uses that text-native file and skips the scanned
ones entirely (no pytesseract/OCR dependency needed or present in this
environment — an existing corpus fetcher, doc_bfi.py, explicitly notes
OCR is "not wired" anywhere in prices/fetchers).

Cross-checked live 2026-09-01 against the September 2026 press release
(OCR'd manually for verification only, not used at runtime): "the price of
Petrol has been maintained at K25.29/litre, Diesel at K26.86/litre,
Kerosene at K27.02/litre" — matches the build-up PDF's Uniform Pump Price
row (25,288.82 / 26,857.70 / 27,015.21 ZMW/M3, i.e. /1000 = 25.29 / 26.86
/ 27.02 ZMW/L) exactly, and also matches ZamStats' independently-published
Table 7 average prices for the same period (Diesel 26.86, Petrol 25.28) —
two independent government sources agreeing to 2 decimal places.

Prices are NATIONALLY UNIFORM (Zambia regulates one pump price per product
countrywide, not per station) — `subnational_area` is left null by design,
not an omission.

DISCOVERY: WP REST API search (`/wp-json/wp/v2/posts?search=Petroleum Pump
Prices`, sorted date desc) — confirmed stable and correctly ordered across
10 months back to December 2025. The build-up PDF link is picked out of
the post content by matching "PUMP-PRICE-BUILD-UP" while excluding
"WHOLESALE" (the post also links wholesale/Jet-A-1 build-ups with
overlapping filename fragments).

EFFECTIVE DATE: the build-up PDF states only "<MONTH> <YEAR> PRICE
ADJUSTMENT", not a specific day. This fetcher uses the 1st of that month
as `effective_from` — ERB's monthly review cycle takes effect at the start
of the named month (the September review was issued 31 Aug 2026 "for
September 2026"). The exact announcement day is on the (image-only) press
statement and is not recovered here; flagged so a future OCR pass could
tighten this if the day-level distinction ever matters downstream.

analytical_role: tariff -> PriceObservation, period_kind: effective_from
(rule 17's PriceObservation vocabulary, not IndexObservation's *_avg
forms). coicop_classification: source_curated, narrow
(coicop_codes: ["07.2.2"], motor fuels).
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

_COUNTRY = "Zambia"
_SOURCE_KEY = "erb_fuel"
_CURRENCY = "ZMW"
_COICOP = "07.2.2"
_POSTS_API = "https://www.erb.org.zm/wp-json/wp/v2/posts"
_IDENT = ["source_key", "observation_date", "item_name"]

_PDF_LINK_RE = re.compile(r'href="([^"]+\.pdf)"', re.IGNORECASE)
_UNIFORM_ROW_RE = re.compile(
    r"Uniform Pump Price\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})"
)

_MONTHS = {
    m: i + 1
    for i, m in enumerate(
        [
            "january",
            "february",
            "march",
            "april",
            "may",
            "june",
            "july",
            "august",
            "september",
            "october",
            "november",
            "december",
        ]
    )
}


def _find_latest_buildup_pdf(session) -> tuple[str, str] | None:
    try:
        resp = session.get(
            _POSTS_API,
            params={
                "search": "Petroleum Pump Prices",
                "orderby": "date",
                "order": "desc",
                "per_page": 10,
            },
            timeout=30,
        )
        resp.raise_for_status()
        posts = resp.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] wp-json posts lookup failed: %s", _SOURCE_KEY, exc)
        return None

    for post in posts:
        slug = post.get("slug", "")
        content = post.get("content", {}).get("rendered", "")
        links = _PDF_LINK_RE.findall(content)
        buildup = next(
            (
                link
                for link in links
                if "PUMP-PRICE-BUILD-UP" in link.upper()
                and "WHOLESALE" not in link.upper()
            ),
            None,
        )
        if buildup:
            return buildup, slug
    return None


def _slug_to_effective_date(slug: str) -> str | None:
    parts = slug.split("-")
    for i in range(len(parts) - 1):
        mon = parts[i].lower()
        if mon in _MONTHS and parts[i + 1].isdigit() and len(parts[i + 1]) == 4:
            return date(int(parts[i + 1]), _MONTHS[mon], 1).isoformat()
    return None


def _extract_uniform_prices(pdf_bytes: bytes) -> dict[str, float] | None:
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        text = pdf.pages[0].extract_text() or ""
    m = _UNIFORM_ROW_RE.search(text)
    if not m:
        return None
    petrol_m3, diesel_m3, kerosene_m3 = (float(v.replace(",", "")) for v in m.groups())
    return {
        "Petrol": round(petrol_m3 / 1000, 4),
        "Diesel": round(diesel_m3 / 1000, 4),
        "Kerosene": round(kerosene_m3 / 1000, 4),
    }


def fetch_erb_fuel(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    found = _find_latest_buildup_pdf(session)
    if not found:
        logger.warning(
            "[%s] could not resolve latest pump-price build-up post", _SOURCE_KEY
        )
        return None
    pdf_url, slug = found

    eff_date = _slug_to_effective_date(slug)
    if not eff_date:
        logger.warning(
            "[%s] could not parse effective month from slug %r", _SOURCE_KEY, slug
        )
        return None
    if date.fromisoformat(eff_date) <= cutoff:
        logger.info(
            "[%s] latest build-up (%s) is at/before cutoff=%s",
            _SOURCE_KEY,
            eff_date,
            cutoff,
        )
        return None

    try:
        resp = session.get(pdf_url, timeout=60)
        resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] pdf fetch failed: %s", _SOURCE_KEY, exc)
        return None

    prices = _extract_uniform_prices(resp.content)
    if not prices:
        logger.warning(
            "[%s] could not parse Uniform Pump Price row from %s", _SOURCE_KEY, pdf_url
        )
        return None

    ts = get_scrape_ts()
    rows = []
    for item_name, price_per_litre in prices.items():
        if price_per_litre <= 0:
            continue
        row = {
            "observation_date": eff_date,
            "period_kind": "effective_from",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "coicop_code": _COICOP,
            "item_name": item_name,
            "price_local": price_per_litre,
            "currency": _CURRENCY,
            "unit": "litre",
            "source_url": pdf_url,
            "notes": (
                "ERB national uniform pump price (ZMW/litre), derived from the "
                "'Uniform Pump Price' row (ZMW/M3 / 1000) in the monthly PUMP-"
                "PRICE-BUILD-UP PDF; effective_from set to the 1st of the "
                "announced review month (exact announcement day is on an "
                "image-only press-statement PDF not parsed here)."
            ),
            "scrape_ts": ts,
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)

    logger.info(
        "[%s] %d rows for %s (cutoff=%s)", _SOURCE_KEY, len(rows), eff_date, cutoff
    )
    return pd.DataFrame(rows) if rows else None
