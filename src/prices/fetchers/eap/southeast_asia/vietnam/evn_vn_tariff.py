from __future__ import annotations

import logging
import re
from datetime import date

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_NEWS_URL = "https://www.evn.com.vn/vi-VN/news-l/Gia-dien-60-28"
_COUNTRY = "Vietnam"
_CURRENCY = "VND"
_SOURCE_KEY = "vn_evn_tariff"
_SOURCE_URL = "https://www.evn.com.vn/vi-VN/news-l/Gia-dien-60-28"
_UNIT = "kWh"
_COICOP = "04.5.1"
_IDENT = ["source_key", "observation_date", "item_name"]

_KNOWN_DECISIONS: dict[str, list[dict]] = {
    "2025-05-09": [
        {"label": "Bậc 1 (0–50 kWh)", "price_local": 1893},
        {"label": "Bậc 2 (51–100 kWh)", "price_local": 1956},
        {"label": "Bậc 3 (101–200 kWh)", "price_local": 2271},
        {"label": "Bậc 4 (201–300 kWh)", "price_local": 2860},
        {"label": "Bậc 5 (301–400 kWh)", "price_local": 3197},
        {"label": "Bậc 6 (trên 400 kWh)", "price_local": 3587},
    ],
}

_DECISION_RE = re.compile(
    r"Biểu giá bán lẻ điện.*?Quyết định.*?(\d{1,4}/QĐ-BCT).*?ngày.*?(\d{1,2})/(\d{1,2})/(\d{4})",
    re.IGNORECASE | re.DOTALL,
)


def _latest_decision_date(html: str) -> str | None:
    m = _DECISION_RE.search(html)
    if not m:
        return None
    try:
        _, day, month, year = m.groups()
        return f"{year}-{int(month):02d}-{int(day):02d}"
    except Exception:
        return None


def fetch_vn_evn_tariff(cutoff: date) -> pd.DataFrame | None:
    session = get_session()

    try:
        resp = session.get(_NEWS_URL, timeout=30)
        resp.raise_for_status()
        html = resp.text
    except Exception as exc:
        logger.warning(
            "[%s] news page fetch failed: %s — using last known decision",
            _SOURCE_KEY,
            exc,
        )
        html = ""

    detected_date = _latest_decision_date(html)
    if detected_date and detected_date not in _KNOWN_DECISIONS:
        logger.warning(
            "[%s] EVN news mentions decision dated %s which is NOT in _KNOWN_DECISIONS. "
            "Update _KNOWN_DECISIONS with the new tariff schedule.",
            _SOURCE_KEY,
            detected_date,
        )

    rows: list[dict] = []
    for decision_date_str, tiers in _KNOWN_DECISIONS.items():
        obs_date = date.fromisoformat(decision_date_str)
        if obs_date <= cutoff:
            continue
        for tier in tiers:
            row = {
                "observation_date": obs_date.isoformat(),
                "period_kind": "snapshot",
                "country": _COUNTRY,
                "source_key": _SOURCE_KEY,
                "coicop_code": _COICOP,
                "item_name": f"Giá điện sinh hoạt {tier['label']}",
                "price_local": float(tier["price_local"]),
                "currency": _CURRENCY,
                "unit": _UNIT,
                "source_url": _SOURCE_URL,
                "notes": "Decision 1279/QĐ-BCT dated 2025-05-09; household retail tier rate",
                "scrape_ts": get_scrape_ts(),
                "observation_hash": None,
            }
            row["observation_hash"] = make_hash(row, _IDENT)
            rows.append(row)

    if not rows:
        logger.info(
            "[%s] all decision dates ≤ cutoff %s — nothing new", _SOURCE_KEY, cutoff
        )
        return None

    return pd.DataFrame(rows)
