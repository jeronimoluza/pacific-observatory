"""Global and EAP commodity oil/gasoline price fetchers.

Source:
  1. Investing.com historical-data pages (daily, Playwright-based — fresh context per slug)
"""

import json
import time
from datetime import date, timedelta
from typing import Optional

import pandas as pd
from playwright.sync_api import Browser, sync_playwright

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
        "notes": "Uses Playwright headless Chromium with fresh context per slug to bypass Cloudflare.",
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
_INVESTING_API = "https://api.investing.com/api/financialdata/historical"
_INVESTING_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}
_INVESTING_API_HEADERS = {
    **_INVESTING_HEADERS,
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.investing.com/",
    "X-Requested-With": "XMLHttpRequest",
    "Domain": "www.investing.com",
}

# Playwright fetch settings — fresh context per slug defeats CF bot fingerprinting
_INVESTING_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
_INVESTING_VIEWPORT = {"width": 1366, "height": 900}
_INVESTING_SETTLE_MS = 2500  # let CF challenge run after domcontentloaded
_FETCH_RETRIES = 3
_FETCH_RETRY_SLEEP = 5


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


def _extract_instrument_id(obj: object, depth: int = 0) -> Optional[int]:
    """Recursively search __NEXT_DATA__ for the investing.com numeric instrument ID.

    Looks for ``pairId`` or ``instrumentId`` keys (in that priority order) since
    those are investing.com-specific and unambiguous.  The generic ``id`` key is
    intentionally skipped to avoid false positives.
    """
    if depth > 15:
        return None
    if isinstance(obj, dict):
        for key in ("pairId", "instrumentId"):
            val = obj.get(key)
            if isinstance(val, int) and val > 0:
                return val
        for v in obj.values():
            result = _extract_instrument_id(v, depth + 1)
            if result:
                return result
    elif isinstance(obj, list):
        for item in obj:
            result = _extract_instrument_id(item, depth + 1)
            if result:
                return result
    return None


def _parse_price_rows(rows_data: list[dict], cutoff: date) -> list[dict]:
    """Convert raw investing.com row dicts into ``{obs_date, price}`` entries."""
    results = []
    for entry in rows_data:
        try:
            raw_date = entry.get("rowDateTimestamp") or entry.get("rowDate")
            obs_date = pd.to_datetime(raw_date).date()
        except Exception:
            continue
        if obs_date <= cutoff:
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


def _fetch_investing_api(instrument_id: int, cutoff: date, slug: str) -> list[dict]:
    """Attempt to fetch full history via the investing.com historical API.

    Returns parsed ``{obs_date, price}`` rows, or an empty list on any failure.
    """
    session = get_session()
    session.headers.update(_INVESTING_API_HEADERS)
    params = {
        "start-date": str(cutoff + timedelta(days=1)),
        "end-date": str(date.today()),
        "time-frame": "Daily",
        "add-missing-rows": "false",
    }
    url = f"{_INVESTING_API}/{instrument_id}"
    try:
        resp = session.get(url, params=params, timeout=30)
        if resp.status_code != 200:
            print(
                f"  [investing] API HTTP {resp.status_code} for {slug} (id={instrument_id})"
            )
            return []
        api_data = resp.json()
    except Exception as e:
        print(f"  [investing] API error for {slug}: {e}")
        return []

    api_rows = _find_historical_rows(api_data)
    if not api_rows:
        print(f"  [investing] API returned no rows for {slug} (id={instrument_id})")
        return []

    results = _parse_price_rows(api_rows, cutoff)
    print(f"  [investing] API returned {len(results)} rows for {slug}")
    return results


def _fetch_investing_series(slug: str, cutoff: date, browser: Browser) -> list[dict]:
    """Fetch historical data for one slug using a fresh Playwright context.

    Stage 1 (API) — used when ``cutoff`` is more than 30 days in the past.
      Extracts the instrument's numeric ID from ``__NEXT_DATA__`` and calls the
      investing.com history API to retrieve the full date range.  Falls through
      to Stage 2 on any failure.

    Stage 2 (HTML fallback) — always available.
      Returns the ~20 recent trading days embedded in the page's ``__NEXT_DATA__``.
      This is sufficient for normal daily incremental updates.
    """
    url = f"{_INVESTING_BASE}{slug}-historical-data"
    html = None

    for attempt in range(1, _FETCH_RETRIES + 1):
        # Fresh context each attempt — wipes CF fingerprint score between slugs
        ctx = browser.new_context(
            user_agent=_INVESTING_USER_AGENT,
            locale="en-US",
            viewport=_INVESTING_VIEWPORT,
        )
        page = ctx.new_page()
        try:
            try:
                resp = page.goto(url, wait_until="domcontentloaded", timeout=45000)
            except Exception as e:
                print(
                    f"  [investing] Navigation error for {slug} (attempt {attempt}): {e}"
                )
                if attempt < _FETCH_RETRIES:
                    time.sleep(_FETCH_RETRY_SLEEP)
                continue

            if resp is None or resp.status != 200:
                status = resp.status if resp else "None"
                print(f"  [investing] HTTP {status} for {slug} (attempt {attempt})")
                if attempt < _FETCH_RETRIES:
                    time.sleep(_FETCH_RETRY_SLEEP)
                continue

            page.wait_for_timeout(_INVESTING_SETTLE_MS)
            html = page.content()
        finally:
            ctx.close()  # CRITICAL: wipes the CF fingerprint score
        break  # successful fetch

    if html is None:
        print(f"  [investing] All {_FETCH_RETRIES} attempts failed for {slug}")
        return []

    data = _extract_next_data(html)
    if data is None:
        print(f"  [investing] __NEXT_DATA__ not found/parseable for {slug}")
        return []

    rows_data = _find_historical_rows(data)
    if not rows_data:
        print(f"  [investing] No historical rows found in page data for {slug}")
        return []

    # Stage 1: attempt API for large historical backfills
    if cutoff < date.today() - timedelta(days=30):
        instrument_id = _extract_instrument_id(data)
        if instrument_id:
            print(
                f"  [investing] Trying API for {slug} (id={instrument_id}, cutoff={cutoff})"
            )
            api_results = _fetch_investing_api(instrument_id, cutoff, slug)
            if api_results:
                return api_results
            print(f"  [investing] API failed for {slug}, falling back to HTML rows")
        else:
            print(f"  [investing] No instrument ID found in page data for {slug}")

    # Stage 2: HTML fallback (~20 recent rows)
    return _parse_price_rows(rows_data, cutoff)


def fetch_investing_commodities(cutoff: date) -> pd.DataFrame:
    """Fetch daily global/EAP commodity prices from investing.com via Playwright."""
    print("  [investing] Fetching investing.com commodity data...")
    print(f"  [investing] Cutoff: {cutoff}")

    all_rows = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            for spec in _INVESTING_SLUGS:
                slug = spec["slug"]
                print(f"  [investing] → {slug}")

                raw_rows = _fetch_investing_series(slug, cutoff, browser)
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
                            "price_local": round(entry["price"], 4),
                            "effective_from": str(obs_date),
                            "effective_to": str(obs_date),
                            "observation_date": str(obs_date),
                            "source_url": f"{_INVESTING_BASE}{slug}-historical-data",
                        }
                    )
                    r["observation_hash"] = make_hash(r)
                    all_rows.append(r)

                print(f"  [investing]   {len(raw_rows)} rows for {slug}")
        finally:
            browser.close()

    print(f"  [investing] Total: {len(all_rows)} rows")
    return pd.DataFrame(all_rows) if all_rows else pd.DataFrame()
