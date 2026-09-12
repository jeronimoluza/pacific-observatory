"""Flying Fox Brewing Co. (Pago Pago, American Samoa) drink and food menu."""

from __future__ import annotations

import logging
import re
from datetime import date

import pandas as pd
from bs4 import BeautifulSoup

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_URL = "https://flyingfoxbeer.wixsite.com/home/menu"
_COUNTRY = "American Samoa"
_CURRENCY = "USD"
_SOURCE_KEY = "as_flyingfox_menu"
_IDENT = ["source_key", "observation_date", "item_name", "unit"]

# Beers and ciders served on premises and prepared food are both COICOP 11.1.1
# (food and beverage serving services); the split is by serve type, not by
# whether the drink is alcoholic.
_COICOP = "11.1.1.1"

_PRICE_RE = re.compile(r"^\$(?P<price>\d[\d,]*(?:\.\d{2})?)$")
_SIZE_RE = re.compile(r"^(?P<size>\d+(?:\.\d+)?)\s*oz\.?$", re.I)
# Each menu section opens with a pull-quote and its attribution; both sit
# exactly where an item name would and must not be read as one.
_EPIGRAPH_RE = re.compile(r'^["\u201c\u2018\u2019\u201d]|^-{1,2}\s*\S')

_NOISE = {
    "top of page",
    "bottom of page",
    "Show More",
    "My New Option",
    "Use tab to navigate through the menu items.",
    "This website was built on Wix. Create yours today.",
    "Get Started",
    "Home",
    "ABOUT US",
    "PIA O AMERIKA SAMOA",
    "FOOD & BEER",
    "SOCIAL FOX",
    "BLOG",
    "GALLERY",
    "FF CALENDAR",
    "FOR VISITORS",
    "FLYING FOX MERCH",
    "More",
    "Gallery",
    "ADDRESS",
    "FIND​ US",
    "FIND US",
}

_SECTIONS = {
    "FLYING FOX CRAFT BEERS -- Locally brewed, cold draft beer!": "draft beer/cider",
    "Flying Fox Food!": "food",
}


def _clean(value: str) -> str:
    return " ".join(str(value).replace("\xa0", " ").split())


def _row(item_name: str, price: float, unit: str, section: str, ts: str) -> dict:
    row = {
        "observation_date": date.today().isoformat(),
        "period_kind": "current_menu",
        "country": _COUNTRY,
        "subnational_area": "Pago Pago",
        "source_key": _SOURCE_KEY,
        "coicop_code": _COICOP,
        "item_name": item_name[:500],
        "price_local": round(price, 2),
        "currency": _CURRENCY,
        "unit": unit,
        "source_url": _URL,
        "notes": f"Flying Fox Brewing Co. menu price; section={section}",
        "scrape_ts": ts,
        "observation_hash": None,
    }
    row["observation_hash"] = make_hash(row, _IDENT)
    return row


def _parse(text: str, ts: str) -> list[dict]:
    """Menu items render as: name, description, headline price, then optional
    ``<size>`` / ``$<price>`` variant pairs.

    The FIRST line after a completed item is the next item's name; anything
    after that and before its first price is the blurb, so descriptions can
    never be mistaken for the name. When an item publishes per-size pours the
    headline price is dropped, because it merely restates the largest pour and
    would otherwise double-count that beer."""
    rows: list[dict] = []
    section = "menu"
    item: str | None = None
    headline: float | None = None
    variants: list[tuple[str, float]] = []
    pending_size: str | None = None
    priced = False

    def flush() -> None:
        nonlocal item, headline, variants, pending_size, priced
        if item is not None:
            if variants:
                for size, price in variants:
                    rows.append(
                        _row(
                            f"{item}, {size}", price, size.replace(" ", "_"), section, ts
                        )
                    )
            elif headline is not None:
                rows.append(_row(item, headline, "item", section, ts))
        item, headline, variants, pending_size, priced = None, None, [], None, False

    for raw_line in text.splitlines():
        line = _clean(raw_line)
        if not line or line in _NOISE:
            continue
        if line in _SECTIONS:
            flush()
            section = _SECTIONS[line]
            continue

        if _EPIGRAPH_RE.match(line):
            continue

        size = _SIZE_RE.match(line)
        if size is not None:
            pending_size = f"{size.group('size')} oz"
            continue

        price_match = _PRICE_RE.match(line)
        if price_match is not None:
            if item is None:
                continue
            price = float(price_match.group("price").replace(",", ""))
            if pending_size is not None:
                variants.append((pending_size, price))
                pending_size = None
            elif headline is None:
                headline = price
            priced = True
            continue

        if priced:
            flush()
            item = line
        elif item is None:
            item = line
        # else: a blurb line for the item already named -- ignored.

    flush()

    deduped: list[dict] = []
    seen: set[str] = set()
    for row in rows:
        if row["observation_hash"] in seen:
            continue
        seen.add(row["observation_hash"])
        deduped.append(row)
    return deduped


def fetch_as_flyingfox_menu(cutoff: date) -> pd.DataFrame | None:
    today = date.today()
    if today <= cutoff:
        return None

    session = get_session()
    session.headers.update({"User-Agent": "Mozilla/5.0 price-research"})
    resp = session.get(_URL, timeout=60)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "lxml")
    text = soup.get_text("\n", strip=True)
    ts = get_scrape_ts()
    rows = _parse(text, ts)

    if not rows:
        logger.warning("[%s] no menu rows parsed", _SOURCE_KEY)
        return None
    out = pd.DataFrame(rows).drop_duplicates(subset=["observation_hash"])
    logger.info("[%s] parsed %d menu rows", _SOURCE_KEY, len(out))
    return out
