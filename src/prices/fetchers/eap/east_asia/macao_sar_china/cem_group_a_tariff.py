"""Macao CEM Group A electricity tariff page."""

from __future__ import annotations

import re
from datetime import date

import pandas as pd
import requests
from bs4 import BeautifulSoup

from prices.fetchers.utils import get_scrape_ts, make_hash

_URL = "https://www.cem-macau.com/en/customer-service/billing-service/tariff-group-a/"
_COUNTRY = "Macao SAR, China"
_CURRENCY = "MOP"
_SOURCE_KEY = "mo_cem_group_a_tariff"
_COICOP = "04.5.1"
_IDENT = ["source_key", "observation_date", "item_name", "unit"]
_NUM_RE = re.compile(r"[\d,.]+")


def _parse_price(text: str) -> float | None:
    match = _NUM_RE.search(text.replace(",", ""))
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


def _make_row(
    *,
    today: date,
    item_name: str,
    price: float,
    unit: str,
    notes: str,
    scrape_ts: str,
) -> dict:
    row = {
        "observation_date": today.isoformat(),
        "period_kind": "snapshot",
        "country": _COUNTRY,
        "subnational_area": None,
        "source_key": _SOURCE_KEY,
        "coicop_code": _COICOP,
        "item_name": item_name,
        "price_local": price,
        "currency": _CURRENCY,
        "unit": unit,
        "source_url": _URL,
        "notes": notes,
        "scrape_ts": scrape_ts,
        "observation_hash": None,
    }
    row["observation_hash"] = make_hash(row, _IDENT)
    return row


def _tariff_sections(soup: BeautifulSoup) -> list[tuple[str, list[list[str]]]]:
    sections: list[tuple[str, list[list[str]]]] = []
    for section in soup.select("section.collapse-box"):
        title_el = section.select_one(".collapse-box-title")
        title = title_el.get_text(" ", strip=True) if title_el else ""
        if not title:
            continue
        table = section.select_one("table")
        if table is None:
            continue
        rows = []
        for tr in table.select("tr"):
            cells = [c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"])]
            if cells:
                rows.append(cells)
        sections.append((title, rows))
    return sections


def _rows_from_tariff_tables(soup: BeautifulSoup, today: date, scrape_ts: str) -> list[dict]:
    rows: list[dict] = []
    for title, table_rows in _tariff_sections(soup):
        for cells in table_rows[1:]:
            if len(cells) < 3:
                continue
            subscribed_demand, demand_text, energy_text = cells[:3]
            demand = _parse_price(demand_text)
            energy = _parse_price(energy_text)

            if demand is not None:
                unit = "MOP/kVA" if "kVA" in demand_text else "MOP/month"
                rows.append(
                    _make_row(
                        today=today,
                        item_name=f"{title} demand charge, {subscribed_demand}",
                        price=demand,
                        unit=unit,
                        notes="CEM Group A tariff table, demand component",
                        scrape_ts=scrape_ts,
                    )
                )
            if energy is not None:
                rows.append(
                    _make_row(
                        today=today,
                        item_name=f"{title} energy charge, {subscribed_demand}",
                        price=energy,
                        unit="MOP/kWh",
                        notes="CEM Group A tariff table, energy component",
                        scrape_ts=scrape_ts,
                    )
                )
    return rows


def fetch_mo_cem_group_a_tariff(cutoff: date) -> pd.DataFrame | None:
    today = date.today()
    if today <= cutoff:
        return None

    session = requests.Session()
    session.headers.update(
        {
            "Accept": "text/html,application/xhtml+xml",
            "User-Agent": "python-requests/2.32",
        }
    )
    resp = session.get(_URL, timeout=45, verify=False)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    text = soup.get_text(" ", strip=True)
    if "A1 General Tariff" not in text or "A4 Social Support Tariff" not in text:
        raise ValueError("CEM Group A page did not include expected tariff sections")

    rows = _rows_from_tariff_tables(soup, today, get_scrape_ts())
    return pd.DataFrame(rows) if rows else None
