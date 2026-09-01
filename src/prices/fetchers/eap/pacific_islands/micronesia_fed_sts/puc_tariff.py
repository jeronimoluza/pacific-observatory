"""Pohnpei Utilities Corporation (PUC) -- electricity + water tariff.

pohnpeipuc.fm publishes its "Current Tariff Schedule" directly in the
homepage-linked Power Generation & Distribution page
(``/index.php/pages/powerg-d``) as two small server-rendered HTML
``<table>``s side by side (Power user/Rate, Water user/Rate), each followed
by two plain-text "Senior Citizen" lines that are NOT inside the table.
Tier 1A, plain ``requests`` -- no WAF, no JS.

Electricity and water are combined into ONE source (rather than split into
two manifests the way Vanuatu's URA page was) because, unlike URA, each
individual rate block here is thin (3-4 line items) -- water alone would
land under the onboarding skill's 5-row Phase-6 gate. Every row still
carries its own correct COICOP leaf (04.5.1 electricity / 04.4.1 water) set
here in code, so the combined source_key does not blur per-leaf coverage
reporting; only the manifest file itself is shared.

"Senior Citizen Discount rate" lines are read on the page but deliberately
NOT emitted as rows -- see the docstring on `_leaf_senior_lines` for why
(they're a derived delta between two rates already emitted, and the
water-block discount figure is independently provably wrong on the site's
own page: 10x off from what its own two rate rows imply).

No effective-date is published -- the page says "Currently, the tariffs
charged by PUC ... are as follows", i.e. this is a live "current rate" page
PUC edits in place. Modelled as a daily period_kind=snapshot at scrape time,
same pattern as fsmtc_tariff.py.

Currency is USD (FSM's actual currency, no FX conversion needed).
"""

from __future__ import annotations

import logging
import re
from datetime import date

import pandas as pd
from bs4 import BeautifulSoup

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_COUNTRY = "Micronesia, Fed. Sts."
_CURRENCY = "USD"
_SOURCE_KEY = "fm_puc_tariff"
_STATE = "Pohnpei"
_URL = "https://www.pohnpeipuc.fm/index.php/pages/powerg-d"
_IDENT = ["source_key", "observation_date", "item_name"]

_ELECTRICITY_COICOP = "04.5.1"
_WATER_COICOP = "04.4.1"


def _price(text: str) -> float | None:
    m = re.search(r"[\d,.]+", text.replace(",", ""))
    if not m:
        return None
    try:
        val = float(m.group(0))
    except ValueError:
        return None
    return val if val > 0 else None


def _parse_power_block(soup: BeautifulSoup) -> list[dict]:
    heading = soup.find(string=re.compile(r"Power user\s*/\s*Rate"))
    if heading is None:
        logger.warning("[%s] 'Power user / Rate' heading not found", _SOURCE_KEY)
        return []
    container = heading.find_parent("h4").find_parent("div", class_="sppb-addon")
    table = container.find("table")
    out = []
    if table is not None:
        for tr in table.find_all("tr")[1:]:  # skip header row
            cells = tr.find_all("td")
            if len(cells) != 2:
                continue
            label = cells[0].get_text(" ", strip=True)
            price = _price(cells[1].get_text(" ", strip=True))
            if price is None or not label:
                continue
            out.append(
                {
                    "item_name": f"Electricity -- {label}",
                    "price_local": price,
                    "unit": "USD/kWh",
                    "coicop_code": _ELECTRICITY_COICOP,
                }
            )
    for label, price in _leaf_senior_lines(container):
        out.append(
            {
                "item_name": f"Electricity -- {label}",
                "price_local": price,
                "unit": "USD/kWh",
                "coicop_code": _ELECTRICITY_COICOP,
            }
        )
    return out


def _leaf_senior_lines(container) -> list[tuple[str, float]]:
    """Yield (label, price) for each LEAF '<div>Senior Citizen Rate...</div>'.

    Only leaf divs (no nested <div>) are used, so an outer wrapper div
    whose .get_text() concatenates all its children's text isn't also
    counted as a spurious extra row. Text is NBSP-normalized ('\\xa0' -> ' ')
    before the "Senior Citizen" prefix check, because the source's markup
    inconsistently uses a literal space in some lines and '&nbsp;' in
    others between the two words.

    "Senior Citizen Discount rate" lines are deliberately excluded here --
    they are not an independent price, they are (base rate - senior rate),
    and both of those are already emitted as their own rows. Emitting the
    delta too would let a naive average/index over this source's rows mix a
    ~0.05 delta in with ~0.50 rates. It is also independently unsafe to
    trust as data: on the water block, the page's own printed discount is
    $0.0237, but its own two rate rows are $2.37 and $2.133 -- a real
    difference of $0.237, i.e. the page's discount figure is off by 10x
    from the page's own rate rows (electricity's discount IS internally
    consistent: 0.4988 - 0.0499 = 0.4489, a clean 10% senior discount --
    water's typo breaks that pattern). Rather than silently "fixing" a
    number pulled from someone else's page, we don't emit it at all; the
    two rate rows a caller actually needs (base + senior) are unaffected by
    this and are correct.
    """
    out = []
    for div in container.find_all("div"):
        if div.find("div") is not None:
            continue  # wrapper, not a leaf line
        text = div.get_text(" ", strip=True).replace("\xa0", " ")
        text = re.sub(r"\s+", " ", text).strip()
        if not text.startswith("Senior Citizen") or "discount" in text.lower():
            continue
        price = _price(text)
        if price is None:
            continue
        # Label = everything before the ':' (if present) or before the
        # first '$' (some lines have no colon, e.g. "...rate  $0.0499").
        label = re.split(r":|\$", text, maxsplit=1)[0].strip()
        out.append((label, price))
    return out


def _parse_water_block(soup: BeautifulSoup) -> list[dict]:
    heading = soup.find(string=re.compile(r"Water user\s*/\s*Rate"))
    if heading is None:
        logger.warning("[%s] 'Water user / Rate' heading not found", _SOURCE_KEY)
        return []
    container = heading.find_parent("h4").find_parent("div", class_="sppb-addon")
    table = container.find("table")
    out = []
    if table is not None:
        for tr in table.find_all("tr"):
            cells = tr.find_all("td")
            if len(cells) != 2:
                continue
            label = cells[0].get_text(" ", strip=True)
            price = _price(cells[1].get_text(" ", strip=True))
            if price is None or not label:
                continue
            out.append(
                {
                    "item_name": f"Water -- {label}",
                    "price_local": price,
                    "unit": "USD/1000gal"
                    if "1000" in cells[1].get_text()
                    else "USD/month",
                    "coicop_code": _WATER_COICOP,
                }
            )
    for label, price in _leaf_senior_lines(container):
        out.append(
            {
                "item_name": f"Water -- {label}",
                "price_local": price,
                "unit": "USD/1000gal",
                "coicop_code": _WATER_COICOP,
            }
        )
    return out


def fetch_fm_puc_tariff(cutoff: date) -> pd.DataFrame | None:
    today = date.today()
    if today <= cutoff:
        logger.info("[%s] already snapshotted today (cutoff=%s)", _SOURCE_KEY, cutoff)
        return None

    session = get_session()
    resp = session.get(_URL, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")

    items = _parse_power_block(soup) + _parse_water_block(soup)
    if not items:
        logger.warning("[%s] no tariff rows parsed from %s", _SOURCE_KEY, _URL)
        return None

    ts = get_scrape_ts()
    rows = []
    for item in items:
        row = {
            "observation_date": today.isoformat(),
            "period_kind": "snapshot",
            "country": _COUNTRY,
            "subnational_area": _STATE,
            "source_key": _SOURCE_KEY,
            "coicop_code": item["coicop_code"],
            "item_name": item["item_name"],
            "price_local": item["price_local"],
            "currency": _CURRENCY,
            "unit": item["unit"],
            "source_url": _URL,
            "notes": None,
            "scrape_ts": ts,
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)

    return pd.DataFrame(rows)
