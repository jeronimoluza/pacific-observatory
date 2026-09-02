"""Moov Africa Malitel — mobile internet data-plan tariffs, Mali.

Scrapes the server-rendered "Forfaits internet mobile" page at malitel.ml
(a SharePoint-style .aspx public content page — no login, no anti-bot).
The page lays out 21 prepaid data-plan cards (`div.dropshadaw`), each with
a price (`.gradient-container p`, e.g. "500 FCFA" / "1 000 CFA") and two
bold values in `.ptexte`: the data allowance ("500 Mo", "2.6 Go") and the
validity window ("30 jours", "23H- 07H" for a night-only bundle).

No effective/decision date is printed on the page — this is a live
snapshot of the tariff schedule currently in force, so observation_date is
the scrape date (period_kind=snapshot), matching the cie_tariff.py /
our_telekom_plans.py convention.

NOTE: malitel.ml fails TLS certificate verification with both curl_cffi
(impersonate=chrome124) and plain requests identically (server-side
misconfiguration, not a transient block) -- verify=False is required; the
page carries no credentials or user input, only published tariff data.

COICOP: 08.1.0 (telephone and telefax equipment/services -- mobile data),
matching the vodafone_ki_prepaid_data.yaml convention for prepaid mobile
data bundles.
"""

from __future__ import annotations

import logging
import re
from datetime import date

import pandas as pd
from bs4 import BeautifulSoup

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_TARIFF_URL = (
    "https://malitel.ml/particulier/internet/Pages/" "Forfaits%20internet%20mobile.aspx"
)
_COUNTRY = "Mali"
_CURRENCY = "XOF"
_SOURCE_KEY = "malitel_ml_tariff"
_COICOP_CODE = "08.1.0"
_IDENT = ["source_key", "observation_date", "item_name"]


def _parse_price(text: str) -> float | None:
    """'500 FCFA' / '1 000 CFA' / '4 500  FCFA' -> 500.0 / 1000.0 / 4500.0."""
    cleaned = re.sub(r"(?i)f?cfa", "", text)
    cleaned = cleaned.replace("\xa0", "").replace(" ", "").strip()
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _extract_tariff_rows(soup: BeautifulSoup, obs_date: date) -> list[dict]:
    rows: list[dict] = []
    ts = get_scrape_ts()
    for card in soup.select("div.dropshadaw"):
        price_el = card.select_one(".gradient-container p")
        ptexte = card.select_one(".ptexte")
        if price_el is None or ptexte is None:
            continue
        price_local = _parse_price(price_el.get_text(strip=True))
        bolds = [b.get_text(strip=True) for b in ptexte.find_all("b")]
        if price_local is None or price_local <= 0 or len(bolds) < 2:
            continue
        data_allowance, validity = bolds[0], bolds[1]
        item_name = f"Malitel forfait internet mobile {data_allowance} / {validity}"
        row = {
            "observation_date": obs_date.isoformat(),
            "period_kind": "snapshot",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "coicop_code": _COICOP_CODE,
            "item_name": item_name,
            "price_local": price_local,
            "currency": _CURRENCY,
            "unit": data_allowance,
            "source_url": _TARIFF_URL,
            "notes": f"validity={validity}",
            "scrape_ts": ts,
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)
    return rows


def fetch_malitel_ml_tariff(cutoff: date) -> pd.DataFrame | None:
    obs_date = date.today()
    if obs_date <= cutoff:
        return None

    session = get_session()
    resp = session.get(_TARIFF_URL, timeout=30, verify=False)
    if resp.status_code != 200:
        logger.warning(
            "[%s] HTTP %d for %s", _SOURCE_KEY, resp.status_code, _TARIFF_URL
        )
        return None

    soup = BeautifulSoup(resp.text, "html.parser")
    rows = _extract_tariff_rows(soup, obs_date)
    if not rows:
        logger.warning("[%s] No tariff rows parsed from %s", _SOURCE_KEY, _TARIFF_URL)
        return None

    # Dedup identical (price, data_allowance, validity) cards -- the page
    # occasionally repeats a card inside a mobile-responsive duplicate block.
    df = pd.DataFrame(rows).drop_duplicates(subset=["item_name", "price_local"])
    return df
