"""Brunei DES residential and commercial electricity tariff tables."""

from __future__ import annotations

import re
from datetime import date

import pandas as pd
import requests
from bs4 import BeautifulSoup

from prices.fetchers.utils import get_scrape_ts, make_hash

_URL = "https://www.des.gov.bn/electricity-tariff/"
_COUNTRY = "Brunei Darussalam"
_CURRENCY = "BND"
_SOURCE_KEY = "bn_des_electricity_tariff"
_COICOP = "04.5.1"
_IDENT = ["source_key", "observation_date", "item_name", "unit"]
_PRICE_RE = re.compile(r"[\d,.]+")

_RESIDENTIAL_TIER_ROWS = [
    ("0001 kWh to 0600 kWh", "Residential electricity marginal tariff, 1-600 kWh monthly use"),
    ("0601 kWh to 2000 kWh", "Residential electricity marginal tariff, 601-2000 kWh monthly use"),
    ("2001 kWh to 4000 kWh", "Residential electricity marginal tariff, 2001-4000 kWh monthly use"),
    ("4001 kWh and Above", "Residential electricity marginal tariff, 4001+ kWh monthly use"),
]


def _parse_price(text: str) -> float | None:
    match = _PRICE_RE.search(text.replace(",", ""))
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


def _find_table_after_heading(soup: BeautifulSoup, heading_text: str) -> list[list[str]]:
    heading = soup.find(
        lambda tag: tag.name in {"h2", "h3"}
        and heading_text.lower() in tag.get_text(" ", strip=True).lower()
    )
    table = heading.find_next("table") if heading else None
    if table is None:
        return []
    rows: list[list[str]] = []
    for tr in table.select("tr"):
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"])]
        if cells:
            rows.append(cells)
    return rows


def _residential_rates(soup: BeautifulSoup, today: date, scrape_ts: str) -> list[dict]:
    rows = []
    table_rows = _find_table_after_heading(soup, "Tariff A")
    lookup = {row[0]: row[1] for row in table_rows if len(row) >= 2}
    for tier_label, item_name in _RESIDENTIAL_TIER_ROWS:
        price = _parse_price(lookup.get(tier_label, ""))
        if price is None:
            continue
        rows.append(
            _make_row(
                today=today,
                item_name=item_name,
                price=price,
                unit="BND/kWh",
                notes=f"DES Tariff A residential tier: {tier_label}",
                scrape_ts=scrape_ts,
            )
        )
    return rows


def _residential_bill_examples(soup: BeautifulSoup, today: date, scrape_ts: str) -> list[dict]:
    rows = []
    heading = soup.find(string=re.compile(r"Tariff\s+A\s+–\s+Residential", re.I))
    if heading:
        tables = heading.find_parent().find_all_next("table", limit=5)
    else:
        tables = soup.select("table")

    for table in tables:
        header = " ".join(c.get_text(" ", strip=True) for c in table.select("thead th"))
        if "kWh" not in header or "B$" not in header:
            continue
        for tr in table.select("tbody tr"):
            values = [c.get_text(" ", strip=True) for c in tr.find_all("td")]
            if len(values) < 2:
                continue
            kwh = _parse_price(values[0])
            bill = _parse_price(values[1])
            if kwh is None or bill is None:
                continue
            rows.append(
                _make_row(
                    today=today,
                    item_name=f"Residential electricity bill at {int(kwh)} kWh monthly use",
                    price=bill,
                    unit="monthly bill",
                    notes="DES Tariff A residential monthly bill example table",
                    scrape_ts=scrape_ts,
                )
            )
    return rows


def _commercial_rates(soup: BeautifulSoup, today: date, scrape_ts: str) -> list[dict]:
    rows = []
    table_rows = _find_table_after_heading(soup, "Tariff B")
    labels = {
        "The First 10 Units": "Commercial electricity marginal tariff, first 10 units",
        "The Second 100 Units": "Commercial electricity marginal tariff, second 100 units",
        "The Third 100 Units": "Commercial electricity marginal tariff, third 100 units",
        "Remaining Units": "Commercial electricity marginal tariff, remaining units",
    }
    for row in table_rows:
        if len(row) < 2:
            continue
        label = row[0]
        item_name = next((name for key, name in labels.items() if key in label), None)
        if not item_name:
            continue
        price = _parse_price(row[-1])
        if price is None:
            continue
        rows.append(
            _make_row(
                today=today,
                item_name=item_name,
                price=price,
                unit="BND/kWh",
                notes=f"DES Tariff B commercial formula row: {label}",
                scrape_ts=scrape_ts,
            )
        )
    return rows


def fetch_bn_des_electricity_tariff(cutoff: date) -> pd.DataFrame | None:
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
    resp = session.get(_URL, timeout=45)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    text = soup.get_text(" ", strip=True)
    if "Tariff A" not in text or "Tariff B" not in text:
        raise ValueError("DES electricity tariff page did not include expected tariff headings")

    scrape_ts = get_scrape_ts()
    rows = (
        _residential_rates(soup, today, scrape_ts)
        + _residential_bill_examples(soup, today, scrape_ts)
        + _commercial_rates(soup, today, scrape_ts)
    )
    return pd.DataFrame(rows) if rows else None
