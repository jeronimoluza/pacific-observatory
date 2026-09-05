"""Myanmar fuel price fetchers — Denko station prices and Starfish market prices."""

# ruff: noqa: E402
SOURCE_META = [
    {
        "fetcher_fn": "fetch_myanmar_denko",
        "country": "Myanmar",
        "source_name": "Denko Myanmar — All Station Daily Fuel Rates",
        "url": "https://denkomyanmar.com/all-denko-station-daily-fuel-rates/",
        "description": "Denko Myanmar retail fuel station chain. Daily station-level pump prices across multiple divisions/states.",
        "extraction_method": ["Playwright web scraping"],
        "products": [
            "Diesel",
            "Premium Diesel",
            "Gasoline Octane 92 (Regular)",
            "Gasoline Octane 95 (Premium)",
        ],
        "source_keys": ["mm_denko_station_daily"],
        "publishes_on": "Daily",
        "notes": "Cloudflare-protected site — requires Playwright headless browser. Extracts daily price table with division/station granularity.",
    },
    {
        "fetcher_fn": "fetch_myanmar_starfish",
        "country": "Myanmar",
        "source_name": "Starfish Myanmar — Market Price",
        "url": "https://starfishmyanmar.com/market-price",
        "description": "Starfish Myanmar petroleum distributor. National-level 5-day average retail fuel prices published at ~25-day intervals.",
        "extraction_method": ["Web scraping (embedded JS data)"],
        "products": [
            "Gasoline Octane 92 (Regular)",
            "Gasoline Octane 95 (Premium)",
            "Diesel",
            "Diesel (Premium)",
        ],
        "source_keys": ["mm_starfish_market_price"],
        "publishes_on": "Irregular (~25 days)",
        "notes": "Prices extracted from chart_data JS object embedded in HTML. No API, no auth, no bot protection.",
    },
]

import json
import re
from datetime import date

import pandas as pd

from ..utils import get_session, make_hash, make_template, MONTH_MAP_EN

# ── Denko Myanmar ─────────────────────────────────────────────────────────────

_TMPL_MM_DENKO = make_template(
    country="Myanmar",
    wb_iso3="MMR",
    source_key="mm_denko_station_daily",
    source_name="Denko Myanmar — All Station Daily Fuel Rates",
    source_url="https://denkomyanmar.com/all-denko-station-daily-fuel-rates/",
    currency="MMK",
    unit="L",
    publication_frequency="daily",
    observation_method="reported",
    tax_status="tax_inclusive",
)

_DENKO_PRODUCTS = [
    ("Diesel", "diesel", "regular", None),
    ("Premium Diesel", "diesel", "premium", None),
    ("Octane 92", "gasoline", "regular", 92),
    ("Octane 95", "gasoline", "premium", 95),
]

_DENKO_URL = "https://denkomyanmar.com/all-denko-station-daily-fuel-rates/"

_DENKO_DATE_RE = re.compile(
    r"(?:Effective\s+on|as\s+of)\s+"
    r"(January|February|March|April|May|June|July|August|September|October|November|December)"
    r"\s+(\d{1,2}),?\s+(20\d{2})",
    re.IGNORECASE,
)


def fetch_myanmar_denko(cutoff: date) -> pd.DataFrame:
    """Fetch Denko Myanmar daily station-level fuel prices via Playwright."""
    print("  [mm_denko] Fetching Denko Myanmar station prices...")
    print(f"  [mm_denko] Cutoff: {cutoff}")

    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:
        print(f"  [mm_denko] Playwright not available: {e}")
        return pd.DataFrame()

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
        )
        ctx = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/121.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1920, "height": 1080},
        )
        page = ctx.new_page()
        page.add_init_script(
            'Object.defineProperty(navigator, "webdriver", {get: () => undefined})'
        )

        try:
            page.goto(_DENKO_URL, timeout=60_000)
            page.wait_for_timeout(8_000)  # Cloudflare challenge
        except Exception as e:
            print(f"  [mm_denko] Page load error: {e}")
            browser.close()
            return pd.DataFrame()

        try:
            payload = page.evaluate(
                """() => {
                    const body = document.body.innerText;
                    const dateMatch = body.match(
                        /(?:Effective\\s+on|as\\s+of)\\s+(January|February|March|April|May|June|July|August|September|October|November|December)\\s+(\\d{1,2}),?\\s+(20\\d{2})/i
                    );
                    const date_text = dateMatch ? dateMatch[0] : '';

                    const table = document.querySelector('table');
                    if (!table) return { date_text, headers: [], rows: [] };

                    // Header row
                    const headerRow = table.querySelector('thead tr') || table.querySelector('tr');
                    const headers = Array.from(headerRow.querySelectorAll('th,td'))
                        .map(c => (c.textContent || '').trim());
                    const numCols = headers.length;

                    // Flatten rowspan: build a 2D grid from tbody rows
                    const trs = Array.from(table.querySelectorAll('tbody tr'));
                    // spanTracker[col] = {text, remaining}
                    const spanTracker = {};
                    const rows = [];
                    for (const tr of trs) {
                        const cells = Array.from(tr.querySelectorAll('th,td'));
                        const row = new Array(numCols).fill('');
                        let cellIdx = 0;
                        for (let col = 0; col < numCols; col++) {
                            if (spanTracker[col] && spanTracker[col].remaining > 0) {
                                row[col] = spanTracker[col].text;
                                spanTracker[col].remaining--;
                            } else if (cellIdx < cells.length) {
                                const c = cells[cellIdx];
                                const text = (c.textContent || '').trim();
                                const rs = c.rowSpan || 1;
                                row[col] = text;
                                if (rs > 1) {
                                    spanTracker[col] = { text, remaining: rs - 1 };
                                }
                                cellIdx++;
                            }
                        }
                        if (row.some(v => v !== '')) rows.push(row);
                    }

                    return { date_text, headers, rows };
                }"""
            )
        except Exception as e:
            print(f"  [mm_denko] DOM extract error: {e}")
            browser.close()
            return pd.DataFrame()

        browser.close()

    # --- parse effective date ---
    date_text = payload.get("date_text", "")
    dm = _DENKO_DATE_RE.search(date_text)
    if not dm:
        print(f"  [mm_denko] Could not parse date from: {date_text!r}")
        return pd.DataFrame()

    month_num = MONTH_MAP_EN[dm.group(1).lower()]
    day = int(dm.group(2))
    year = int(dm.group(3))
    try:
        obs_date = date(year, month_num, day)
    except ValueError:
        print(f"  [mm_denko] Invalid date: {year}-{month_num}-{day}")
        return pd.DataFrame()

    if obs_date <= cutoff:
        print(f"  [mm_denko] Date {obs_date} not newer than cutoff {cutoff}")
        return pd.DataFrame()

    # --- map header columns to product indices ---
    headers = payload.get("headers", [])
    body_rows = payload.get("rows", [])

    col_map: dict[int, tuple] = {}  # col_idx → (prod_name, family, qg, ron)
    for i, hdr in enumerate(headers):
        hdr_lower = hdr.lower().strip()
        if "octane 92" in hdr_lower:
            col_map[i] = _DENKO_PRODUCTS[2]  # Octane 92
        elif "octane 95" in hdr_lower:
            col_map[i] = _DENKO_PRODUCTS[3]  # Octane 95
        elif "premium" in hdr_lower or "premiun" in hdr_lower:
            col_map[i] = _DENKO_PRODUCTS[1]  # Premium Diesel
        elif hdr_lower == "diesel":
            col_map[i] = _DENKO_PRODUCTS[0]  # Diesel

    if not col_map:
        print(f"  [mm_denko] Could not map product columns from headers: {headers}")
        return pd.DataFrame()

    # --- identify division and station columns ---
    div_col = None
    station_col = None
    for i, hdr in enumerate(headers):
        hdr_lower = hdr.lower().strip()
        if "division" in hdr_lower or "state" in hdr_lower or "region" in hdr_lower:
            div_col = i
        elif "station" in hdr_lower:
            station_col = i

    # --- process rows (rowspan already flattened by JS) ---
    all_rows: list[dict] = []

    for cells in body_rows:
        if not cells:
            continue

        division = ""
        if div_col is not None and div_col < len(cells):
            division = cells[div_col].strip()

        station = ""
        if station_col is not None and station_col < len(cells):
            station = cells[station_col].strip()

        if not station:
            continue

        for col_idx, (prod_name, family, qg, ron) in col_map.items():
            if col_idx >= len(cells):
                continue
            price_text = cells[col_idx].strip().replace(",", "")
            if not price_text:
                continue
            pm = re.search(r"(\d+(?:\.\d+)?)", price_text)
            if not pm:
                continue
            try:
                price = float(pm.group(1))
            except ValueError:
                continue

            r_row = _TMPL_MM_DENKO.copy()
            r_row.update(
                {
                    "subnational_area": division,
                    "city": station,
                    "fuel_family": family,
                    "fuel_product": prod_name,
                    "quality_group": qg,
                    "octane_ron": ron,
                    "price_local": price,
                    "effective_from": str(obs_date),
                    "effective_to": str(obs_date),
                    "observation_date": str(obs_date),
                    "source_url": _DENKO_URL,
                }
            )
            r_row["observation_hash"] = make_hash(r_row)
            all_rows.append(r_row)

    if all_rows:
        stations = len({r["city"] for r in all_rows})
        print(f"  [mm_denko] {obs_date}: {len(all_rows)} rows from {stations} stations")
    else:
        print("  [mm_denko] No new rows")
    return pd.DataFrame(all_rows) if all_rows else pd.DataFrame()


# ── Starfish Myanmar ─────────────────────────────────────────────────────────

_TMPL_MM_STARFISH = make_template(
    country="Myanmar",
    wb_iso3="MMR",
    source_key="mm_starfish_market_price",
    source_name="Starfish Myanmar — Market Price",
    source_url="https://starfishmyanmar.com/market-price",
    currency="MMK",
    unit="L",
    subnational_area="National",
    publication_frequency="irregular",
    observation_method="reported",
    tax_status="tax_inclusive",
)

_STARFISH_URL = "https://starfishmyanmar.com/market-price"

_STARFISH_PRODUCTS = {
    "Ron 92": ("Octane 92", "gasoline", "regular", 92),
    "Ron 95": ("Octane 95", "gasoline", "premium", 95),
    "Diesel - 500 PPM": ("Diesel", "diesel", "regular", None),
    "Premium Diesel - 50 PPM": ("Premium Diesel", "diesel", "premium", None),
}


def fetch_myanmar_starfish(cutoff: date) -> pd.DataFrame:
    """Fetch Starfish Myanmar national fuel price averages."""
    print("  [mm_starfish] Fetching Starfish Myanmar market prices...")
    print(f"  [mm_starfish] Cutoff: {cutoff}")

    session = get_session()
    url = f"{_STARFISH_URL}?date_range={cutoff} , {date.today()}"

    try:
        r = session.get(url, timeout=30)
        if r.status_code != 200:
            print(f"  [mm_starfish] HTTP {r.status_code}")
            return pd.DataFrame()
    except Exception as e:
        print(f"  [mm_starfish] Request error: {e}")
        return pd.DataFrame()

    # Extract chart_data JS object from HTML
    m = re.search(r"let\s+chart_data\s*=\s*(\{.*?\})\s*;", r.text, re.DOTALL)
    if not m:
        print("  [mm_starfish] Could not find chart_data in page")
        return pd.DataFrame()

    try:
        chart_data = json.loads(m.group(1))
    except json.JSONDecodeError:
        # chart_data may use single quotes or JS syntax — try eval-safe cleanup
        raw = m.group(1)
        raw = raw.replace("'", '"')
        try:
            chart_data = json.loads(raw)
        except json.JSONDecodeError as e:
            print(f"  [mm_starfish] JSON parse error: {e}")
            return pd.DataFrame()

    head = chart_data.get("head", {})
    body = chart_data.get("body", [])

    # head is {key: display_label, ...} — keys are date strings
    date_keys = list(head.keys())

    all_rows: list[dict] = []

    for series in body:
        if not series or len(series) < 3:
            continue
        label = series[0]
        unit_text = series[1]

        if label not in _STARFISH_PRODUCTS:
            continue
        if "kyat" not in unit_text.lower() or "liter" not in unit_text.lower():
            continue

        prod_name, family, qg, ron = _STARFISH_PRODUCTS[label]
        values = series[2:]

        for i, val in enumerate(values):
            if i >= len(date_keys):
                break
            if val is None or val == "" or val == 0:
                continue

            try:
                price = float(val)
            except (ValueError, TypeError):
                continue

            date_str = date_keys[i]
            try:
                obs_date = date.fromisoformat(date_str)
            except ValueError:
                continue

            if obs_date <= cutoff:
                continue

            row = _TMPL_MM_STARFISH.copy()
            row.update(
                {
                    "fuel_family": family,
                    "fuel_product": prod_name,
                    "quality_group": qg,
                    "octane_ron": ron,
                    "price_local": price,
                    "effective_from": str(obs_date),
                    "effective_to": str(obs_date),
                    "observation_date": str(obs_date),
                    "source_url": _STARFISH_URL,
                }
            )
            row["observation_hash"] = make_hash(row)
            all_rows.append(row)

    if all_rows:
        dates = len({r["observation_date"] for r in all_rows})
        print(f"  [mm_starfish] {len(all_rows)} rows across {dates} dates")
    else:
        print("  [mm_starfish] No new rows")
    return pd.DataFrame(all_rows) if all_rows else pd.DataFrame()
