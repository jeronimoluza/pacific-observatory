"""Myanmar fuel price fetchers — GNLM and Denko station prices."""

# ruff: noqa: E402
SOURCE_META = [
    {
        "fetcher_fn": "fetch_myanmar_gnlm",
        "country": "Myanmar",
        "source_name": "Global New Light of Myanmar (GNLM)",
        "url": "https://www.gnlm.com.mm/?s=fuel+price",
        "description": "State-run newspaper (GNLM). Official government fuel reference prices embedded in news articles. No structured data or API.",
        "extraction_method": ["Web scraping"],
        "products": [
            "Gasoline Octane 92 (Regular)",
            "Gasoline Octane 95 (Premium)",
            "Diesel",
            "Diesel (Premium)",
        ],
        "source_keys": ["mm_gnlm_fuel_reference_prices"],
        "publishes_on": "Weekly",
        "notes": "Crawls search results for fuel articles; regex extracts prices from body text. Processes up to 30 candidate articles. Price range MMK 500–5,000/L.",
    },
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
        "notes": "Cloudflare-protected site — requires Playwright headless browser. Extracts daily price table with division/station granularity. Price range MMK 500–5,000/L.",
    },
]

import re
import time
from datetime import date

import pandas as pd
from bs4 import BeautifulSoup

from ..utils import MONTH_MAP_EN, get_session, make_hash, make_template

_TMPL_MM = make_template(
    country="Myanmar",
    wb_iso3="MMR",
    source_key="mm_gnlm_fuel_reference_prices",
    source_name="Myanmar Global New Light — Fuel Reference Prices",
    source_url="https://www.gnlm.com.mm/",
    currency="MMK",
    unit="L",
    subnational_area="National",
    publication_frequency="weekly",
    observation_method="reported",
    tax_status="tax_inclusive",
)

_PRODUCTS = [
    (
        "Octane 92",
        "gasoline",
        "regular",
        92,
        r"(?i)octane.{0,5}92|ron.{0,5}92|92.{0,5}octane",
    ),
    (
        "Octane 95",
        "gasoline",
        "premium",
        95,
        r"(?i)octane.{0,5}95|ron.{0,5}95|95.{0,5}octane",
    ),
    ("Diesel", "diesel", "regular", None, r"(?i)\bdiesel\b"),
    (
        "Premium Diesel",
        "diesel",
        "premium",
        None,
        r"(?i)premium diesel|high.quality diesel",
    ),
]

_SCAN_URLS = [
    "https://www.gnlm.com.mm/?s=fuel+price",
    "https://www.gnlm.com.mm/?s=petroleum+price",
    "https://www.gnlm.com.mm/?s=petrol+price",
    "https://www.gnlm.com.mm/",
]


def fetch_myanmar_gnlm(cutoff: date) -> pd.DataFrame:
    """Fetch Myanmar GNLM weekly fuel reference prices."""
    print("  [mm_gnlm] Fetching Myanmar GNLM data...")
    print(f"  [mm_gnlm] Cutoff: {cutoff}")

    session = get_session()
    today = date.today()
    all_rows = []

    article_links: set[str] = set()
    for scan_url in _SCAN_URLS:
        try:
            r = session.get(scan_url, timeout=20)
            if r.status_code != 200:
                continue
            s = BeautifulSoup(r.content, "lxml")
            for a in s.find_all("a", href=True):
                href = a["href"]
                link_text = a.get_text(strip=True).lower()
                if any(
                    kw in link_text or kw in href.lower()
                    for kw in [
                        "fuel",
                        "petrol",
                        "diesel",
                        "price",
                        "petroleum",
                        "octane",
                    ]
                ):
                    if "gnlm.com.mm" in href:
                        article_links.add(href)
        except Exception as e:
            print(f"  [mm_gnlm] Scan error {scan_url}: {e}")
        time.sleep(0.3)

    print(f"  [mm_gnlm] Found {len(article_links)} candidate links")

    for art_url in list(article_links)[:30]:
        try:
            r = session.get(art_url, timeout=20)
            if r.status_code != 200:
                continue
            art_soup = BeautifulSoup(r.content, "lxml")
            text = art_soup.get_text(separator="\n")

            if not any(
                kw in text.lower() for kw in ["fuel", "octane", "diesel", "petroleum"]
            ):
                continue

            obs_date = None
            iso_m = re.search(r"(20\d{2})[/\-](\d{2})[/\-](\d{2})", text)
            if iso_m:
                try:
                    obs_date = date(
                        int(iso_m.group(1)), int(iso_m.group(2)), int(iso_m.group(3))
                    )
                except ValueError:
                    pass
            if obs_date is None:
                for month_name, month_num in MONTH_MAP_EN.items():
                    if len(month_name) < 4:
                        continue  # skip 3-letter abbrevs to avoid false positives
                    if month_name in text.lower():
                        year_m = re.search(r"\b(20\d{2})\b", text)
                        if year_m:
                            try:
                                obs_date = date(int(year_m.group(1)), month_num, 1)
                                break
                            except ValueError:
                                pass

            if obs_date is None or obs_date <= cutoff or obs_date > today:
                continue

            rows_added = 0
            for prod_name, family, qg, ron, prod_pat in _PRODUCTS:
                m = re.search(
                    rf"{prod_pat}[^\d]{{0,150}}(\d{{3,5}}(?:\.\d{{1,2}})?)",
                    text,
                    re.IGNORECASE | re.DOTALL,
                )
                if not m:
                    continue
                try:
                    price = float(m.group(1))
                    if not (500 <= price <= 5000):
                        continue
                except ValueError:
                    continue

                r_row = _TMPL_MM.copy()
                r_row.update(
                    {
                        "fuel_family": family,
                        "fuel_product": prod_name,
                        "quality_group": qg,
                        "octane_ron": ron,
                        "price_local": price,
                        "effective_from": str(obs_date),
                        "effective_to": str(obs_date),
                        "observation_date": str(obs_date),
                        "source_url": art_url,
                    }
                )
                r_row["observation_hash"] = make_hash(r_row)
                all_rows.append(r_row)
                rows_added += 1

            if rows_added:
                print(f"  [mm_gnlm] {obs_date}: {rows_added} products from {art_url}")

        except Exception as e:
            print(f"  [mm_gnlm] Error {art_url}: {e}")
        time.sleep(0.3)

    if all_rows:
        print(f"  [mm_gnlm] {len(all_rows)} new rows")
    else:
        print("  [mm_gnlm] No new rows")
    return pd.DataFrame(all_rows) if all_rows else pd.DataFrame()


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
                if not (500 <= price <= 5000):
                    continue
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
