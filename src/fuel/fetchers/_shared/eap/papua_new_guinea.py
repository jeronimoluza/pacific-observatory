"""Papua New Guinea ICCC monthly indicative retail fuel prices.

Split out unchanged from legacy pacific-observatory
``src/cpi/fuel_prices/fetchers/pacific_islands.py::fetch_png_iccc`` (dev 2d60a353).
"""

# ruff: noqa: E402
SOURCE_META = [
    {
        "fetcher_fn": "fetch_png_iccc",
        "country": "Papua New Guinea",
        "source_name": "ICCC Monthly Indicative Retail Prices",
        "url": "https://iccc.gov.pg/prices-regulation/#fuel-prices",
        "description": "Official government regulator (ICCC). Monthly indicative retail prices for Port Moresby published as WordPress posts with HTML tables.",
        "extraction_method": ["REST API", "HTML table parsing"],
        "products": ["Gasoline (Regular Petrol)", "Diesel", "Kerosene"],
        "source_keys": ["pg_iccc_monthly_irp"],
        "publishes_on": "Monthly",
        "notes": "Uses WP REST API to list and fetch posts. Parses HTML tables for current and previous month prices (toea converted to PGK). Port Moresby only. Price range PGK 1.0–20.0/L.",
    },
]

import re
import time
from datetime import date, timedelta

import pandas as pd
import requests
from bs4 import BeautifulSoup

from fuel.fetchers._shared.eap.legacy import MONTH_MAP_EN, make_hash, make_template

# ── Papua New Guinea ICCC ──────────────────────────────────────────────────────

_TMPL_PNG = make_template(
    country="Papua New Guinea",
    wb_iso3="PNG",
    source_key="pg_iccc_monthly_irp",
    source_name="Papua New Guinea ICCC Indicative Retail Fuel Prices",
    source_url="https://iccc.gov.pg/prices-regulation/#fuel-prices",
    currency="PGK",
    unit="L",
    subnational_area="Port Moresby",
    publication_frequency="monthly",
    observation_method="reported",
    tax_status="tax_inclusive",
)

_PNG_PRODUCTS = [
    ("Petrol", "gasoline", "regular", None),
    ("Diesel", "diesel", "regular", None),
    ("Kerosene", "kerosene", "regular", None),
]

_PNG_DATE_RE = re.compile(
    r"(\d{1,2})\s*(?:st|nd|rd|th)?\s+"
    r"(January|February|March|April|May|June|July|August|September|October|November|December)"
    r"\s+(20\d{2})",
    re.IGNORECASE,
)

_WP_LIST_URL = (
    "https://iccc.gov.pg/wp-json/wp/v2/posts"
    "?categories=763309980&per_page=100&orderby=date&order=desc"
    "&_fields=id,date,slug,title,link"
)


def _parse_png_table(html: str, article_link: str) -> list[dict]:
    """Parse an ICCC article HTML table and return observation rows.

    Each table has header row (product columns) then current-month and
    previous-month price rows.  Prices are in toea (÷100 → PGK).
    """
    soup = BeautifulSoup(html, "lxml")
    table = soup.find("table")
    if table is None:
        return []

    tbody = table.find("tbody")
    trs = (tbody if tbody else table).find_all("tr")
    if len(trs) < 2:
        return []

    # --- header row: identify column indices for each product ---
    header_cells = trs[0].find_all(["th", "td"])
    col_map: dict[int, tuple] = {}  # col_idx → (prod_name, family, qg, ron)
    for i, cell in enumerate(header_cells):
        text = cell.get_text(separator=" ", strip=True).lower()
        for prod_name, family, qg, ron in _PNG_PRODUCTS:
            if prod_name.lower() in text:
                col_map[i] = (prod_name, family, qg, ron)
                break

    if not col_map:
        return []

    rows: list[dict] = []

    # --- data rows (row 1 = current month, row 2 = previous month) ---
    for tr in trs[1:3]:
        cells = tr.find_all(["th", "td"])
        if not cells:
            continue

        # Parse date from the first cell text
        first_text = cells[0].get_text(separator=" ", strip=True)
        dm = _PNG_DATE_RE.search(first_text)
        if not dm:
            continue
        day = int(dm.group(1))
        month_num = MONTH_MAP_EN[dm.group(2).lower()]
        year = int(dm.group(3))
        try:
            obs_date = date(year, month_num, day)
        except ValueError:
            continue

        month_end = (obs_date.replace(day=28) + timedelta(days=4)).replace(
            day=1
        ) - timedelta(days=1)

        for col_idx, (prod_name, family, qg, ron) in col_map.items():
            if col_idx >= len(cells):
                continue
            price_text = cells[col_idx].get_text(separator=" ", strip=True)
            # Extract numeric value (may be inside <strong> tags already flattened)
            pm = re.search(r"([\d,]+(?:\.\d+)?)", price_text.replace(",", ""))
            if not pm:
                continue
            try:
                toea = float(pm.group(1))
                price = toea / 100.0  # toea → PGK
                if not (1.0 <= price <= 20.0):
                    continue
            except ValueError:
                continue

            r_row = _TMPL_PNG.copy()
            r_row.update(
                {
                    "fuel_family": family,
                    "fuel_product": prod_name,
                    "quality_group": qg,
                    "octane_ron": ron,
                    "price_local": round(price, 4),
                    "effective_from": str(obs_date),
                    "effective_to": str(month_end),
                    "observation_date": str(obs_date),
                    "source_url": article_link,
                }
            )
            r_row["observation_hash"] = make_hash(r_row)
            rows.append(r_row)

    return rows


def _wp_get(session, url: str, max_retries: int = 3) -> requests.Response | None:
    """GET with retry on 429."""
    for attempt in range(max_retries):
        try:
            resp = session.get(url, timeout=30)
            if resp.status_code == 429:
                wait = int(resp.headers.get("Retry-After", 3 * (attempt + 1)))
                print(f"  [png_iccc] Rate limited, waiting {wait}s...")
                time.sleep(wait)
                continue
            return resp
        except Exception as e:
            print(f"  [png_iccc] Request error (attempt {attempt + 1}): {e}")
            time.sleep(2)
    return None


def _wp_session() -> requests.Session:
    """Session for ICCC WP REST API — minimal headers to avoid WAF blocks."""
    s = requests.Session()
    s.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "application/json",
        }
    )
    return s


def fetch_png_iccc(cutoff: date) -> pd.DataFrame:
    """Fetch PNG ICCC indicative retail fuel prices via WP REST API.

    ICCC prices are state-controlled and published monthly. This fetcher
    forward-fills each monthly price across daily observation dates from the
    effective date through the end of the month (capped at today).
    """
    print("  [png_iccc] Fetching PNG ICCC data (WP REST API)...")
    print(f"  [png_iccc] Cutoff: {cutoff}")

    session = _wp_session()

    # --- listing phase: paginate through WP posts ---
    posts: list[dict] = []
    page_num = 1
    while True:
        url = f"{_WP_LIST_URL}&page={page_num}"
        resp = _wp_get(session, url)
        if resp is None:
            print(f"  [png_iccc] Listing page {page_num} failed after retries")
            break
        if resp.status_code == 400:
            break  # past last page
        try:
            resp.raise_for_status()
        except Exception as e:
            print(f"  [png_iccc] Listing page {page_num} error: {e}")
            break

        batch = resp.json()
        if not batch:
            break
        posts.extend(batch)

        total = int(resp.headers.get("X-WP-Total", len(posts)))
        if len(posts) >= total:
            break
        page_num += 1
        time.sleep(0.5)

    print(f"  [png_iccc] Found {len(posts)} posts via WP API")
    today = date.today()
    all_rows: list[dict] = []

    # --- content phase: fetch each post and parse table ---
    for post in posts:
        post_id = post["id"]
        article_link = post.get("link", "")
        content_url = (
            f"https://iccc.gov.pg/wp-json/wp/v2/posts/{post_id}"
            f"?_fields=id,date,title,content"
        )
        r = _wp_get(session, content_url)
        if r is None or r.status_code != 200:
            time.sleep(0.5)
            continue
        try:
            data = r.json()
            html = data.get("content", {}).get("rendered", "")
            if not html:
                continue
        except Exception as e:
            print(f"  [png_iccc] Content parse error (id={post_id}): {e}")
            continue

        monthly_rows = _parse_png_table(html, article_link)

        # Forward-fill monthly rows to daily observations.
        expanded: list[dict] = []
        for r in monthly_rows:
            try:
                eff_from = date.fromisoformat(str(r.get("effective_from") or ""))
                eff_to = date.fromisoformat(str(r.get("effective_to") or ""))
            except Exception:
                continue

            fill_start = max(eff_from, cutoff + timedelta(days=1))
            fill_end = min(eff_to, today)
            if fill_end < fill_start:
                continue

            d = fill_start
            while d <= fill_end:
                rr = r.copy()
                rr["observation_date"] = str(d)
                rr["observation_hash"] = make_hash(rr)
                expanded.append(rr)
                d += timedelta(days=1)

        if expanded:
            all_rows.extend(expanded)
            dates = {r["observation_date"] for r in expanded}
            print(
                f"  [png_iccc] Post {post_id}: {len(expanded)} rows "
                f"({min(dates)} to {max(dates)})"
            )

        time.sleep(0.3)

    if all_rows:
        print(f"  [png_iccc] {len(all_rows)} total new rows")
    else:
        print("  [png_iccc] No new rows")
    return pd.DataFrame(all_rows) if all_rows else pd.DataFrame()
