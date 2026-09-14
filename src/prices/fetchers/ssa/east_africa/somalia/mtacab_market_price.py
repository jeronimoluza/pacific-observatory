"""Collect M-TACAB Somalia's dated crop-market price records."""
from __future__ import annotations

import logging
import re
from datetime import date

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash


logger = logging.getLogger(__name__)
_LANDING_URL = "https://www.mtacab.so/market-price/"
_SOURCE_KEY = "somalia_mtacab_so"
_PAGE_SIZE = 1000
_MAX_PAGES = 20
_IDENT = ["source_key", "observation_date", "item_name", "market", "unit"]
_INDEX_RE = re.compile(r'src="(?P<path>/assets/index-[^"]+\.js)"')
_URL_RE = re.compile(r"VITE_SUPABASE_URL:`(?P<url>https://[^`]+)`")
_KEY_RE = re.compile(r"VITE_SUPABASE_PUBLISHABLE_KEY:`(?P<key>[^`]+)`")


def _api_config(session):
    try:
        page = session.get(_LANDING_URL, timeout=30)
        page.raise_for_status()
        asset = _INDEX_RE.search(page.text)
        if not asset:
            return None
        bundle = session.get(f"https://www.mtacab.so{asset.group('path')}", timeout=30)
        bundle.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] public app discovery failed: %s", _SOURCE_KEY, exc)
        return None
    url = _URL_RE.search(bundle.text)
    key = _KEY_RE.search(bundle.text)
    return (url.group("url"), key.group("key")) if url and key else None


def _records(session, api_url, api_key):
    params = {
        "select": "id,date,crop,variety,market,unit,price,note",
        "status": "eq.priced",
        "order": "date.desc,id.desc",
    }
    records = []
    for page in range(_MAX_PAGES):
        start = page * _PAGE_SIZE
        headers = {
            "apikey": api_key,
            "Authorization": f"Bearer {api_key}",
            "Range": f"{start}-{start + _PAGE_SIZE - 1}",
        }
        try:
            response = session.get(
                f"{api_url}/rest/v1/price_records",
                params=params,
                headers=headers,
                timeout=30,
            )
            response.raise_for_status()
            batch = response.json()
        except Exception as exc:  # noqa: BLE001
            logger.warning("[%s] API page %d failed: %s", _SOURCE_KEY, page + 1, exc)
            break
        if not isinstance(batch, list) or not batch:
            break
        records.extend(batch)
        if len(batch) < _PAGE_SIZE:
            break
    return records


def fetch_somalia_mtacab_so(cutoff: date):
    session = get_session()
    config = _api_config(session)
    if not config:
        return None

    rows = []
    scrape_ts = get_scrape_ts()
    for record in _records(session, *config):
        try:
            observation_date = date.fromisoformat(str(record["date"]))
            price = float(record["price"])
        except (KeyError, TypeError, ValueError):
            continue
        crop = str(record.get("crop") or "").strip()
        variety = str(record.get("variety") or "").strip()
        market = str(record.get("market") or "").strip()
        unit = str(record.get("unit") or "").strip()
        if observation_date <= cutoff or not 0 < price < 1_000_000 or not all((crop, market, unit)):
            continue
        row = {
            "observation_date": observation_date.isoformat(),
            "period_kind": "snapshot",
            "country": "Somalia",
            "source_key": _SOURCE_KEY,
            "item_name": " - ".join(part for part in (crop, variety) if part),
            "price_local": price,
            "currency": unit.partition("/")[0].strip(),
            "unit": unit,
            "market": market,
            "variety": variety or None,
            "source_url": _LANDING_URL,
            "notes": str(record.get("note") or "").strip() or None,
            "scrape_ts": scrape_ts,
            "observation_hash": None,
        }
        if not row["currency"]:
            continue
        row["observation_hash"] = make_hash(row, _IDENT)
        rows.append(row)
    logger.info("[%s] produced %d post-cutoff rows", _SOURCE_KEY, len(rows))
    return pd.DataFrame(rows) if rows else None
