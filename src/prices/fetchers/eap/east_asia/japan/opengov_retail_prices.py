"""Japan (opengov.jp) Retail Price Survey — full monthly time series per item.

A re-publication of the MIC (Ministry of Internal Affairs and Communications)
Statistics Bureau retail price survey. The item index page
(/en/prices/retail-prices/) lists 541 item codes with English names; each
item's own page (/en/prices/retail-prices/<code>/) embeds a Chart.js
`data-chart-data` attribute on its trend chart holding the FULL monthly
series back to 2000-01 (313 points as of this pass) — not just the
year+latest-month snapshot the landing page shows. Re-verified live
2026-08-06: /en/prices/retail-prices/01001/ (Rice A) -> 200, chart data
labels 2000-01..2026-01, latest JPY 5,317. Survey area shown per item is
"Tokyo Special Wards" (the standard national-representative area used by
the MIC survey).

Scoped to item-code prefixes 01 (food, ~207 items) and 02 (alcohol, ~32
items) — the rest of the 541-item basket (03-09: rent, clothing, health,
education, personal care) is out of scope for this pipeline. COICOP is
deferred to the classifier (item_name = the site's own English item label,
e.g. "Rice A", "Tuna", "Daikon radish").

No auth, plain GET, one request per item page (~239 requests for the food+
alcohol scope). Polite fixed delay between requests.
"""

from __future__ import annotations

import html
import json
import logging
import re
import time
from datetime import date, datetime

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_INDEX_URL = "https://opengov.jp/en/prices/retail-prices/"
_ITEM_URL = "https://opengov.jp/en/prices/retail-prices/{code}/"
_COUNTRY = "Japan"
_CURRENCY = "JPY"
_SOURCE_KEY = "jp_opengov_retail_prices"
_IDENT = ["source_key", "observation_date", "item_name"]
_ITEM_LINK_RE = re.compile(
    r'href="/en/prices/retail-prices/([0-9]+)/"[^>]*>\s*([^<]+?)\s*</a>'
)
_CHART_DATA_RE = re.compile(r'data-chart-data="([^"]+)"')
_REQUEST_DELAY_S = 0.3
_SCOPE_PREFIXES = ("01", "02")


def _list_items(session) -> list[tuple[str, str]]:
    resp = session.get(_INDEX_URL, timeout=30)
    resp.raise_for_status()
    pairs = _ITEM_LINK_RE.findall(resp.text)
    seen: dict[str, str] = {}
    for code, name in pairs:
        if code.startswith(_SCOPE_PREFIXES):
            seen[code] = html.unescape(name).strip()
    return sorted(seen.items())


def _fetch_series(session, code: str) -> dict | None:
    url = _ITEM_URL.format(code=code)
    try:
        resp = session.get(url, timeout=20)
        resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] item %s fetch failed: %s", _SOURCE_KEY, code, exc)
        return None
    m = _CHART_DATA_RE.search(resp.text)
    if not m:
        return None
    try:
        data = json.loads(html.unescape(m.group(1)))
    except json.JSONDecodeError:
        return None
    labels = data.get("labels") or []
    datasets = data.get("datasets") or []
    if not labels or not datasets:
        return None
    values = datasets[0].get("data") or []
    return {"url": url, "labels": labels, "values": values}


def fetch_jp_opengov_retail_prices(cutoff: date) -> pd.DataFrame | None:
    session = get_session()
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Chrome/120 Safari/537.36"
        }
    )
    items = _list_items(session)
    logger.info(
        "[%s] %d items in scope (prefixes %s)", _SOURCE_KEY, len(items), _SCOPE_PREFIXES
    )

    ts = get_scrape_ts()
    rows: list[dict] = []
    seen_hashes: set = set()
    for code, name in items:
        series = _fetch_series(session, code)
        time.sleep(_REQUEST_DELAY_S)
        if series is None:
            continue
        for label, value in zip(series["labels"], series["values"]):
            if value is None:
                continue
            try:
                obs_date = datetime.strptime(label, "%Y-%m").date().replace(day=1)
            except ValueError:
                continue
            if obs_date <= cutoff:
                continue
            row = {
                "observation_date": obs_date.isoformat(),
                "period_kind": "monthly",
                "country": _COUNTRY,
                "source_key": _SOURCE_KEY,
                "item_name": name,
                "price_local": round(float(value), 2),
                "currency": _CURRENCY,
                "unit": None,
                "source_url": series["url"],
                "notes": f"MIC retail price survey; item_code={code}; survey_area=Tokyo Special Wards",
                "scrape_ts": ts,
                "observation_hash": None,
            }
            row["observation_hash"] = make_hash(row, _IDENT)
            if row["observation_hash"] in seen_hashes:
                continue
            seen_hashes.add(row["observation_hash"])
            rows.append(row)
        logger.info(
            "[%s] item=%s (%s) rows so far=%d", _SOURCE_KEY, code, name, len(rows)
        )

    logger.info("[%s] %d rows total (cutoff=%s)", _SOURCE_KEY, len(rows), cutoff)
    return pd.DataFrame(rows) if rows else None
