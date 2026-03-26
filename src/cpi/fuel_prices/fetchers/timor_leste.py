"""Timor-Leste ANP daily fuel price fetcher."""

# ruff: noqa: E402
SOURCE_META = [
    {
        "fetcher_fn": "fetch_timor_anp",
        "country": "Timor-Leste",
        "source_name": "ANP Daily Fuel Price",
        "url": "https://www.anp.tl/category/daily-fuel-price/",
        "description": "Official government regulator (Autoridade Nacional do Petróleo). Daily station-level fuel prices are retrieved from the WordPress API and parsed from embedded HTML tables; official regulated prices. National average computed from station data.",
        "extraction_method": ["API", "Web scraping"],
        "products": ["Gasoline (Regular Petrol)", "Diesel"],
        "source_keys": ["tl_anp_daily_fuel_price"],
        "publishes_on": "Daily",
        "notes": "WordPress API posts endpoint is paginated and scanned historically. Date prefers post title and falls back to slug parsing. Price range USD 0.50–5.00/L.",
    },
]

import re
import time
from datetime import date
from html import unescape

import pandas as pd
from bs4 import BeautifulSoup

from ..utils import MONTH_MAP_EN, get_session, make_hash, make_template

_CATEGORY_URL = "https://www.anp.tl/category/daily-fuel-price/"
_WP_CATEGORY_ID = 65
_WP_POSTS_URL = "https://www.anp.tl/wp-json/wp/v2/posts"
_WP_POST_FIELDS = "id,date,link,slug,title,content"

_TMPL_TL = make_template(
    country="Timor-Leste",
    wb_iso3="TLS",
    source_key="tl_anp_daily_fuel_price",
    source_name="Timor-Leste ANP Daily Fuel Price",
    source_url="https://www.anp.tl/category/daily-fuel-price/",
    currency="USD",
    unit="L",
    subnational_area="National",
    publication_frequency="daily",
    observation_method="reported",
    tax_status="tax_inclusive",
)

_TL_PRODUCTS = [
    ("Petrol", "gasoline", "regular", None, r"(?i)petrol|gasoline|benzina"),
    ("Diesel", "diesel", "regular", None, r"(?i)diesel|gasoleo"),
]


def _parse_date_from_slug(slug: str) -> date | None:
    """Parse date from ANP URL slugs like 'daily-fuel-price-15-17-march-2025'."""
    # Extract the last day, month name, and year from the slug
    m = re.search(r"(\d{1,2})-(\w+)-(\d{4})/?$", slug)
    if m:
        day, month_name, year = int(m.group(1)), m.group(2).lower(), int(m.group(3))
        month_num = MONTH_MAP_EN.get(month_name)
        if month_num:
            try:
                return date(year, month_num, day)
            except ValueError:
                pass
    # Fallback: try extracting from longer patterns
    m = re.search(r"(\d{1,2})-(\d{1,2})-(\w+)-(\d{4})/?$", slug)
    if m:
        day2, month_name, year = int(m.group(2)), m.group(3).lower(), int(m.group(4))
        month_num = MONTH_MAP_EN.get(month_name)
        if month_num:
            try:
                return date(year, month_num, day2)
            except ValueError:
                pass
    return None


def _parse_date_from_title(title_text: str) -> date | None:
    """Parse date from listing titles like 'Daily Fuel Price – 15-17 March 2025'."""
    cleaned = unescape(title_text).replace("–", "-").strip().lower()
    m = re.search(r"(\d{1,2})(?:\s*-\s*(\d{1,3}))?\s+([a-z]+)\s+(\d{4})", cleaned)
    if not m:
        return None
    day1 = int(m.group(1))
    day2 = int(m.group(2)) if m.group(2) else day1
    month_name = m.group(3)
    year = int(m.group(4))
    month_num = MONTH_MAP_EN.get(month_name)
    if not month_num:
        return None
    try:
        return date(year, month_num, day2)
    except ValueError:
        return None


def _parse_price_cell(cell_text: str) -> float | None:
    """Parse ANP price cells like '$1,25' into floats."""
    raw = cell_text.replace("$", "").strip()
    if "," in raw and "." not in raw:
        raw = raw.replace(",", ".")
    try:
        value = float(re.sub(r"[^0-9.]", "", raw))
    except (ValueError, TypeError):
        return None
    return value if 0.5 <= value <= 5.0 else None


def _fetch_api_posts(session, cutoff: date) -> list[dict]:
    """Fetch Timor-Leste daily fuel price posts from the WordPress API."""
    posts: list[dict] = []
    page = 1
    total_pages = 1

    while page <= total_pages:
        try:
            resp = session.get(
                _WP_POSTS_URL,
                params={
                    "categories": _WP_CATEGORY_ID,
                    "page": page,
                    "per_page": 100,
                    "_fields": _WP_POST_FIELDS,
                },
                timeout=30,
            )
            resp.raise_for_status()
        except Exception as e:
            print(f"  [tl_anp] Could not fetch API page {page}: {e}")
            break

        try:
            total_pages = int(resp.headers.get("X-WP-TotalPages", total_pages))
        except (TypeError, ValueError):
            total_pages = max(total_pages, page)

        page_posts = resp.json()
        stop_after_page = False
        for post in page_posts:
            title_text = (post.get("title") or {}).get("rendered", "")
            slug = post.get("slug", "")
            obs_date = _parse_date_from_title(title_text)
            if obs_date is None:
                obs_date = _parse_date_from_slug(slug)
            if obs_date is None:
                continue
            if obs_date <= cutoff:
                stop_after_page = True
                continue
            posts.append(
                {
                    "observation_date": obs_date,
                    "source_url": post.get("link") or _CATEGORY_URL,
                    "content_html": (post.get("content") or {}).get("rendered", ""),
                }
            )

        if stop_after_page:
            break
        page += 1
        time.sleep(0.2)

    posts.sort(key=lambda item: item["observation_date"], reverse=True)
    return posts


def _extract_prices_from_post_html(
    content_html: str, source_url: str, obs_date: date
) -> list[dict]:
    """Extract national-average fuel prices from API post HTML content."""
    soup = BeautifulSoup(content_html, "lxml")
    rows_out = []

    for table in soup.find_all("table"):
        rows_html = table.find_all("tr")
        if len(rows_html) < 3:
            continue
        header_row_idx = None
        headers: list[str] = []
        for idx, row in enumerate(rows_html[:3]):
            row_headers = [
                c.get_text(strip=True).lower() for c in row.find_all(["th", "td"])
            ]
            if any(
                re.search(prod_pat, header)
                for _, _, _, _, prod_pat in _TL_PRODUCTS
                for header in row_headers
            ):
                header_row_idx = idx
                headers = row_headers
                break
        if header_row_idx is None:
            continue

        for prod_name, family, qg, ron, prod_pat in _TL_PRODUCTS:
            price_col = next(
                (i for i, h in enumerate(headers) if re.search(prod_pat, h)), None
            )
            if price_col is None:
                continue

            prices = []
            for row in rows_html[header_row_idx + 1 :]:
                cells = [c.get_text(strip=True) for c in row.find_all(["th", "td"])]
                cell_offset = max(len(cells) - len(headers), 0)
                value_col = price_col + cell_offset
                if value_col >= len(cells):
                    continue
                # Municipality/station cells are intentionally ignored for now because the
                # current source contract emits national averages only. If we later need
                # location-level observations, retain those cells here before aggregation.
                p = _parse_price_cell(cells[value_col])
                if p is not None:
                    prices.append(p)

            if not prices:
                continue

            avg_price = round(sum(prices) / len(prices), 4)
            r = _TMPL_TL.copy()
            r.update(
                {
                    "fuel_family": family,
                    "fuel_product": prod_name,
                    "quality_group": qg,
                    "octane_ron": ron,
                    "price_local": avg_price,
                    "observation_date": str(obs_date),
                    "source_url": source_url,
                }
            )
            r["observation_hash"] = make_hash(r)
            rows_out.append(r)

    return rows_out


def fetch_timor_anp(cutoff: date) -> pd.DataFrame:
    """Fetch Timor-Leste ANP daily fuel prices from the WordPress API."""
    print("  [tl_anp] Fetching Timor-Leste ANP data...")
    print(f"  [tl_anp] Cutoff: {cutoff}")

    session = get_session()

    posts = _fetch_api_posts(session, cutoff)
    if not posts:
        print("  [tl_anp] No API posts after cutoff")
        return pd.DataFrame()
    print(f"  [tl_anp] API posts after cutoff: {len(posts)}")

    all_rows = []
    for post in posts:
        rows = _extract_prices_from_post_html(
            post["content_html"], post["source_url"], post["observation_date"]
        )
        if rows:
            all_rows.extend(rows)
            print(f"  [tl_anp] {post['observation_date']}: {len(rows)} products")
        time.sleep(0.1)

    if all_rows:
        print(f"  [tl_anp] {len(all_rows)} new rows")
    else:
        print("  [tl_anp] No new rows")
    return pd.DataFrame(all_rows) if all_rows else pd.DataFrame()
