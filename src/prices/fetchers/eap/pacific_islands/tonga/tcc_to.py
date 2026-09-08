"""Tonga Communications Corporation (TCC) — prepaid mobile data/voice/SMS bundles.

Scrapes the SSR HTML plan-listing page at tcc.to. The site is WordPress +
Elementor; each plan group (Unet Plans, Super Data Plans, Student SIM Plans,
Oukka Plans, Night Owl Plans, Voice Plan, ...) is rendered as an Elementor
"price-table" widget (``div.elementor-widget-price-table``) whose heading
(``.elementor-price-table__heading``) names the plan group, and whose
feature-list items (``li.elementor-repeater-item-*``) each hold one bundle
as free text, e.g. "$1.00 TOP | 400MB Data | valid 1hour" — "TOP" here is
the site's own "top-up" abbreviation, not the currency code (the currency
actually is Tongan Pa'anga, ISO TOP, from ``countries.yaml``; the site only
ever shows a bare "$"). No JS execution is required — the tariff data is
present in the raw server response.

Source URL: https://www.tcc.to/prepaid-voice-plan/
"""

from __future__ import annotations

import logging
import re
from datetime import date

import pandas as pd
from bs4 import BeautifulSoup

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_URL = "https://www.tcc.to/prepaid-voice-plan/"
_COUNTRY = "Tonga"
_CURRENCY = "TOP"
_SOURCE_KEY = "tcc_to"
_IDENT = ["source_key", "observation_date", "item_name"]

_PRICE_RE = re.compile(r"\$\s?([0-9]+(?:\.[0-9]{1,2})?)")


def _coicop_for(text: str) -> str:
    """Per-item COICOP-2018 leaf under 08.3 (Information and communication
    services), based on which of data/SMS/minutes the bundle line mentions."""
    has_data = "Data" in text
    has_voice = "Minutes" in text or "SMS" in text or "Call" in text or "Voice" in text
    if has_data and has_voice:
        return "08.3.4.0"  # Bundled telecommunication services
    if has_data:
        return "08.3.3.0"  # Internet access provision services (data-only)
    if has_voice:
        return "08.3.2.0"  # Mobile communication services (voice/SMS-only)
    return "08.3.2.0"  # Default: TCC is a mobile operator; residual = mobile comms


def fetch_tcc_to(cutoff: date) -> pd.DataFrame | None:
    obs_date = date.today()
    if obs_date <= cutoff:
        return None

    session = get_session()
    resp = session.get(_URL, timeout=30)
    if resp.status_code != 200:
        logger.warning("[%s] HTTP %d for %s", _SOURCE_KEY, resp.status_code, _URL)
        return None

    soup = BeautifulSoup(resp.text, "html.parser")
    widgets = soup.find_all("div", class_="elementor-widget-price-table")

    rows: list[dict] = []
    for w in widgets:
        heading_el = w.find(class_="elementor-price-table__heading")
        heading = heading_el.get_text(strip=True) if heading_el else "Plan"
        items = w.find_all("li", class_=lambda c: c and "elementor-repeater-item" in c)
        for item in items:
            text = item.get_text(strip=True)
            m = _PRICE_RE.search(text)
            if not m:
                continue
            price_local = float(m.group(1))
            row = {
                "observation_date": obs_date.isoformat(),
                "period_kind": "snapshot",
                "country": _COUNTRY,
                "source_key": _SOURCE_KEY,
                "coicop_code": _coicop_for(text),
                "item_name": f"TCC Tonga prepaid plan, {heading}: {text}",
                "price_local": price_local,
                "currency": _CURRENCY,
                "unit": "bundle",
                "source_url": _URL,
                "notes": heading,
                "scrape_ts": get_scrape_ts(),
                "observation_hash": None,
            }
            row["observation_hash"] = make_hash(row, _IDENT)
            rows.append(row)

    if not rows:
        logger.warning("[%s] No plans parsed from %s", _SOURCE_KEY, _URL)
        return None

    df = pd.DataFrame(rows)
    dup_count = int(df["observation_hash"].duplicated().sum())
    if dup_count:
        logger.warning("[%s] %d duplicate observation_hash rows before de-dup", _SOURCE_KEY, dup_count)
        df = df.drop_duplicates(subset="observation_hash")
    return df
