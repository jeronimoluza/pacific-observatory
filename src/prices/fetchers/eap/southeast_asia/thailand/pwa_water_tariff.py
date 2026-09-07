"""Provincial Waterworks Authority Thailand household water tariffs."""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from io import StringIO

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_URL = "https://www.pwa.co.th/contents/service/table-price"
_COUNTRY = "Thailand"
_CURRENCY = "THB"
_SOURCE_KEY = "th_pwa_water_tariff"
_COICOP = "04.4.1"
_UNIT = "m3"
_IDENT = ["source_key", "observation_date", "item_name"]

_GROUPS = [
    (
        "PWA tariff table 1",
        "private-investment service areas",
        "ตารางหมายเลข 1 อัตราค่าน้ำประปาพื้นทีเอกชนร่วมลงทุน",
    ),
    (
        "PWA tariff table 2",
        "Phuket, Ko Samui, and Ko Pha-ngan branches",
        "ตารางหมายเลข 2 อัตราค่าน้ำประปาพื้นที่ กปภ.สาขาภูเก็ต เกาะสมุย และเกาะพะงัน",
    ),
    (
        "PWA tariff table 3",
        "other PWA branches nationwide",
        "ตารางหมายเลข 3 อัตราค่าน้ำประปาพื้นที่ กปภ.สาขาอื่น (ทั่วประเทศ)",
    ),
]


def _clean(value: object) -> str:
    return " ".join(str(value).replace("\xa0", " ").split())


def fetch_th_pwa_water_tariff(cutoff: date) -> pd.DataFrame | None:
    obs_date = datetime.now(timezone.utc).date()
    if obs_date <= cutoff:
        return None

    session = get_session()
    resp = session.get(_URL, timeout=45)
    resp.raise_for_status()
    resp.encoding = "utf-8"

    tables = pd.read_html(StringIO(resp.text))
    if len(tables) < len(_GROUPS):
        logger.warning(
            "[%s] expected %d water tariff tables, found %d",
            _SOURCE_KEY,
            len(_GROUPS),
            len(tables),
        )

    rows: list[dict] = []
    ts = get_scrape_ts()
    for table_idx, df in enumerate(tables[: len(_GROUPS)]):
        table_label, area_label, thai_label = _GROUPS[table_idx]
        for _, src_row in df.iterrows():
            block = _clean(src_row.iloc[0])
            raw_price = src_row.iloc[2] if len(src_row) > 2 else None
            if not block or block.lower() == "nan" or pd.isna(raw_price):
                continue
            try:
                price = float(raw_price)
            except (TypeError, ValueError):
                continue

            row = {
                "observation_date": obs_date.isoformat(),
                "period_kind": "snapshot",
                "country": _COUNTRY,
                "subnational_area": area_label,
                "source_key": _SOURCE_KEY,
                "coicop_code": _COICOP,
                "item_name": f"{table_label}, residential water tariff, {block}",
                "price_local": round(price, 4),
                "currency": _CURRENCY,
                "unit": _UNIT,
                "source_url": _URL,
                "notes": f"residential rate per cubic metre; {thai_label}"[:500],
                "scrape_ts": ts,
                "observation_hash": None,
            }
            row["observation_hash"] = make_hash(row, _IDENT)
            rows.append(row)

    logger.info("[%s] %d rows", _SOURCE_KEY, len(rows))
    return pd.DataFrame(rows) if rows else None
