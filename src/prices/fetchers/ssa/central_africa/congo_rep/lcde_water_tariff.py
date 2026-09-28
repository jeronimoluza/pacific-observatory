"""LCDE (La Congolaise des Eaux) -- household water tariff, Republic of the
Congo.

Scrapes the server-rendered tarifs page at lcde-sa.cg, which carries two
kinds of published price:

1. **Consumption tariff** ("Tarif du metre cube", <h3>Eau</h3> section):
   4 rows -- per-cubic-metre FCFA price by customer class (Domestiques
   <=55 m3 / >55 m3, Non Domestiques, Non Domestiques Industriels).
2. **Connection-fee schedule** (<h3>ABONNEMENT SUR NOUVEAU BRANCHEMENT</h3>
   and <h3>ABONNEMENT SUR ANCIEN BRANCHEMENT</h3>): 10 tables, each a
   line-item cost breakdown (frais administratif, materiel, TVA, ...) by
   pipe diameter (DN15..DN200) ending in a "TOTAL (FCFA)" row -- the actual
   one-time FCFA amount a customer pays for a new or existing connection.
   Only the TOTAL row is emitted per (group, subsection, diameter); the
   accounting breakdown lines are not separate consumer prices.

Both are genuine LCDE-published FCFA prices; combining them clears the
5-row shipping bar (4 consumption rows alone did not) and adds real
household/institutional water-connection cost coverage. No effective/
decision date is printed on the page -- scraped as a live snapshot
(period_kind=snapshot, observation_date=scrape date), same convention as
civ_cie_tariff.py.

COICOP: 04.4.1 (water supply) for both the consumption tariff and the
connection fees -- both are LCDE water-service charges paid by the
household.
"""

from __future__ import annotations

import logging
from datetime import date

import pandas as pd
from bs4 import BeautifulSoup

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_TARIFF_URL = "https://lcde-sa.cg/informations-clientele/tarifs/"
_COUNTRY = "Congo, Rep."
_CURRENCY = "XAF"
_SOURCE_KEY = "cog_lcde_water_tariff"
_COICOP_CODE = "04.4.1"
_IDENT = ["source_key", "observation_date", "item_name"]

_GROUP_HEADINGS = {
    "ABONNEMENT SUR NOUVEAU BRANCHEMENT",
    "ABONNEMENT SUR ANCIEN BRANCHEMENT",
}


def _parse_fcfa(text: str) -> float | None:
    """'130,00 FCFA' -> 130.0 ; '1\xa0571 000' -> 1571000.0."""
    cleaned = text.replace("\xa0", "").replace(" ", "").replace(" ", "")
    cleaned = cleaned.replace("FCFA", "").strip()
    if not cleaned or cleaned == "–":
        return None
    cleaned = cleaned.replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def _extract_consumption_rows(soup: BeautifulSoup, obs_date: date) -> list[dict]:
    rows: list[dict] = []
    table = soup.find("table")
    if table is None:
        return rows
    for tr in table.find_all("tr"):
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
        if len(cells) != 3:
            continue
        category, tranche, price_text = cells
        if category.strip().lower().startswith("catégorie"):
            continue  # header row
        price_local = _parse_fcfa(price_text)
        if price_local is None:
            continue
        item_name = f"LCDE eau, consommation, {category}, {tranche}"
        rows.append(
            {
                "item_name": item_name,
                "price_local": price_local,
                "unit": "m3",
                "notes": "Tarif du metre cube, consumption tariff",
            }
        )
    return rows


def _extract_connection_fee_rows(soup: BeautifulSoup) -> list[dict]:
    rows: list[dict] = []
    group = None
    sub = None
    for el in soup.find_all(["h3", "table"]):
        if el.name == "h3":
            txt = el.get_text(" ", strip=True)
            if txt in _GROUP_HEADINGS:
                group = txt
                sub = None
            else:
                sub = txt
            continue
        if group is None:
            continue  # tables before the connection-fee section (the consumption table)
        trs = el.find_all("tr")
        if not trs:
            continue
        header = [c.get_text(" ", strip=True) for c in trs[0].find_all(["td", "th"])]
        diam_cols = header[2:]  # e.g. ["DN15", "DN20", ...]
        total_row = None
        for tr in trs:
            cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
            if len(cells) >= 2 and "TOTAL" in cells[1]:
                total_row = cells
                break
        if total_row is None:
            continue
        prices = total_row[2:]
        for diam, price_text in zip(diam_cols, prices):
            price_local = _parse_fcfa(price_text)
            if price_local is None:
                continue
            item_name = f"LCDE eau, {group}, {sub}, {diam}"
            rows.append(
                {
                    "item_name": item_name,
                    "price_local": price_local,
                    "unit": "forfait",
                    "notes": f"{group} TOTAL, {diam}",
                }
            )
    return rows


def fetch_cog_lcde_water_tariff(cutoff: date) -> pd.DataFrame | None:
    obs_date = date.today()
    if obs_date <= cutoff:
        return None

    session = get_session()
    resp = session.get(_TARIFF_URL, timeout=30)
    if resp.status_code != 200:
        logger.warning(
            "[%s] HTTP %d for %s", _SOURCE_KEY, resp.status_code, _TARIFF_URL
        )
        return None

    soup = BeautifulSoup(resp.text, "html.parser")
    parsed = _extract_consumption_rows(soup, obs_date) + _extract_connection_fee_rows(
        soup
    )
    if not parsed:
        logger.warning("[%s] No tariff rows parsed from %s", _SOURCE_KEY, _TARIFF_URL)
        return None

    rows: list[dict] = []
    for p in parsed:
        row = {
            "observation_date": obs_date.isoformat(),
            "period_kind": "snapshot",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "coicop_code": _COICOP_CODE,
            "item_name": p["item_name"],
            "price_local": p["price_local"],
            "currency": _CURRENCY,
            "unit": p["unit"],
            "source_url": _TARIFF_URL,
            "notes": p["notes"],
            "scrape_ts": get_scrape_ts(),
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)

    return pd.DataFrame(rows)
