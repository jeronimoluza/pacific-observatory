"""Beijing DRC residential electricity tariff table."""

from __future__ import annotations

import io
import logging
import re
from datetime import date

import pandas as pd
from bs4 import BeautifulSoup

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_URL = "https://fgw.beijing.gov.cn/bmcx/djcx/jzldj/202110/t20211025_2520169.htm"
_COUNTRY = "China"
_SUBNATIONAL_AREA = "Beijing"
_SOURCE_KEY = "cn_beijing_residential_electricity_tariff"
_CURRENCY = "CNY"
_COICOP = "04.5.1"
_IDENT = ["source_key", "observation_date", "item_name", "unit"]


def _pub_date(html: str) -> date:
    soup = BeautifulSoup(html, "lxml")
    meta = soup.find("meta", attrs={"name": "PubDate"})
    if meta and meta.get("content"):
        match = re.search(r"(\d{4})-(\d{2})-(\d{2})", meta["content"])
        if match:
            year, month, day = match.groups()
            return date(int(year), int(month), int(day))
    return date.today()


def _clean(value: object) -> str:
    return " ".join(str(value or "").replace("\xa0", " ").split())


def _parse_residential_rows(html: str) -> list[dict]:
    tables = pd.read_html(io.StringIO(html))
    if not tables:
        return []
    table = tables[0]
    rows: list[dict] = []
    for _, row in table.iloc[1:].iterrows():
        price = pd.to_numeric(row.iloc[4], errors="coerce")
        if pd.isna(price) or float(price) <= 0:
            continue
        user_group = _clean(row.iloc[0])
        tariff_class = _clean(row.iloc[1])
        block = _clean(row.iloc[2])
        voltage = _clean(row.iloc[3])
        item_name = (
            "Beijing residential electricity tariff: "
            f"{user_group}; {tariff_class}; {block}; {voltage}"
        )
        rows.append({"item_name": item_name, "price_local": float(price)})
    return rows


def fetch_cn_beijing_residential_electricity_tariff(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    session.headers.update({"User-Agent": "Mozilla/5.0 price-research"})
    resp = session.get(_URL, timeout=30)
    resp.raise_for_status()
    obs_date = _pub_date(resp.text)
    if obs_date <= cutoff:
        logger.info("[%s] latest date %s <= cutoff %s", _SOURCE_KEY, obs_date, cutoff)
        return None

    ts = get_scrape_ts()
    parsed = _parse_residential_rows(resp.text)
    rows: list[dict] = []
    for parsed_row in parsed:
        row = {
            "observation_date": obs_date.isoformat(),
            "period_kind": "snapshot",
            "country": _COUNTRY,
            "subnational_area": _SUBNATIONAL_AREA,
            "source_key": _SOURCE_KEY,
            "coicop_code": _COICOP,
            "item_name": parsed_row["item_name"],
            "price_local": parsed_row["price_local"],
            "currency": _CURRENCY,
            "unit": "CNY/kWh",
            "source_url": _URL,
            "notes": "Beijing Municipal DRC residential electricity tariff table",
            "scrape_ts": ts,
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)

    logger.info("[%s] parsed %d tariff rows", _SOURCE_KEY, len(rows))
    return pd.DataFrame(rows) if rows else None
