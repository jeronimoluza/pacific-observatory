#!/usr/bin/env python3
"""Bootstrap Abu Dhabi Murban historical data using Playwright.

Strategy:
  1. Open the investing.com Murban historical-data page in a real browser
     (bypasses Cloudflare because the TLS/JS fingerprint is genuine).
  2. Intercept any XHR/fetch calls to api.investing.com/api/financialdata/historical/*.
  3. If no API call fires on load, try clicking the "Max" date-range button to
     trigger a full-history fetch.
  4. Fall back to __NEXT_DATA__ embedded in the rendered HTML if no API call is
     captured.
  5. Merge extracted rows into the existing observations.csv and report counts.

Usage:
    python scripts/bootstrap_murban.py
"""

import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.cpi.fuel_prices.fetchers.global_commodities import (
    _extract_next_data,
    _find_historical_rows,
    _parse_price_rows,
)
from src.cpi.fuel_prices.loader import merge_new_rows
from src.cpi.fuel_prices.storage import source_csv_path
from src.cpi.fuel_prices.utils import make_hash, make_template

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MURBAN_SLUG = "abu-dhabi-murban-crude-oil-futures"
MURBAN_URL = f"https://www.investing.com/commodities/{MURBAN_SLUG}-historical-data"

# ICE Murban contract launched 2021-03-29; use day before as cutoff
BOOTSTRAP_CUTOFF = date(2021, 3, 28)

_MURBAN_TEMPLATE_KWARGS = dict(
    country="EAP",
    wb_iso3="EAP",
    subnational_area="East Asia & Pacific",
    fuel_family="crude_oil",
    fuel_product="Abu Dhabi Murban Crude Oil F (MRBNc1)",
    quality_group="murban",
    currency="USD",
    unit="bbl",
    source_key="global_investing_daily",
    source_name="Investing.com Commodity Futures",
    source_url=MURBAN_URL,
    source_type="market",
    publication_frequency="daily",
    observation_method="market",
    tax_status="pre_tax",
)

# Selectors tried in order when looking for a "Max" date-range button
_MAX_BUTTON_SELECTORS = [
    "button:has-text('Max')",
    "li:has-text('Max')",
    "a:has-text('Max')",
    "[data-testid='Max']",
    "[data-value='max']",
    "span:has-text('Max')",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _rows_to_df(raw_rows: list[dict]) -> pd.DataFrame:
    tmpl = make_template(**_MURBAN_TEMPLATE_KWARGS)
    records = []
    for entry in raw_rows:
        obs_date = entry["obs_date"]
        r = tmpl.copy()
        r.update(
            {
                "price_local": round(entry["price"], 4),
                "effective_from": str(obs_date),
                "effective_to": str(obs_date),
                "observation_date": str(obs_date),
            }
        )
        r["observation_hash"] = make_hash(r)
        records.append(r)
    return pd.DataFrame(records)


def _try_expand_date_range(page) -> None:
    """Attempt to click a 'Max' date-range button on the page."""
    for selector in _MAX_BUTTON_SELECTORS:
        try:
            btn = page.locator(selector).first
            if btn.is_visible(timeout=2000):
                btn.click()
                page.wait_for_load_state("networkidle", timeout=20000)
                print(f"  [playwright] Clicked Max via: {selector!r}")
                return
        except Exception:
            pass
    print("  [playwright] Max button not found with any selector")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def _date_chunks(start: date, end: date, months: int = 11) -> list[tuple[date, date]]:
    """Split [start, end] into chunks of at most `months` months."""
    chunks = []
    cursor = start
    while cursor <= end:
        # Advance by `months` months
        year = cursor.year + (cursor.month + months - 1) // 12
        month = (cursor.month + months - 1) % 12 + 1
        chunk_end = min(date(year, month, 1) - timedelta(days=1), end)
        chunks.append((cursor, chunk_end))
        cursor = chunk_end + timedelta(days=1)
    return chunks


def main() -> None:
    api_responses: list[dict] = []
    html_content: str | None = None

    instrument_id: int | None = None
    captured_request_headers: dict = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()

        def _on_request(request):
            nonlocal captured_request_headers
            if "api.investing.com/api/financialdata/historical" in request.url:
                captured_request_headers = dict(request.headers)

        def _on_response(response):
            nonlocal instrument_id
            if "api.investing.com/api/financialdata/historical" in response.url:
                print(f"  [playwright] Intercepted API call → HTTP {response.status}")
                print(f"               {response.url[:120]}")
                # Extract instrument ID from URL path: .../historical/{id}?...
                try:
                    path_part = response.url.split("/api/financialdata/historical/")[1]
                    instrument_id = int(path_part.split("?")[0])
                    print(f"  [playwright] Instrument ID: {instrument_id}")
                except Exception:
                    pass
                if response.status == 200:
                    try:
                        api_responses.append(response.json())
                    except Exception as e:
                        print(f"  [playwright] JSON parse error: {e}")

        page.on("request", _on_request)
        page.on("response", _on_response)

        print(f"  [playwright] Loading {MURBAN_URL}")
        # investing.com pages never reach "load"/"networkidle" cleanly due to
        # persistent ad/tracker resources. Catch the timeout — the API call
        # fires early and we capture the instrument ID before the timeout hits.
        try:
            page.goto(MURBAN_URL, wait_until="load", timeout=30000)
        except Exception:
            pass  # timeout expected; proceed if instrument_id was captured
        # Give JS a moment to fire the initial data fetch
        page.wait_for_timeout(5000)
        try:
            html_content = page.content()
        except Exception:
            html_content = None
        print(
            f"  [playwright] Navigation done — instrument_id={instrument_id}, {len(api_responses)} API response(s)"
        )
        if captured_request_headers:
            print(
                f"  [playwright] Captured request headers: {list(captured_request_headers.keys())}"
            )

        # If we have the instrument ID, use page.evaluate (runs inside the browser,
        # so Cloudflare passes it) with the exact headers the page used — including
        # the `domain-id` header that the server requires.
        if instrument_id:
            chunks = _date_chunks(BOOTSTRAP_CUTOFF + timedelta(days=1), date.today())
            print(
                f"  [playwright] Fetching {len(chunks)} annual chunk(s) via page.evaluate fetch..."
            )
            for chunk_start, chunk_end in chunks:
                api_url = (
                    f"https://api.investing.com/api/financialdata/historical/{instrument_id}"
                    f"?start-date={chunk_start}&end-date={chunk_end}"
                    f"&time-frame=Daily&add-missing-rows=false"
                )
                print(f"  [playwright] Chunk {chunk_start} → {chunk_end}")
                try:
                    result = page.evaluate(
                        """async ([url, headers]) => {
                            const resp = await fetch(url, { headers: headers });
                            const body = await resp.json().catch(() => null);
                            return { status: resp.status, body: body };
                        }""",
                        [api_url, captured_request_headers],
                    )
                    print(f"    HTTP {result['status']}")
                    if result["status"] == 200 and result.get("body"):
                        api_responses.append(result["body"])
                    else:
                        print(f"    body={str(result.get('body'))[:120]}")
                except Exception as e:
                    print(f"    Evaluate error: {e}")

        elif not api_responses:
            print("  [playwright] No instrument ID — trying to expand date range...")
            _try_expand_date_range(page)
            print(
                f"  [playwright] After expansion — {len(api_responses)} API response(s)"
            )

        browser.close()

    # Parse results ----------------------------------------------------------------
    raw_rows: list[dict] = []

    if api_responses:
        for i, resp_json in enumerate(api_responses, 1):
            rows_data = _find_historical_rows(resp_json)
            parsed = _parse_price_rows(rows_data, BOOTSTRAP_CUTOFF)
            raw_rows.extend(parsed)
            print(f"  [playwright] API response {i}: {len(parsed)} rows parsed")
    else:
        print("  [playwright] No API responses — falling back to __NEXT_DATA__")
        if html_content:
            next_data = _extract_next_data(html_content)
            if next_data:
                rows_data = _find_historical_rows(next_data)
                raw_rows = _parse_price_rows(rows_data, BOOTSTRAP_CUTOFF)

    if not raw_rows:
        print("  [playwright] No rows extracted. Nothing to save.")
        return

    raw_rows.sort(key=lambda x: x["obs_date"])
    print(
        f"  [playwright] Extracted {len(raw_rows)} rows: "
        f"{raw_rows[0]['obs_date']} → {raw_rows[-1]['obs_date']}"
    )

    # Merge into observations.csv --------------------------------------------------
    new_df = _rows_to_df(raw_rows)
    csv_path = source_csv_path("eap", "global_investing_daily")
    existing = pd.read_csv(csv_path) if csv_path.exists() else pd.DataFrame()
    merged = merge_new_rows(existing, new_df)
    merged.to_csv(csv_path, index=False)
    print(f"  [playwright] Saved {len(merged)} total rows → {csv_path}")


if __name__ == "__main__":
    main()
