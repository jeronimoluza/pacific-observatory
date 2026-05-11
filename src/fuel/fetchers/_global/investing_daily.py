"""Global and EAP commodity oil/gasoline price fetcher.

Source: Investing.com internal API + HTML fallback.
Smart backfill: API → Playwright (optional) → HTML __NEXT_DATA__.
HTML fetches use Playwright with a fresh ``browser.new_context()`` per slug
to bypass Cloudflare bot fingerprinting (verified 2026-05-04).
"""

from __future__ import annotations

import json
import logging
import time
from datetime import date, timedelta

import pandas as pd
from playwright.sync_api import Browser, sync_playwright

from core.hashing import observation_hash
from core.http import make_session

logger = logging.getLogger(__name__)

_GLOBAL = dict(country="Global", wb_iso3="WLD", subnational_area="Global")
_EAP = dict(country="EAP", wb_iso3="EAP", subnational_area="East Asia & Pacific")

INVESTING_SLUGS: list[dict] = [
    dict(
        slug="crude-oil",
        fuel_product="WTI Crude Oil",
        fuel_family="crude_oil",
        unit="bbl",
        currency="USD",
        **_GLOBAL,
    ),
    dict(
        slug="brent-oil",
        fuel_product="Brent Crude Oil",
        fuel_family="crude_oil",
        unit="bbl",
        currency="USD",
        **_GLOBAL,
    ),
    dict(
        slug="gasoline-rbob",
        fuel_product="Gasoline RBOB",
        fuel_family="gasoline",
        unit="gal",
        currency="USD",
        **_GLOBAL,
    ),
    dict(
        slug="dubai-crude-oil-platts-futures",
        fuel_product="Dubai Crude Oil (Platts)",
        fuel_family="crude_oil",
        unit="bbl",
        currency="USD",
        **_EAP,
    ),
    dict(
        slug="nymex-singapore-gasoil-platts-c1-futures",
        fuel_product="Singapore Gasoil (Platts)",
        fuel_family="gasoil",
        unit="bbl",
        currency="USD",
        **_EAP,
    ),
    dict(
        slug="abu-dhabi-murban-crude-oil-futures",
        fuel_product="Abu Dhabi Murban Crude Oil F (MRBNc1)",
        fuel_family="crude_oil",
        unit="bbl",
        currency="USD",
        **_EAP,
    ),
]

_SOURCE_KEY = "investing_daily"

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
_INVESTING_USER_AGENT = _INVESTING_HEADERS["User-Agent"]
_INVESTING_VIEWPORT = {"width": 1366, "height": 900}
_INVESTING_SETTLE_MS = 2500  # let CF challenge run after domcontentloaded

_HASH_FIELDS = [
    "country",
    "source_key",
    "observation_date",
    "fuel_product",
    "subnational_area",
    "price_local",
]


def _extract_next_data(html: str) -> dict | None:
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


def _extract_instrument_id(obj: object, depth: int = 0) -> int | None:
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


def _parse_price_rows(rows_data: list[dict], cutoff: date | None = None) -> list[dict]:
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


def _fetch_api(instrument_id: int, cutoff: date, slug: str, session) -> list[dict]:
    params = {
        "start-date": str(cutoff + timedelta(days=1)),
        "end-date": str(date.today()),
        "time-frame": "Daily",
        "add-missing-rows": "false",
    }
    url = f"{_INVESTING_API}/{instrument_id}"
    try:
        resp = session.get(
            url, params=params, headers=_INVESTING_API_HEADERS, timeout=30
        )
        if resp.status_code != 200:
            logger.info(
                "API HTTP %d for %s (id=%d)", resp.status_code, slug, instrument_id
            )
            return []
        api_data = resp.json()
    except Exception as e:
        logger.info("API error for %s: %s", slug, e)
        return []

    api_rows = _find_historical_rows(api_data)
    if not api_rows:
        logger.info("API returned no rows for %s (id=%d)", slug, instrument_id)
        return []

    results = _parse_price_rows(api_rows, cutoff)
    logger.info("API returned %d rows for %s", len(results), slug)
    return results


def _date_chunks(start: date, end: date, months: int = 11) -> list[tuple[date, date]]:
    chunks = []
    cursor = start
    while cursor <= end:
        year = cursor.year + (cursor.month + months - 1) // 12
        month = (cursor.month + months - 1) % 12 + 1
        chunk_end = min(date(year, month, 1) - timedelta(days=1), end)
        chunks.append((cursor, chunk_end))
        cursor = chunk_end + timedelta(days=1)
    return chunks


def _fetch_playwright(slug: str, cutoff: date, instrument_id: int) -> list[dict]:
    """Backfill via Playwright browser automation (Cloudflare bypass)."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.warning(
            "Playwright not installed — skipping browser backfill for %s", slug
        )
        return []

    url = f"{_INVESTING_BASE}{slug}-historical-data"
    api_responses: list[dict] = []
    captured_headers: dict = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=_INVESTING_HEADERS["User-Agent"],
        )
        page = context.new_page()

        def _on_request(request):
            nonlocal captured_headers
            if "api.investing.com/api/financialdata/historical" in request.url:
                captured_headers = dict(request.headers)

        def _on_response(response):
            if "api.investing.com/api/financialdata/historical" in response.url:
                if response.status == 200:
                    try:
                        api_responses.append(response.json())
                    except Exception:
                        pass

        page.on("request", _on_request)
        page.on("response", _on_response)

        logger.info("[playwright] Loading %s", url)
        try:
            page.goto(url, wait_until="load", timeout=30000)
        except Exception:
            pass
        page.wait_for_timeout(5000)

        if instrument_id and captured_headers:
            chunks = _date_chunks(cutoff + timedelta(days=1), date.today())
            logger.info("[playwright] Fetching %d chunks for %s", len(chunks), slug)
            for chunk_start, chunk_end in chunks:
                api_url = (
                    f"{_INVESTING_API}/{instrument_id}"
                    f"?start-date={chunk_start}&end-date={chunk_end}"
                    f"&time-frame=Daily&add-missing-rows=false"
                )
                try:
                    result = page.evaluate(
                        """async ([url, headers]) => {
                            const resp = await fetch(url, { headers });
                            const body = await resp.json().catch(() => null);
                            return { status: resp.status, body };
                        }""",
                        [api_url, captured_headers],
                    )
                    if result["status"] == 200 and result.get("body"):
                        api_responses.append(result["body"])
                except Exception as e:
                    logger.warning("[playwright] Chunk error: %s", e)

        browser.close()

    raw_rows: list[dict] = []
    for resp_json in api_responses:
        rows_data = _find_historical_rows(resp_json)
        raw_rows.extend(_parse_price_rows(rows_data, cutoff))

    logger.info("[playwright] Extracted %d rows for %s", len(raw_rows), slug)
    return raw_rows


_FETCH_RETRIES = 3
_FETCH_RETRY_SLEEP = 5


def _fetch_series(slug: str, cutoff: date, session, browser: Browser) -> list[dict]:
    """Smart 3-stage fetch: API → Playwright backfill → HTML fallback.

    The HTML fetch uses Playwright with a **fresh context per slug** to defeat
    Cloudflare's bot fingerprinting — plain `requests` returns 403 since 2026-05-04.
    Stage 3 (HTML) returns all ~20 rows without cutoff filtering — deduplication
    is handled downstream by ``_merge_new_rows`` via ``observation_hash``.
    """
    url = f"{_INVESTING_BASE}{slug}-historical-data"
    html: str | None = None

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
                logger.info(
                    "Navigation error for %s (attempt %d): %s", slug, attempt, e
                )
                if attempt < _FETCH_RETRIES:
                    time.sleep(_FETCH_RETRY_SLEEP)
                continue

            if resp is None or resp.status != 200:
                status = resp.status if resp else "None"
                logger.info("HTTP %s for %s (attempt %d)", status, slug, attempt)
                if attempt < _FETCH_RETRIES:
                    time.sleep(_FETCH_RETRY_SLEEP)
                continue

            page.wait_for_timeout(_INVESTING_SETTLE_MS)
            html = page.content()
        finally:
            ctx.close()  # CRITICAL: wipes the CF fingerprint score
        break  # successful fetch

    if html is None:
        logger.info("All %d attempts failed for %s", _FETCH_RETRIES, slug)
        return []

    data = _extract_next_data(html)
    if data is None:
        logger.info("__NEXT_DATA__ not found for %s", slug)
        return []

    rows_data = _find_historical_rows(data)
    instrument_id = _extract_instrument_id(data)

    # Stage 1: API (for backfills > 30 days)
    if cutoff < date.today() - timedelta(days=30) and instrument_id:
        logger.info("Trying API for %s (id=%d, cutoff=%s)", slug, instrument_id, cutoff)
        api_results = _fetch_api(instrument_id, cutoff, slug, session)
        if api_results:
            return api_results

        # Stage 2: Playwright fallback (if API failed, e.g. Cloudflare)
        logger.info("API failed for %s — trying Playwright", slug)
        pw_results = _fetch_playwright(slug, cutoff, instrument_id)
        if pw_results:
            return pw_results
        logger.info(
            "Playwright unavailable or failed for %s — using HTML fallback", slug
        )

    # Stage 3: HTML fallback (~20 recent rows, no cutoff — dedup handles it)
    if not rows_data:
        logger.info("No historical rows in page data for %s", slug)
        return []
    return _parse_price_rows(rows_data)


def fetch_investing_commodities(cutoff: date) -> pd.DataFrame:
    """Fetch daily global/EAP commodity prices from investing.com."""
    logger.info("Fetching investing.com commodity data (cutoff=%s) ...", cutoff)
    session = make_session()
    session.headers.update(_INVESTING_HEADERS)

    all_rows = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            for spec in INVESTING_SLUGS:
                slug = spec["slug"]
                logger.info("→ %s", slug)

                raw_rows = _fetch_series(slug, cutoff, session, browser)
                if not raw_rows:
                    logger.info("  0 rows for %s", slug)
                    continue

                for entry in raw_rows:
                    obs_date = entry["obs_date"]
                    r = {
                        "observation_date": str(obs_date),
                        "country": spec["country"],
                        "fuel_product": spec["fuel_product"],
                        "price_local": round(entry["price"], 4),
                        "currency": spec["currency"],
                        "unit": spec["unit"],
                        "source_key": _SOURCE_KEY,
                        "subnational_area": spec["subnational_area"],
                        "city": "",
                        "address": "",
                    }
                    r["observation_hash"] = observation_hash(r, _HASH_FIELDS)
                    all_rows.append(r)

                logger.info("  %d rows for %s", len(raw_rows), slug)
        finally:
            browser.close()

    logger.info("Total: %d rows", len(all_rows))
    return pd.DataFrame(all_rows) if all_rows else pd.DataFrame()
