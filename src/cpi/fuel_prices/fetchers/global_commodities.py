"""Global and EAP commodity oil/gasoline price fetchers.

Source:
  1. Investing.com internal API (daily, best-effort — Cloudflare may block)
"""

import json
import time
from datetime import date
from typing import Optional

import pandas as pd

from ..utils import get_session, make_hash, make_template

SOURCE_META = [
    {
        "fetcher_fn": "fetch_investing_commodities",
        "country": "Global / EAP",
        "source_name": "Investing.com Commodity Prices",
        "url": "https://www.investing.com/commodities/",
        "description": "Commercial platform (Investing.com). Internal undocumented REST API to retrieve daily historical commodity prices. Not an official public API.",
        "extraction_method": ["Web scraping", "REST API"],
        "products": [
            "WTI Crude Oil",
            "Brent Crude Oil",
            "Gasoline RBOB",
            "Dubai Crude Oil",
            "Singapore Gasoil",
            "Abu Dhabi Murban Crude Oil F (MRBNc1)",
        ],
        "source_keys": ["global_investing_daily"],
        "publishes_on": "Daily",
        "notes": "WARNING: May be blocked by Cloudflare (403). Best-effort only.",
    },
]

# ---------------------------------------------------------------------------
# Shared commodity definitions
# ---------------------------------------------------------------------------

_GLOBAL = dict(country="Global", wb_iso3="WLD", subnational_area="Global")
_EAP = dict(country="EAP", wb_iso3="EAP", subnational_area="East Asia & Pacific")

_INVESTING_SLUGS: list[dict] = [
    dict(
        slug="crude-oil",
        fuel_product="WTI Crude Oil",
        fuel_family="crude_oil",
        quality_group="wti",
        unit="bbl",
        currency="USD",
        **_GLOBAL,
    ),
    dict(
        slug="brent-oil",
        fuel_product="Brent Crude Oil",
        fuel_family="crude_oil",
        quality_group="brent",
        unit="bbl",
        currency="USD",
        **_GLOBAL,
    ),
    dict(
        slug="gasoline-rbob",
        fuel_product="Gasoline RBOB",
        fuel_family="gasoline",
        quality_group="regular",
        unit="gal",
        currency="USD",
        **_GLOBAL,
    ),
    dict(
        slug="dubai-crude-oil-platts-futures",
        fuel_product="Dubai Crude Oil (Platts)",
        fuel_family="crude_oil",
        quality_group="dubai",
        unit="bbl",
        currency="USD",
        **_EAP,
    ),
    dict(
        slug="nymex-singapore-gasoil-platts-c1-futures",
        fuel_product="Singapore Gasoil (Platts)",
        fuel_family="gasoil",
        quality_group="regular",
        unit="bbl",
        currency="USD",
        **_EAP,
    ),
    dict(
        slug="abu-dhabi-murban-crude-oil-futures",
        fuel_product="Abu Dhabi Murban Crude Oil F (MRBNc1)",
        fuel_family="crude_oil",
        quality_group="murban",
        unit="bbl",
        currency="USD",
        **_EAP,
    ),
]

# ---------------------------------------------------------------------------
# Source 1: investing.com — scrape __NEXT_DATA__ from historical-data pages
# ---------------------------------------------------------------------------

_INVESTING_BASE = "https://www.investing.com/commodities/"
_INVESTING_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def _extract_next_data(html: str) -> Optional[dict]:
    """Extract __NEXT_DATA__ JSON from an investing.com HTML page."""
    start = html.find('<script id="__NEXT_DATA__"')
    if start == -1:
        return None
    start = html.find(">", start) + 1
    end = html.find("</script>", start)
    if end == -1:
        return None
    try:
        return json.loads(html[start:end])
    except (json.JSONDecodeError, ValueError):
        return None


def _find_historical_rows(obj: object, depth: int = 0) -> list[dict]:
    """Recursively find the historical data array in __NEXT_DATA__ or API response."""
    if depth > 15:
        return []
    if isinstance(obj, dict):
        if "data" in obj and isinstance(obj["data"], list):
            items = obj["data"]
            if items and isinstance(items[0], dict) and "rowDate" in items[0]:
                return items
        for v in obj.values():
            result = _find_historical_rows(v, depth + 1)
            if result:
                return result
    elif isinstance(obj, list):
        for item in obj:
            result = _find_historical_rows(item, depth + 1)
            if result:
                return result
    return []


def _parse_price_rows(
    rows_data: list[dict], cutoff: Optional[date] = None
) -> list[dict]:
    """Convert raw investing.com row dicts into ``{obs_date, price}`` entries.

    When ``cutoff`` is None (the default), all rows are returned and deduplication
    is handled downstream by ``merge_new_rows`` via ``observation_hash``.  Pass a
    cutoff only when you explicitly want to filter (e.g. bootstrap scripts).
    """
    results = []
    for entry in rows_data:
        try:
            raw_date = entry.get("rowDateTimestamp") or entry.get("rowDate")
            obs_date = pd.to_datetime(raw_date).date()
        except Exception:
            continue
        if cutoff is not None and obs_date <= cutoff:
            continue
        price_raw = entry.get("last_closeRaw") or entry.get("last_close")
        try:
            price = float(price_raw)
        except (TypeError, ValueError):
            continue
        if price <= 0:
            continue
        results.append({"obs_date": obs_date, "price": price})
    return results


_FETCH_RETRIES = 3
_FETCH_RETRY_SLEEP = 5  # seconds between retries


def _fetch_investing_series(slug: str, session) -> list[dict]:
    """Fetch the ~20 most-recent trading days for one slug via HTML __NEXT_DATA__.

    Retries up to ``_FETCH_RETRIES`` times on transient failures (non-200, network
    errors, missing __NEXT_DATA__).  Returns all rows found without cutoff filtering
    — deduplication is handled downstream by ``merge_new_rows``.
    """
    url = f"{_INVESTING_BASE}{slug}-historical-data"
    for attempt in range(1, _FETCH_RETRIES + 1):
        try:
            resp = session.get(url, timeout=30)
        except Exception as e:
            print(f"  [investing] Fetch error for {slug} (attempt {attempt}): {e}")
            if attempt < _FETCH_RETRIES:
                time.sleep(_FETCH_RETRY_SLEEP)
            continue

        if resp.status_code != 200:
            print(
                f"  [investing] HTTP {resp.status_code} for {slug} (attempt {attempt})"
            )
            if attempt < _FETCH_RETRIES:
                time.sleep(_FETCH_RETRY_SLEEP)
            continue

        data = _extract_next_data(resp.text)
        if data is None:
            print(
                f"  [investing] __NEXT_DATA__ not found/parseable for {slug} (attempt {attempt})"
            )
            if attempt < _FETCH_RETRIES:
                time.sleep(_FETCH_RETRY_SLEEP)
            continue

        rows_data = _find_historical_rows(data)
        if not rows_data:
            print(
                f"  [investing] No historical rows in page for {slug} (attempt {attempt})"
            )
            if attempt < _FETCH_RETRIES:
                time.sleep(_FETCH_RETRY_SLEEP)
            continue

        return _parse_price_rows(rows_data)

    print(f"  [investing] All {_FETCH_RETRIES} attempts failed for {slug}")
    return []


def fetch_investing_commodities(cutoff: date) -> pd.DataFrame:
    """Fetch daily global/EAP commodity prices from investing.com (best-effort).

    ``cutoff`` is accepted for pipeline compatibility but is not used to filter
    rows — all ~20 rows from the HTML page are returned and deduplication is
    handled downstream by ``merge_new_rows`` via ``observation_hash``.
    """
    print("  [investing] Fetching investing.com commodity data...")

    session = get_session()
    session.headers.update(_INVESTING_HEADERS)

    all_rows = []
    for spec in _INVESTING_SLUGS:
        slug = spec["slug"]
        print(f"  [investing] → {slug}")

        raw_rows = _fetch_investing_series(slug, session)
        if not raw_rows:
            print(f"  [investing]   0 rows for {slug}")
            continue

        tmpl = make_template(
            country=spec["country"],
            wb_iso3=spec["wb_iso3"],
            subnational_area=spec["subnational_area"],
            fuel_family=spec["fuel_family"],
            fuel_product=spec["fuel_product"],
            quality_group=spec["quality_group"],
            currency=spec["currency"],
            unit=spec["unit"],
            source_key="global_investing_daily",
            source_name="Investing.com Commodity Futures",
            source_url=f"{_INVESTING_BASE}{slug}-historical-data",
            source_type="market",
            publication_frequency="daily",
            observation_method="market",
            tax_status="pre_tax",
        )

        for entry in raw_rows:
            obs_date = entry["obs_date"]
            r = tmpl.copy()
            r.update(
                {
                    "price_local": round(entry["price"], 2),
                    "effective_from": str(obs_date),
                    "effective_to": str(obs_date),
                    "observation_date": str(obs_date),
                    "source_url": f"{_INVESTING_BASE}{slug}-historical-data",
                }
            )
            r["observation_hash"] = make_hash(r)
            all_rows.append(r)

        print(f"  [investing]   {len(raw_rows)} rows for {slug}")

    print(f"  [investing] Total: {len(all_rows)} rows")
    return pd.DataFrame(all_rows) if all_rows else pd.DataFrame()
