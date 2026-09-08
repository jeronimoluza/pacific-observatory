"""National University of Mongolia (NUM) — undergraduate/graduate tuition fees.

Discovery lead "num.edu.mn". The public fees-and-funding page is plain
server-rendered WordPress HTML with 5 well-formed <table id="myTable">
elements (no JS, no anti-bot) at:
  https://www.num.edu.mn/admissions/undergraduate/fees-and-funding/course-fees/

First education-division (COICOP 10) source for Mongolia. Three of the five
tables are clean, homogeneous, per-row records and are parsed here:
  - table[0]: undergraduate per-credit-hour fee (MNT) by school, split into
    general-foundation vs major-foundation course fee.
  - table[1]: master's per-credit-hour fee (MNT) by school.
  - table[4]: hourly rate range (MNT) for non-credit language courses by
    level (beginner/intermediate/advanced).
The remaining two tables (foreign-student annual fee schedule, a second
master's/PhD schedule) use merged/rowspan cells for a nested category
structure that a flat table walk mis-splits, and are left for a future pass.
"""

from __future__ import annotations

import logging
import re
from datetime import date

import pandas as pd
from bs4 import BeautifulSoup

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_URL = "https://www.num.edu.mn/admissions/undergraduate/fees-and-funding/course-fees/"
_COUNTRY = "Mongolia"
_CURRENCY = "MNT"
_SOURCE_KEY = "mn_num_tuition_fees"
_COICOP_CODE = "10.4.0.0"
_IDENT = ["source_key", "observation_date", "item_name"]

_NUM_RE = re.compile(r"[\d,]+")


def _row_base(obs_date: date, item_name: str, price_local: float, notes: str) -> dict:
    row = {
        "observation_date": obs_date.isoformat(),
        "period_kind": "snapshot",
        "country": _COUNTRY,
        "source_key": _SOURCE_KEY,
        "coicop_code": _COICOP_CODE,
        "item_name": item_name,
        "price_local": price_local,
        "currency": _CURRENCY,
        "unit": "credit-hour",
        "source_url": _URL,
        "notes": notes,
        "scrape_ts": get_scrape_ts(),
        "observation_hash": None,
    }
    row["observation_hash"] = make_hash(row, _IDENT)
    return row


def _parse_undergrad_table(table, obs_date: date) -> list[dict]:
    rows = []
    for tr in table.find("tbody").find_all("tr"):
        cells = [td.get_text(strip=True) for td in tr.find_all("td")]
        if len(cells) < 4:
            continue
        _, school, general_fee, major_fee = cells[:4]
        for label, fee in (("general-foundation", general_fee), ("major-foundation", major_fee)):
            m = _NUM_RE.search(fee)
            if not m or not school:
                continue
            price = float(m.group(0).replace(",", ""))
            item_name = f"NUM undergraduate tuition, {school}, {label} course, per credit hour"
            rows.append(_row_base(obs_date, item_name, price, f"undergraduate / {label}"))
    return rows


def _parse_masters_table(table, obs_date: date) -> list[dict]:
    rows = []
    for tr in table.find("tbody").find_all("tr"):
        cells = [td.get_text(strip=True) for td in tr.find_all("td")]
        if len(cells) < 5:
            continue
        _, school, level, course_type, fee = cells[:5]
        m = _NUM_RE.search(fee)
        if not m or not school:
            continue
        price = float(m.group(0).replace(",", ""))
        item_name = f"NUM {level} tuition, {school}, per credit hour"
        rows.append(_row_base(obs_date, item_name, price, course_type))
    return rows


def _parse_language_table(table, obs_date: date) -> list[dict]:
    rows = []
    for tr in table.find("tbody").find_all("tr"):
        cells = [td.get_text(strip=True) for td in tr.find_all("td")]
        if len(cells) < 3:
            continue
        _, level, fee_range = cells[:3]
        nums = [float(n.replace(",", "")) for n in _NUM_RE.findall(fee_range)]
        if not nums or not level:
            continue
        price = sum(nums) / len(nums)  # midpoint of the published range
        item_name = f"NUM non-credit language course, {level} level, per academic hour"
        rows.append(_row_base(obs_date, item_name, price, f"published range: {fee_range}"))
    return rows


def fetch_mn_num_tuition_fees(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    obs_date = date.today()
    if obs_date <= cutoff:
        return None

    resp = session.get(_URL, timeout=30)
    if resp.status_code != 200:
        logger.warning("[%s] HTTP %d for %s", _SOURCE_KEY, resp.status_code, _URL)
        return None

    soup = BeautifulSoup(resp.text, "html.parser")
    tables = soup.find_all("table", id="myTable")
    if len(tables) < 5:
        logger.warning("[%s] expected 5 tables, found %d", _SOURCE_KEY, len(tables))

    rows: list[dict] = []
    if len(tables) > 0:
        rows.extend(_parse_undergrad_table(tables[0], obs_date))
    if len(tables) > 1:
        rows.extend(_parse_masters_table(tables[1], obs_date))
    if len(tables) > 4:
        rows.extend(_parse_language_table(tables[4], obs_date))

    return pd.DataFrame(rows) if rows else None
