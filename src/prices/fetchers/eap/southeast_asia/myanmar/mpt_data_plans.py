"""MPT (Myanmar Post and Telecommunications) -- mobile data bundle plans.

Static, server-rendered HTML page (`/en/packages-and-plans/`) built from
Visual Composer "toggle" accordion sections, each containing a
`<ul class="pack_box"><li class="pack-li">...` list of plan cards. Every
card carries `Price : <n> Ks`, `Data : <n> MB|GB`, `Validity : <n> day(s)`
as plain `<p>` text lines under an `<h3>` plan name -- no JS rendering
needed, confirmed via plain `requests` fetch 2026-09-06 (20 cards on the
page).

A handful of cards share an identical `<h3>` name + price + data + validity
(the three "A Kyite Kyi (Auto Renew)" YouTube/TikTok/Telegram-only variants,
all 298 Ks / 300 MB / 1 day) -- these are genuinely distinct products (each
subscribes/unsubscribes via its own USSD code, and the site itself
distinguishes them only via a styled `<p style="color:#0030b7">App Only</p>`
line after Validity, not part of the `<h3>`). That descriptor is folded
into `item_name` specifically to keep these rows from colliding on the
identity hash.

Cadence: irregular -- MPT changes plan prices/pack sizes without a
published change-log; this fetcher snapshots whatever is live at fetch
time (`period_kind: snapshot`), same treatment as air_vanuatu_domestic.py
(no per-plan effective-date is published).
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime, timezone

import pandas as pd
from bs4 import BeautifulSoup

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_URL = "https://mpt.com.mm/en/packages-and-plans/"
_COUNTRY = "Myanmar"
_CURRENCY = "MMK"
_SOURCE_KEY = "mm_mpt_data_plans"
_COICOP = "08.3.2.0"
_IDENT = ["source_key", "item_name", "price_local"]

_APP_ONLY_RE = re.compile(r"([A-Za-z ]+ Only)")


def _parse_cards(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    out: list[dict] = []
    for li in soup.select("li.pack-li"):
        text = li.get_text("\n", strip=True)

        h3 = li.find("h3")
        name = h3.get_text(strip=True) if h3 else None

        price_m = re.search(r"Price\s*:\s*([\d,]+)\s*Ks", text)
        data_m = re.search(r"Data\s*:\s*([^\n]+)", text)
        valid_m = re.search(r"Validity\s*:\s*([^\n]+)", text)
        app_m = _APP_ONLY_RE.search(text)

        if not (name and price_m):
            continue

        try:
            price = float(price_m.group(1).replace(",", ""))
        except ValueError:
            continue
        if price <= 0:
            continue

        label_parts = [name]
        if data_m:
            label_parts.append(data_m.group(1).strip())
        if valid_m:
            label_parts.append(valid_m.group(1).strip())
        if app_m:
            label_parts.append(app_m.group(1).strip())

        out.append(
            {
                "item_name": " – ".join(label_parts),
                "price_local": price,
            }
        )
    return out


def fetch_mm_mpt_data_plans(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    resp = session.get(_URL, timeout=30)
    resp.raise_for_status()

    parsed = _parse_cards(resp.text)
    if not parsed:
        logger.warning("[%s] No plan cards found at %s", _SOURCE_KEY, _URL)
        return None

    observation_date = datetime.now(timezone.utc).date()
    if observation_date <= cutoff:
        return None

    rows = []
    seen_hashes = set()
    for item in parsed:
        row = {
            "observation_date": observation_date.isoformat(),
            "period_kind": "snapshot",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "item_name": item["item_name"],
            "price_local": item["price_local"],
            "currency": _CURRENCY,
            "unit": "plan",
            "coicop_code": _COICOP,
            "source_url": _URL,
            "notes": "MPT mobile data bundle, snapshot at fetch time (no published effective date).",
            "scrape_ts": get_scrape_ts(),
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        if row["observation_hash"] in seen_hashes:
            continue
        seen_hashes.add(row["observation_hash"])
        rows.append(row)

    return pd.DataFrame(rows) if rows else None
