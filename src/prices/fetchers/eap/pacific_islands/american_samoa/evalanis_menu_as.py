"""Evalani's American Samoa restaurant menu prices."""

from __future__ import annotations

import logging
import re
from datetime import date

import pandas as pd
from bs4 import BeautifulSoup

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_URL = "https://ropetim.wixsite.com/evalanis-1/restaraunt"
_COUNTRY = "American Samoa"
_SOURCE_KEY = "as_evalanis_menu"
_CURRENCY = "USD"
_COICOP = "11.1.1"
_IDENT = ["source_key", "observation_date", "item_name"]
_MONEY_RE = re.compile(r"\$(?P<price>\d+(?:\.\d+)?)")

_SKIP_LINES = {
    "Afio Mai,",
    "Home",
    "Meet Evalani",
    "Bar & NightClub",
    "Motu O FiaFiaga Motel",
    "Restaraunt",
    "Gallery",
    "Events",
    "Contact/Booking",
    "More",
    "Please reload",
    "top of page",
    "bottom of page",
    "Use tab to navigate through the menu items.",
}


def _clean(value: str) -> str:
    value = value.replace("\xa0", " ")
    value = re.sub(r"[.]{2,}", " ", value)
    return " ".join(value.split()).strip(" -")


def _is_description(line: str) -> bool:
    lowered = line.lower()
    return (
        len(line) > 80
        or lowered.startswith("a ")
        or lowered.startswith("an ")
        or lowered.startswith("two ")
        or lowered.startswith("three ")
        or lowered.startswith("four ")
        or lowered.startswith("strips ")
        or lowered.startswith("shrimp grilled")
        or lowered.startswith("steak strips")
        or lowered.startswith("our ")
        or lowered.startswith("your ")
        or lowered.startswith("*")
        or lowered.startswith(",")
    )


def _row(item_name: str, price: float, notes: str, ts: str) -> dict:
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
        "unit": "item",
        "source_url": _URL,
        "notes": notes,
        "scrape_ts": ts,
        "observation_hash": None,
    }
    row["observation_hash"] = make_hash(row, _IDENT)
    return row


def _parse_menu(text: str, ts: str) -> list[dict]:
    rows: list[dict] = []
    section = "mexican specialties"
    previous_item = ""
    seen: set[str] = set()

    for raw_line in text.splitlines():
        line = _clean(raw_line)
        if not line or line in _SKIP_LINES:
            continue
        if line == "Side Order":
            section = "side order"
            previous_item = ""
            continue
        if line == "Lunch":
            section = "american favorites lunch"
            previous_item = ""
            continue
        if line == "Dinner":
            section = "american favorites dinner"
            previous_item = ""
            continue
        if line == "Appetizers":
            section = "american favorites dinner appetizers"
            previous_item = ""
            continue

        match = _MONEY_RE.search(line)
        if match:
            price = float(match.group("price"))
            name = _clean(line[: match.start()]) or previous_item
            if not name or _is_description(name):
                continue
            if name.upper().startswith("BEEF TACO SPECALS"):
                name = "Beef taco special, 5 tacos"
            item_name = f"Evalani's menu item, {section}, {name}"
            if item_name in seen:
                continue
            seen.add(item_name)
            rows.append(
                _row(
                    item_name,
                    price,
                    f"Restaurant menu row parsed from Wix page; section={section}",
                    ts,
                )
            )
            previous_item = ""
            continue

        if line in {"Mexic", "an Speci", "alties", "Ameri", "can Fav", "orites"}:
            continue
        if not _is_description(line):
            previous_item = line

    return rows


def fetch_as_evalanis_menu(cutoff: date) -> pd.DataFrame | None:
    today = date.today()
    if today <= cutoff:
        return None

    session = get_session()
    session.headers.update({"User-Agent": "Mozilla/5.0 price-research"})
    resp = session.get(_URL, timeout=45)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "lxml")
    text = soup.get_text("\n", strip=True)
    rows = _parse_menu(text, get_scrape_ts())

    logger.info("[%s] parsed %d menu rows", _SOURCE_KEY, len(rows))
    return pd.DataFrame(rows) if rows else None
