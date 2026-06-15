from __future__ import annotations

import logging
from datetime import date, datetime, timezone

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_BASE_URL = "https://gateway.chotot.com/v1/public/ad-listing"
_COUNTRY = "Vietnam"
_CURRENCY = "VND"
_SOURCE_KEY = "vn_chotot"
_SOURCE_URL = "https://www.chotot.com"
_IDENT = ["source_key", "observation_date", "item_name", "subnational_area"]

_REGIONS = {
    13000: "Hồ Chí Minh",
    12000: "Hà Nội",
    48000: "Đà Nẵng",
}

_CATEGORIES = {
    2010: ("07.1.2", "Ô tô (used car)"),
    2020: ("07.1.4", "Xe máy (motorcycle)"),
}

_PAGE_SIZE = 20
_PAGES_PER_REGION = 5


def _parse_list_time(ts_ms: int | None) -> str | None:
    if not ts_ms:
        return None
    try:
        dt = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
        return dt.date().isoformat()
    except Exception:
        return None


def fetch_vn_chotot(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    rows: list[dict] = []

    for region_v2, region_name in _REGIONS.items():
        for cg, (coicop_code, category_label) in _CATEGORIES.items():
            for page in range(1, _PAGES_PER_REGION + 1):
                params = {
                    "region_v2": region_v2,
                    "cg": cg,
                    "page": page,
                    "limit": _PAGE_SIZE,
                }
                try:
                    resp = session.get(_BASE_URL, params=params, timeout=30)
                    resp.raise_for_status()
                    data = resp.json()
                except Exception as exc:
                    logger.warning(
                        "[%s] fetch failed region=%s cg=%s page=%s: %s",
                        _SOURCE_KEY,
                        region_v2,
                        cg,
                        page,
                        exc,
                    )
                    break

                ads = data.get("ads", [])
                if not ads:
                    break

                new_in_page = 0
                for ad in ads:
                    list_time_ms = ad.get("list_time") or ad.get("orig_list_time")
                    obs_date_str = _parse_list_time(list_time_ms)
                    if not obs_date_str:
                        continue
                    obs_date = date.fromisoformat(obs_date_str)
                    if obs_date <= cutoff:
                        continue
                    price = ad.get("price")
                    if not price or price <= 0:
                        continue
                    subject = (ad.get("subject") or "").strip()
                    if not subject:
                        continue
                    row = {
                        "observation_date": obs_date_str,
                        "period_kind": "snapshot",
                        "country": _COUNTRY,
                        "source_key": _SOURCE_KEY,
                        "coicop_code": coicop_code,
                        "item_name": subject,
                        "price_local": float(price),
                        "currency": _CURRENCY,
                        "unit": "unit",
                        "subnational_area": region_name,
                        "source_url": _SOURCE_URL,
                        "notes": f"Classified listing — {category_label}; ad_id={ad.get('ad_id')}",
                        "scrape_ts": get_scrape_ts(),
                        "observation_hash": None,
                    }
                    row["observation_hash"] = make_hash(row, _IDENT)
                    rows.append(row)
                    new_in_page += 1

                if new_in_page == 0:
                    break

    if not rows:
        logger.info("[%s] no new ads since cutoff %s", _SOURCE_KEY, cutoff)
        return None

    return pd.DataFrame(rows)
