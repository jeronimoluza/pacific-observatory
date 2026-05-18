"""MERA Malawi energy price-review decisions.

The Malawi Energy Regulatory Authority publishes first-party Board price-review
posts under the ``energy-price-reviews`` category. The fetcher discovers review
URLs from category pages and the WordPress API, then extracts effective dates
and approved retail prices from HTML tables or inline text.
"""

from __future__ import annotations

import logging
import re
import time
from datetime import date
from urllib.parse import urljoin

import pandas as pd
import requests
from bs4 import BeautifulSoup

from core.http import DEFAULT_HEADERS

logger = logging.getLogger(__name__)

_BASE_URL = "https://mera.mw"
_CATEGORY_URL = f"{_BASE_URL}/category/energy-price-reviews/"
_COUNTRY = "Malawi"
_CURRENCY = "MWK"
_SOURCE_KEY = "mera_mw_monthly"
_THROTTLE_S = 0.6
_MAX_CATEGORY_PAGES = 12
_MAX_API_PAGES = 12

_PRODUCT_PATTERNS = {
    "Petrol": re.compile(r"\bpetrol\b", re.I),
    "Diesel": re.compile(r"\bdiesel\b", re.I),
    "Paraffin": re.compile(r"\b(?:paraffin|kerosene)\b", re.I),
    "LPG": re.compile(r"\b(?:lpg|liquefied\s+petroleum\s+gas)\b", re.I),
    "Jet A-1": re.compile(r"\bjet\s*[- ]?\s*a\s*[- ]?\s*1\b", re.I),
}
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
_POST_RE = re.compile(
    r"https?://mera\.mw/(20\d{2})/(\d{2})/(\d{2})/review-of-[^\"'#?]+/?", re.I
)
_URL_DATE_RE = re.compile(r"/(20\d{2})/(\d{2})/(\d{2})/")
_EFFECTIVE_RE = re.compile(
    r"\beffect(?:ive|ed)\s+(?:from|on)?\s*"
    r"(\d{1,2})(?:st|nd|rd|th|\^\{(?:st|nd|rd|th)\})?\s+"
    r"([A-Za-z]+),?\s+(20\d{2})",
    re.I,
)
_CURRENCY_PRICE_RE = re.compile(
    r"(?:MWK|MK|K)\s*([\d,]+(?:\.\d+)?)|([\d,]+(?:\.\d+)?)\s*(?:MWK|MK)\b",
    re.I,
)


def _parse_number(raw: str | None) -> float | None:
    if raw is None:
        return None
    value = raw.replace(",", "").strip()
    try:
        out = float(value)
    except ValueError:
        return None
    return out if out > 0 else None


def _url_date(url: str) -> date | None:
    match = _URL_DATE_RE.search(url)
    if not match:
        return None
    try:
        return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    except ValueError:
        return None


def _effective_date(text: str, url: str) -> date:
    match = _EFFECTIVE_RE.search(text)
    if match:
        month = _MONTHS.get(match.group(2).lower())
        if month:
            try:
                return date(int(match.group(3)), month, int(match.group(1)))
            except ValueError:
                pass
    return _url_date(url) or date.today()


def _get(
    session: requests.Session, url: str, timeout: int = 45
) -> requests.Response | None:
    try:
        return session.get(url, timeout=timeout)
    except Exception as exc:
        logger.warning("[mera_mw] request failed: %s (%s)", url, exc)
        return None


def _post_urls_from_html(html: str, page_url: str) -> set[str]:
    urls: set[str] = set()
    soup = BeautifulSoup(html, "lxml")
    for anchor in soup.find_all("a", href=True):
        href = urljoin(page_url, anchor["href"]).split("#", 1)[0]
        match = _POST_RE.match(href)
        if match:
            urls.add(href.rstrip("/") + "/")
    return urls


def _discover_category_posts(session: requests.Session) -> set[str]:
    urls: set[str] = set()
    for page in range(1, _MAX_CATEGORY_PAGES + 1):
        candidates = (
            [_CATEGORY_URL]
            if page == 1
            else [
                urljoin(_CATEGORY_URL, f"page/{page}/"),
                f"{_CATEGORY_URL}?paged={page}",
                f"{_CATEGORY_URL}?page={page}",
            ]
        )
        before = len(urls)
        for url in candidates:
            resp = _get(session, url)
            if resp is None or resp.status_code != 200:
                continue
            urls.update(_post_urls_from_html(resp.text, url))
        if page > 1 and len(urls) == before:
            break
        time.sleep(_THROTTLE_S)
    return urls


def _discover_api_posts(session: requests.Session) -> set[str]:
    urls: set[str] = set()
    category_id: int | None = None
    resp = _get(
        session, f"{_BASE_URL}/wp-json/wp/v2/categories?slug=energy-price-reviews"
    )
    if resp is not None and resp.status_code == 200:
        try:
            items = resp.json()
        except Exception:
            items = []
        if items:
            category_id = int(items[0]["id"])
    if category_id is None:
        return urls
    for page in range(1, _MAX_API_PAGES + 1):
        api_url = (
            f"{_BASE_URL}/wp-json/wp/v2/posts?per_page=100&page={page}"
            f"&categories={category_id}&_fields=link,slug"
        )
        resp = _get(session, api_url)
        if resp is None or resp.status_code != 200:
            break
        try:
            posts = resp.json()
        except Exception:
            break
        if not posts:
            break
        for post in posts:
            link = str(post.get("link", ""))
            if _POST_RE.match(link):
                urls.add(link.rstrip("/") + "/")
        time.sleep(_THROTTLE_S)
    return urls


def _discover_posts(session: requests.Session) -> list[str]:
    urls = _discover_category_posts(session)
    urls.update(_discover_api_posts(session))
    return sorted(urls, key=lambda url: _url_date(url) or date.min)


def _product_for_text(text: str) -> str | None:
    for product, pattern in _PRODUCT_PATTERNS.items():
        if pattern.search(text):
            return product
    return None


def _nearest_product_after(text: str, start: int, limit: int = 70) -> str | None:
    best: tuple[int, str] | None = None
    window = text[start : start + limit]
    for product, pattern in _PRODUCT_PATTERNS.items():
        match = pattern.search(window)
        if match and (best is None or match.start() < best[0]):
            best = (match.start(), product)
    return best[1] if best else None


def _nearest_product_before(text: str, end: int, limit: int = 70) -> str | None:
    best: tuple[int, str] | None = None
    window = text[max(0, end - limit) : end]
    for product, pattern in _PRODUCT_PATTERNS.items():
        matches = list(pattern.finditer(window))
        if matches and (best is None or matches[-1].start() > best[0]):
            best = (matches[-1].start(), product)
    return best[1] if best else None


def _numbers_from_cells(cells: list[str], headers: list[str]) -> list[float]:
    values: list[float] = []
    for idx, cell in enumerate(cells):
        header = headers[idx].lower() if idx < len(headers) else ""
        combined = f"{header} {cell}".lower()
        if "%" in combined or "change" in combined or "percent" in combined:
            continue
        for match in re.finditer(r"\d[\d,]*(?:\.\d+)?", cell):
            value = _parse_number(match.group(0))
            if value is not None and value >= 50:
                values.append(value)
    return values


def _extract_table_prices(soup: BeautifulSoup) -> dict[str, float]:
    out: dict[str, float] = {}
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if not rows:
            continue
        table_text = table.get_text(" ", strip=True).lower()
        if not any(
            token in table_text for token in ("pump", "retail", "price", "mwk", "mk/")
        ):
            continue
        headers = [
            cell.get_text(" ", strip=True) for cell in rows[0].find_all(["th", "td"])
        ]
        for row in rows[1:]:
            cells = [
                cell.get_text(" ", strip=True) for cell in row.find_all(["th", "td"])
            ]
            if not cells:
                continue
            product = _product_for_text(" ".join(cells[:2]))
            if product is None:
                continue
            values = _numbers_from_cells(cells[1:], headers[1:])
            if values:
                out[product] = values[-1]
    return out


def _extract_inline_prices(text: str) -> dict[str, float]:
    out: dict[str, float] = {}
    pieces = re.split(r"[\n;]+", text)
    for piece in pieces:
        if not any(pattern.search(piece) for pattern in _PRODUCT_PATTERNS.values()):
            continue
        mentions: list[tuple[int, str, float]] = []
        for price_match in _CURRENCY_PRICE_RE.finditer(piece):
            raw = price_match.group(1) or price_match.group(2)
            price = _parse_number(raw)
            if price is None or price < 50:
                continue
            product = _nearest_product_after(piece, price_match.end())
            if product is None:
                product = _nearest_product_before(piece, price_match.start())
            if product:
                mentions.append((price_match.start(), product, price))
        for _, product, price in sorted(mentions):
            out[product] = price
    return out


def _unit_for_product(product: str) -> str:
    return "kg" if product == "LPG" else "L"


def _extract_post_rows(html: str, url: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text("\n", strip=True)
    obs_date = _effective_date(text, url)
    prices = _extract_table_prices(soup)
    prices.update(_extract_inline_prices(text))
    rows: list[dict] = []
    for product, price in prices.items():
        rows.append(
            {
                "observation_date": obs_date.isoformat(),
                "country": _COUNTRY,
                "fuel_product": product,
                "price_local": price,
                "currency": _CURRENCY,
                "source_key": _SOURCE_KEY,
                "unit": _unit_for_product(product),
            }
        )
    return rows


def fetch_mera_mw(cutoff: date) -> pd.DataFrame | None:
    session = requests.Session()
    session.headers.update(DEFAULT_HEADERS)
    rows: list[dict] = []
    for url in _discover_posts(session):
        post_date = _url_date(url)
        if post_date is not None and post_date <= cutoff:
            continue
        time.sleep(_THROTTLE_S)
        resp = _get(session, url)
        if resp is None or resp.status_code != 200:
            logger.info("[mera_mw] post unavailable: %s", url)
            continue
        parsed = _extract_post_rows(resp.text, url)
        if not parsed:
            logger.info("[mera_mw] no prices parsed from %s", url)
            continue
        rows.extend(parsed)
        logger.info("[mera_mw] %s -> %d rows", url, len(parsed))
    if not rows:
        logger.info("[mera_mw] no rows after cutoff %s", cutoff)
        return None
    df = (
        pd.DataFrame(rows)
        .drop_duplicates(subset=["observation_date", "fuel_product"], keep="last")
        .sort_values(["observation_date", "fuel_product"])
        .reset_index(drop=True)
    )
    logger.info(
        "[mera_mw] %d rows (%s -> %s)",
        len(df),
        df["observation_date"].iloc[0],
        df["observation_date"].iloc[-1],
    )
    return df


__all__ = ["fetch_mera_mw"]
