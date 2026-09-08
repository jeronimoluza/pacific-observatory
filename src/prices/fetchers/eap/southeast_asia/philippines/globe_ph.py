"""Globe Telecom (Philippines) — prepaid promo bundles.

Scrapes the SSR HTML promo-listing page at globe.com.ph/prepaid/promos. The
page renders ~20 Bootstrap "card" widgets inside a Swiper carousel; most are
category-navigation tiles with no price (e.g. "Go+", "GoEXTRA"), but a
fixed small set carry an actual offer: a ``card-title`` naming the plan
(e.g. "Go+99") and a ``card-text`` whose first ``<strong>`` line holds the
data allowance, price and validity, e.g. "20 GB Data | ₱99/7 Days". No JS
execution is required — this content is present in the raw server response
(unlike the Vue-hydrated mamikos.com listing probed for the same shard).
The front door does 403 a plain ``requests`` session (TLS-fingerprint
block, not a JS challenge) so this fetcher uses ``curl_cffi`` with a
``chrome124`` impersonation profile instead.

The promo set here is a small, bounded catalog by design (a telco's
currently-active prepaid promos), not a paginated product catalog, so a
single page fetch is the complete current offer list.

Source URL: https://www.globe.com.ph/prepaid/promos
"""

from __future__ import annotations

import logging
import re
from datetime import date

import pandas as pd
from bs4 import BeautifulSoup
from curl_cffi import requests as curl_requests

from prices.fetchers.utils import get_scrape_ts, make_hash

logger = logging.getLogger(__name__)

_URL = "https://www.globe.com.ph/prepaid/promos"
_COUNTRY = "Philippines"
_CURRENCY = "PHP"
_SOURCE_KEY = "globe_ph"
_IDENT = ["source_key", "observation_date", "item_name"]

_PRICE_RE = re.compile(r"₱\s?([0-9,]+(?:\.[0-9]{2})?)")


def _coicop_for(text: str) -> str:
    has_data = "Data" in text or "GB" in text
    has_voice = "Text" in text or "Minute" in text or "Call" in text
    if has_data and has_voice:
        return "08.3.4.0"  # Bundled telecommunication services
    if has_data:
        return "08.3.3.0"  # Internet access provision services (data-only)
    return "08.3.2.0"  # Mobile communication services (voice/SMS-only)


def fetch_globe_ph(cutoff: date) -> pd.DataFrame | None:
    obs_date = date.today()
    if obs_date <= cutoff:
        return None

    resp = curl_requests.get(_URL, impersonate="chrome124", timeout=30)
    if resp.status_code != 200:
        logger.warning("[%s] HTTP %d for %s", _SOURCE_KEY, resp.status_code, _URL)
        return None

    soup = BeautifulSoup(resp.text, "html.parser")
    cards = soup.find_all("div", class_="card-body")

    rows: list[dict] = []
    for c in cards:
        title_el = c.find(class_="card-title")
        text_el = c.find(class_="card-text")
        if not title_el or not text_el:
            continue
        text = text_el.get_text(" ", strip=True)
        m = _PRICE_RE.search(text)
        if not m:
            continue  # category-nav tile, no offer
        price_local = float(m.group(1).replace(",", ""))
        plan_name = title_el.get_text(strip=True)
        row = {
            "observation_date": obs_date.isoformat(),
            "period_kind": "snapshot",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "coicop_code": _coicop_for(text),
            "item_name": f"Globe Prepaid {plan_name}: {text[:200]}",
            "price_local": price_local,
            "currency": _CURRENCY,
            "unit": "bundle",
            "source_url": _URL,
            "notes": None,
            "scrape_ts": get_scrape_ts(),
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)

    if not rows:
        logger.warning("[%s] No priced promo cards parsed from %s", _SOURCE_KEY, _URL)
        return None

    df = pd.DataFrame(rows)
    dup_count = int(df["observation_hash"].duplicated().sum())
    if dup_count:
        logger.warning("[%s] %d duplicate observation_hash rows before de-dup", _SOURCE_KEY, dup_count)
        df = df.drop_duplicates(subset="observation_hash")
    return df
