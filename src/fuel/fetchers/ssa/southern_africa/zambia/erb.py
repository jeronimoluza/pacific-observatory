"""ERB Zambia — Energy Regulation Board monthly Petroleum Pump Prices.

ERB publishes a "Review of Petroleum Pump Prices" press release each month
and links a one-page PDF (``CurrentFuelPumpPrices<Month><Year>.pdf``) that
carries the canonical uniform countrywide prices in ZMW/litre for:

    PETROL | DIESEL | KEROSENE | JET A-1

We walk the ``/category/price-build-up`` index (3 pages cover Feb 2024
onwards), follow each article to find the PDF, download it, then extract
the new-price column from the on-page table. A sentence-form fallback
("the pump price of <product> is K<price>/litre") covers months where
the table cell layout drifts. The site's TLS chain is incomplete, so
this fetcher disables SSL verification.
"""

import io
import logging
import re
import time
import warnings
from datetime import date
from urllib.parse import urljoin

import pandas as pd
import requests
import urllib3

logger = logging.getLogger(__name__)

_BASE_URL = "https://www.erb.org.zm"
_INDEX_PATH = "/category/price-build-up"
_COUNTRY = "Zambia"
_CURRENCY = "ZMW"
_SOURCE_KEY = "erb_zm_monthly"

_THROTTLE_S = 1.0
_MAX_PAGES = 8

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
_SLUG_MONTH_RE = re.compile(
    r"\b(january|february|march|april|may|june|july|august|"
    r"september|october|november|december)[\s\-_]+(\d{4})",
    re.IGNORECASE,
)
_FILENAME_MONTH_RE = re.compile(
    r"CurrentFuelPumpPrices([A-Za-z]+)(\d{4})\.pdf",
    re.IGNORECASE,
)
_EFFECTIVE_RE = re.compile(
    r"effect\s+at\s+midnight\s+on\s+(\d{1,2})(?:st|nd|rd|th)?\s+(\w+)\s+(\d{4})",
    re.IGNORECASE,
)
_PDF_HREF_RE = re.compile(
    r'href="([^"]+CurrentFuelPumpPrices[^"]+\.pdf)"', re.IGNORECASE
)
_ARTICLE_HREF_RE = re.compile(
    r'href="(https://www\.erb\.org\.zm/[^"#?]+(?:pump-prices|price-build-ups?)[^"]*)"',
    re.IGNORECASE,
)

_PRODUCT_TOKEN = r"PETROL|DIESEL(?:[\s/(]*LSG[\s)]*)?|KEROSENE|JET[\s\-]*A[\s\-]*1"
# Three-column form: 'PETROL 27.15 27.15 - -' (CURRENT NEW). NEW = group(3).
_TABLE_ROW_RE = re.compile(
    rf"^({_PRODUCT_TOKEN})\s+([\d.]+)\s+([\d.]+)\b",
    re.MULTILINE | re.IGNORECASE,
)
# Single-column form: 'PETROL 29.92' (NEW PUMP PRICE only)
_TABLE_SINGLE_RE = re.compile(
    rf"^({_PRODUCT_TOKEN})\s+([\d.]+)\s*$",
    re.MULTILINE | re.IGNORECASE,
)
# Sentence fallback: '... petrol to K27.15/litre' / 'kerosene K35.05/litre'
_SENTENCE_RE = re.compile(
    r"(petrol|diesel(?:/lsg)?|kerosene|jet\s*a[\s\-]*1)[^K]{0,40}K\s*([\d.]+)\s*/\s*litre",
    re.IGNORECASE,
)

_PRODUCT_MAP = {
    "petrol": "Petrol",
    "diesel": "Diesel",
    "diesel/lsg": "Diesel",
    "kerosene": "Kerosene",
    "jet a-1": "Jet A-1",
    "jet a1": "Jet A-1",
    "jet a 1": "Jet A-1",
    "jeta-1": "Jet A-1",
    "jeta1": "Jet A-1",
}


def _normalize_product(raw: str) -> str | None:
    key = re.sub(r"\s+", " ", raw.strip().lower())
    # Collapse "diesel (lsg)" / "diesel/lsg" / "diesel lsg" to "diesel"
    key = re.sub(r"diesel.*lsg.*", "diesel", key)
    return _PRODUCT_MAP.get(key) or _PRODUCT_MAP.get(key.replace(" ", ""))


def _get(url: str, timeout: int = 30) -> requests.Response | None:
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
        logger.exception("[erb_zm] GET %s failed", url)
        return None


def _slug_to_date(slug_or_title: str) -> date | None:
    m = _SLUG_MONTH_RE.search(slug_or_title.replace("-", " ").replace("_", " "))
    if not m:
        return None
    month = _MONTHS.get(m.group(1).lower())
    if not month:
        return None
    try:
        return date(int(m.group(2)), month, 1)
    except ValueError:
        return None


def _filename_to_date(href: str) -> date | None:
    m = _FILENAME_MONTH_RE.search(href)
    if not m:
        return None
    month = _MONTHS.get(m.group(1).lower())
    if not month:
        return None
    try:
        return date(int(m.group(2)), month, 1)
    except ValueError:
        return None


def _body_effective_date(text: str) -> date | None:
    m = _EFFECTIVE_RE.search(text)
    if not m:
        return None
    month = _MONTHS.get(m.group(2).lower())
    if not month:
        return None
    try:
        return date(int(m.group(3)), month, int(m.group(1)))
    except ValueError:
        return None


def _parse_price(value: str | None) -> float | None:
    if value is None:
        return None
    cleaned = value.replace(",", "").strip()
    if not cleaned or cleaned in {"-", "—"}:
        return None
    try:
        v = float(cleaned)
    except ValueError:
        return None
    return v if v > 0 else None


def _discover_articles() -> list[tuple[str, date | None]]:
    """Walk listing pages and return [(article_url, slug_date), ...]."""
    out: dict[str, date | None] = {}
    for page in range(1, _MAX_PAGES + 1):
        url = (
            f"{_BASE_URL}{_INDEX_PATH}"
            if page == 1
            else f"{_BASE_URL}{_INDEX_PATH}/page/{page}"
        )
        if page > 1:
            time.sleep(_THROTTLE_S)
        resp = _get(url)
        if resp is None or resp.status_code != 200:
            break
        hrefs = sorted(set(_ARTICLE_HREF_RE.findall(resp.text)))
        if not hrefs:
            break
        page_new = 0
        for href in hrefs:
            if href in out:
                continue
            slug = href.rsplit("/", 1)[-1]
            out[href] = _slug_to_date(slug)
            page_new += 1
        logger.info("[erb_zm] index page=%d new=%d total=%d", page, page_new, len(out))
        if page_new == 0:
            break
    return sorted(out.items(), key=lambda kv: (kv[1] or date.min), reverse=True)


def _extract_prices(pdf_bytes: bytes) -> tuple[date | None, dict[str, float]]:
    """Return (effective_date_from_body, {product: new_price})."""
    try:
        import pdfplumber
    except ImportError:
        logger.error("[erb_zm] pdfplumber not installed")
        return None, {}

    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            text = "\n".join((p.extract_text() or "") for p in pdf.pages)
    except Exception:
        logger.exception("[erb_zm] PDF parse failed")
        return None, {}

    if not text.strip():
        return None, {}

    prices: dict[str, float] = {}

    # Three-column table form first — column 3 ("NEW") = current price.
    for match in _TABLE_ROW_RE.finditer(text):
        label = _normalize_product(match.group(1))
        if label is None:
            continue
        price = _parse_price(match.group(3))
        if price is None:
            continue
        prices.setdefault(label, price)

    # Single-column form ('PETROL 29.92') for layouts with no CURRENT column.
    if len(prices) < 3:
        for match in _TABLE_SINGLE_RE.finditer(text):
            label = _normalize_product(match.group(1))
            if label is None:
                continue
            price = _parse_price(match.group(2))
            if price is None:
                continue
            prices.setdefault(label, price)

    # Sentence form fallback for any products still missing
    if len(prices) < 3:
        for match in _SENTENCE_RE.finditer(text):
            label = _normalize_product(match.group(1))
            if label is None:
                continue
            price = _parse_price(match.group(2))
            if price is None:
                continue
            prices.setdefault(label, price)

    eff_date = _body_effective_date(text)
    return eff_date, prices


def fetch_erb_zm(cutoff: date) -> pd.DataFrame | None:
    articles = _discover_articles()
    if not articles:
        logger.info("[erb_zm] No articles discovered")
        return None
    logger.info("[erb_zm] %d articles discovered", len(articles))

    rows: list[dict] = []
    parsed_dates: set[date] = set()
    for art_url, slug_date in articles:
        # Skip clearly older articles based on slug month
        if slug_date and slug_date <= cutoff:
            continue
        # Prefer the canonical filename derived from the slug — ERB has
        # corrupted some older articles' inline PDF links.
        canonical_url = None
        if slug_date is not None:
            month_name = list(_MONTHS.keys())[slug_date.month - 1].capitalize()
            canonical_url = (
                f"{_BASE_URL}/wp-content/uploads/PressStatements/"
                f"CurrentFuelPumpPrices{month_name}{slug_date.year}.pdf"
            )
        time.sleep(_THROTTLE_S)
        art_resp = _get(art_url)
        article_pdf = None
        if art_resp is not None and art_resp.status_code == 200:
            pdf_hrefs = _PDF_HREF_RE.findall(art_resp.text)
            if pdf_hrefs:
                article_pdf = urljoin(_BASE_URL, pdf_hrefs[0])
        pdf_url = canonical_url or article_pdf
        if pdf_url is None:
            continue
        # Prefer the filename-derived date over slug-derived
        obs_date = _filename_to_date(pdf_url) or slug_date
        if obs_date and obs_date <= cutoff:
            continue
        time.sleep(_THROTTLE_S)
        pdf_resp = _get(pdf_url, timeout=60)
        # If canonical URL failed, fall back to the in-article link.
        if (
            (
                pdf_resp is None
                or pdf_resp.status_code != 200
                or pdf_resp.content[:4] != b"%PDF"
            )
            and article_pdf
            and article_pdf != pdf_url
        ):
            logger.info("[erb_zm] canonical missed, trying article-linked PDF")
            time.sleep(_THROTTLE_S)
            pdf_resp = _get(article_pdf, timeout=60)
            pdf_url = article_pdf
        if (
            pdf_resp is None
            or pdf_resp.status_code != 200
            or pdf_resp.content[:4] != b"%PDF"
        ):
            logger.warning("[erb_zm] %s not a PDF", pdf_url)
            continue
        body_date, prices = _extract_prices(pdf_resp.content)
        # Effective date from body wins if present
        if body_date:
            obs_date = body_date
        if obs_date is None or not prices:
            logger.warning(
                "[erb_zm] %s → no date or no prices (date=%s, n=%d)",
                pdf_url.rsplit("/", 1)[-1],
                obs_date,
                len(prices),
            )
            continue
        if obs_date <= cutoff:
            continue
        if obs_date in parsed_dates:
            continue
        parsed_dates.add(obs_date)
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
            "[erb_zm] %s → %d products (date %s)",
            pdf_url.rsplit("/", 1)[-1],
            len(prices),
            obs_date,
        )

    if not rows:
        logger.info("[erb_zm] No rows after cutoff %s", cutoff)
        return None

    df = (
        pd.DataFrame(rows)
        .drop_duplicates(subset=["observation_date", "fuel_product"])
        .sort_values(["observation_date", "fuel_product"])
        .reset_index(drop=True)
    )
    logger.info(
        "[erb_zm] %d rows (%s → %s, %d months × %d products)",
        len(df),
        df["observation_date"].iloc[0],
        df["observation_date"].iloc[-1],
        df["observation_date"].nunique(),
        df["fuel_product"].nunique(),
    )
    return df


__all__ = ["fetch_erb_zm"]
