"""Our Telekom Solomon Islands — mobile and internet data plan tariffs.

Scrapes the SSR HTML plan pages at ourtelekom.com.sb. The site uses a custom
CMS with prices in structured HTML tables (for internet plans) and
pricing-card grids (for mobile GIGA plans). Both sections are server-rendered
with no JS requirement.

Two analytical outputs are folded into one fetcher:
  - Mobile prepaid data plans (COICOP 08.1.0 — telephone and fax services)
  - Fixed / prepaid broadband data plans (COICOP 08.1.0)

COICOP 08.1.0 covers all telephone and internet access services at 4-digit
resolution; both mobile and fixed data plans map there.

Source URL: https://www.ourtelekom.com.sb/personal/personal-mobile/ (mobile)
            https://www.ourtelekom.com.sb/personal/personal-internet/ (internet)
"""

from __future__ import annotations

import logging
import re
from datetime import date

import pandas as pd
from bs4 import BeautifulSoup

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_MOBILE_URL = "https://www.ourtelekom.com.sb/personal/personal-mobile/"
_INTERNET_URL = "https://www.ourtelekom.com.sb/personal/personal-internet/"
_COUNTRY = "Solomon Islands"
_CURRENCY = "SBD"
_SOURCE_KEY = "sb_our_telekom_plans"
_COICOP_CODE = "08.1.0"
_IDENT = ["source_key", "observation_date", "item_name"]

_PRICE_RE = re.compile(r"\$\s*([\d,]+(?:\.\d+)?)")


def _extract_mobile_giga_plans(
    soup: BeautifulSoup, obs_date: date, source_url: str
) -> list[dict]:
    rows: list[dict] = []
    pricing_grids = soup.find_all("div", class_=re.compile(r"pricing-table-grid"))
    for grid in pricing_grids:
        title_el = grid.find_previous("h2", class_=re.compile(r"pricing-table-title"))
        plan_series = title_el.get_text(strip=True) if title_el else "Mobile Plan"
        data_amounts = [
            el.get_text(strip=True)
            for el in grid.find_all("span")
            if re.search(r"\d+\s*(?:GB|MB)", el.get_text())
        ]
        plan_cards = grid.find_all("div", class_=re.compile(r"pti-prices", flags=re.I))
        for i, card in enumerate(plan_cards):
            price_val_el = card.find("span", class_=re.compile(r"pti-price-value"))
            if not price_val_el:
                continue
            price_text = price_val_el.get_text(strip=True)
            m = _PRICE_RE.search(price_text)
            if not m:
                continue
            price_local = float(m.group(1).replace(",", ""))
            data_label = data_amounts[i] if i < len(data_amounts) else "unknown"
            item_name = f"Our Telekom {plan_series}, {data_label}, prepaid mobile data"
            row = {
                "observation_date": obs_date.isoformat(),
                "period_kind": "snapshot",
                "country": _COUNTRY,
                "source_key": _SOURCE_KEY,
                "coicop_code": _COICOP_CODE,
                "item_name": item_name,
                "price_local": price_local,
                "currency": _CURRENCY,
                "unit": "plan",
                "source_url": source_url,
                "notes": plan_series,
                "scrape_ts": get_scrape_ts(),
                "observation_hash": None,
            }
            row["observation_hash"] = make_hash(row, _IDENT)
            rows.append(row)
    return rows


def _extract_internet_table_plans(
    soup: BeautifulSoup, obs_date: date, source_url: str
) -> list[dict]:
    rows: list[dict] = []
    tables = soup.find_all("table")
    for table in tables:
        header_row = table.find("tr")
        if not header_row:
            continue
        headers = [
            th.get_text(" ", strip=True) for th in header_row.find_all(["th", "td"])
        ]
        price_idx = next(
            (i for i, h in enumerate(headers) if h.strip().lower() == "price"), None
        )
        plan_idx = next((i for i, h in enumerate(headers) if "plan" in h.lower()), None)
        if price_idx is None or plan_idx is None:
            continue
        for tr in table.find_all("tr")[1:]:
            cells = tr.find_all(["td", "th"])
            if len(cells) <= max(price_idx, plan_idx):
                continue
            plan_cell = cells[plan_idx].get_text(" ", strip=True)
            price_cell = cells[price_idx].get_text(strip=True)
            m = _PRICE_RE.search(price_cell)
            if not m or not plan_cell:
                continue
            price_local = float(m.group(1).replace(",", ""))
            item_name = f"Our Telekom internet plan, {plan_cell}"
            row = {
                "observation_date": obs_date.isoformat(),
                "period_kind": "snapshot",
                "country": _COUNTRY,
                "source_key": _SOURCE_KEY,
                "coicop_code": _COICOP_CODE,
                "item_name": item_name,
                "price_local": price_local,
                "currency": _CURRENCY,
                "unit": "plan",
                "source_url": source_url,
                "notes": "internet data plan",
                "scrape_ts": get_scrape_ts(),
                "observation_hash": None,
            }
            row["observation_hash"] = make_hash(row, _IDENT)
            rows.append(row)
    return rows


def fetch_sb_our_telekom_plans(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    obs_date = date.today()
    if obs_date <= cutoff:
        return None

    rows: list[dict] = []

    for url, extractor in [
        (_MOBILE_URL, _extract_mobile_giga_plans),
        (_INTERNET_URL, _extract_internet_table_plans),
    ]:
        resp = session.get(url, timeout=30)
        if resp.status_code != 200:
            logger.warning("[%s] HTTP %d for %s", _SOURCE_KEY, resp.status_code, url)
            continue
        soup = BeautifulSoup(resp.text, "html.parser")
        batch = extractor(soup, obs_date, url)
        if not batch:
            logger.warning("[%s] No plans parsed from %s", _SOURCE_KEY, url)
        rows.extend(batch)

    return pd.DataFrame(rows) if rows else None
