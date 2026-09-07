"""Yichao China prescription-eyewear listing rows."""

from __future__ import annotations

import logging
import re
from datetime import date
from urllib.parse import urljoin

import pandas as pd
from bs4 import BeautifulSoup

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_URL = "https://www.yichao.cn/jsyjpkey/"
_COUNTRY = "China"
_SUBNATIONAL_AREA = "China online"
_SOURCE_KEY = "cn_yichao_eyewear"
_CURRENCY = "CNY"
_IDENT = ["source_key", "observation_date", "item_name", "source_url"]
_PRICE_RE = re.compile(r"￥\s*(?P<price>[0-9][0-9,.]*)")


def _clean(value: object) -> str:
    return " ".join(str(value or "").split())


def _parse_price(text: str) -> float | None:
    match = _PRICE_RE.search(text)
    if not match:
        return None
    try:
        price = float(match.group("price").replace(",", ""))
    except ValueError:
        return None
    return price if price > 0 else None


def fetch_cn_yichao_eyewear(cutoff: date) -> pd.DataFrame | None:
    obs_date = date.today()
    if obs_date <= cutoff:
        logger.info("[%s] latest date %s <= cutoff %s", _SOURCE_KEY, obs_date, cutoff)
        return None

    session = get_session()
    session.headers.update({"User-Agent": "Mozilla/5.0 price-research"})
    resp = session.get(_URL, timeout=45)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")

    ts = get_scrape_ts()
    rows: list[dict] = []
    seen: set[str] = set()
    for node in soup.select("li, div"):
        text = _clean(node.get_text(" ", strip=True))
        if "￥" not in text or len(text) > 180:
            continue
        price = _parse_price(text)
        anchor = node.find("a", href=True)
        if price is None or anchor is None:
            continue
        item_name = _clean(re.sub(r"^\d+\s*", "", text.split("￥", 1)[0]))
        source_url = urljoin(_URL, anchor["href"])
        if not item_name or source_url in seen or not source_url.endswith(".html"):
            continue
        row = {
            "observation_date": obs_date.isoformat(),
            "period_kind": "daily",
            "country": _COUNTRY,
            "subnational_area": _SUBNATIONAL_AREA,
            "source_key": _SOURCE_KEY,
            "coicop_code": None,
            "item_name": item_name,
            "price_local": price,
            "currency": _CURRENCY,
            "unit": "item",
            "source_url": source_url,
            "notes": "Yichao prescription-eyewear listing; displayed current price",
            "scrape_ts": ts,
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)
        seen.add(source_url)

    logger.info("[%s] parsed %d eyewear rows", _SOURCE_KEY, len(rows))
    return pd.DataFrame(rows) if rows else None
