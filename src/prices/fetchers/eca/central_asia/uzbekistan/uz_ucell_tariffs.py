"""Ucell (Uzbekistan mobile operator) — consumer tariff plans, JSON-LD per plan page."""

import json
import logging
import re
import time
from datetime import date, datetime, timezone

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_SITEMAP_URL = "https://ucell.uz/sitemap-tariffs.xml"
_COUNTRY = "Uzbekistan"
_CURRENCY = "UZS"
_SOURCE_KEY = "uz_ucell_tariffs"
_COICOP = "08.3.0"  # Telephone and telefax services

_PLAN_PATH_RE = re.compile(r"^https://ucell\.uz/ru/tariffs/[a-z0-9_]+$")
_EXCLUDE = {
    "https://ucell.uz/ru/tariffs",
    "https://ucell.uz/ru/tariffs/tariffs_archive",
    "https://ucell.uz/ru/tariffs/tariffs_archive-detail",
}
_LD_JSON_RE = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S)

_IDENT = ["source_key", "observation_date", "item_name"]


def _plan_urls(session) -> list[str]:
    resp = session.get(_SITEMAP_URL, timeout=30)
    resp.raise_for_status()
    urls = re.findall(r"<loc>([^<]+)</loc>", resp.text)
    return sorted(
        {u for u in urls if _PLAN_PATH_RE.match(u) and u not in _EXCLUDE}
    )


def _parse_plan(html: str) -> dict | None:
    for m in _LD_JSON_RE.finditer(html):
        try:
            data = json.loads(m.group(1))
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and data.get("@type") == "Product":
            offers = data.get("offers") or {}
            price = offers.get("price")
            if price is None:
                continue
            return {
                "name": data.get("name"),
                "price": float(price),
                "currency": offers.get("priceCurrency", _CURRENCY),
            }
    return None


def fetch_uz_ucell_tariffs(cutoff: date) -> pd.DataFrame | None:
    today = datetime.now(timezone.utc).date()
    if today <= cutoff:
        return None

    session = get_session()
    urls = _plan_urls(session)

    rows = []
    for url in urls:
        try:
            resp = session.get(url, timeout=30)
            resp.raise_for_status()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Ucell tariff page fetch failed for %s: %s", url, exc)
            continue

        plan = _parse_plan(resp.text)
        if plan is None or not plan["name"]:
            logger.warning("No JSON-LD Product found on %s — dropping", url)
            continue
        if plan["currency"] != _CURRENCY:
            logger.warning(
                "Ucell plan %r priced in %s, expected %s — dropping",
                plan["name"], plan["currency"], _CURRENCY,
            )
            continue

        row = {
            "observation_date": today.isoformat(),
            "period_kind": "snapshot",
            "country": _COUNTRY,
            "source_key": _SOURCE_KEY,
            "item_name": plan["name"],
            "price_local": plan["price"],
            "currency": _CURRENCY,
            "unit": "month",
            "coicop_code": _COICOP,
            "source_url": url,
            "scrape_ts": get_scrape_ts(),
            "observation_hash": None,
        }
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)
        time.sleep(0.3)

    return pd.DataFrame(rows) if rows else None
