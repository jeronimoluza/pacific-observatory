"""Smart Axiata (Cambodia) -- published prepaid plan entry-tier tariffs.

https://www.smart.com.kh/plans lists Smart's plan families as
server-rendered cards (plain ``requests`` needs no JS/impersonation --
confirmed live 2026-09-06). Each card has an ``<img alt="...">`` carrying
the plan family name and a "Starts from X USD/<period>" line.

This is coarser than a full tariff schedule: the per-plan detail pages
(``/plans/<slug>``) render their tier-by-tier price table client-side (no
price text present in the server HTML -- confirmed empty on
``/plans/5g-data``), so only the entry/"starts from" price per plan family
is captured here. Still real, non-zero, verifiable published pricing for a
division (08 communication services) with no other Cambodia coverage in
this repo. Revisit with Playwright if the full per-tier table is wanted.

Plans without a numeric "Starts from" price (bonus/top-up add-ons such as
Smart Flexi250, or plans priced per-call rather than per-period such as
Smart Sponsored Call) are skipped -- no exploitable list price.
"""

from __future__ import annotations

import logging
import re
from datetime import date

import pandas as pd
from bs4 import BeautifulSoup

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_URL = "https://www.smart.com.kh/plans"
_COUNTRY = "Cambodia"
_CURRENCY = "USD"
_SOURCE_KEY = "kh_smart_tariff"
_COICOP = "08.3.0"
_IDENT = ["source_key", "observation_date", "item_name"]

_PRICE_RE = re.compile(r"Starts from\s*([0-9]+(?:\.[0-9]+)?)\s*USD\s*/\s*([0-9]*\s*[a-zA-Z]+)")


def fetch_kh_smart_tariff(cutoff: date) -> pd.DataFrame | None:
    today = date.today()
    if today <= cutoff:
        logger.info("[%s] already snapshotted today (cutoff=%s)", _SOURCE_KEY, cutoff)
        return None

    session = get_session()
    resp = session.get(_URL, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")

    cards = soup.select("div.m-3")
    if not cards:
        logger.warning("[%s] no plan cards found", _SOURCE_KEY)
        return None

    scrape_ts = get_scrape_ts()
    rows: list[dict] = []
    seen_names: set[str] = set()
    for card in cards:
        img = card.find("img", alt=True)
        if not img:
            continue
        name = img["alt"].strip()
        if not name or name in seen_names:
            continue
        text = card.get_text(" ", strip=True)
        m = _PRICE_RE.search(text)
        if not m:
            continue
        price = float(m.group(1))
        period = re.sub(r"\s+", " ", m.group(2)).strip()
        seen_names.add(name)
        row = {
            "observation_date": today.isoformat(),
            "period_kind": "snapshot",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "coicop_code": _COICOP,
            "item_name": f"{name} -- entry tier",
            "price_local": price,
            "currency": _CURRENCY,
            "unit": period,
            "source_url": _URL,
            "notes": "'Starts from' entry-tier price; full per-tier table is client-rendered",
            "scrape_ts": scrape_ts,
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)

    if not rows:
        logger.warning("[%s] no priced plan cards parsed", _SOURCE_KEY)
        return None
    return pd.DataFrame(rows)
