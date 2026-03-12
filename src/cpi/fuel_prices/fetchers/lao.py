"""Lao State Fuel Company provincial price fetcher + KPL national price notices."""

# ruff: noqa: E402
SOURCE_META = [
    {
        "fetcher_fn": "fetch_lao",
        "country": "Lao PDR",
        "source_name": "Lao State Fuel Company Provincial Prices",
        "url": "https://www.laostatefuel.com/en/gas-price.html",
        "description": "Semi-official (Lao State Fuel Company, state enterprise). Monthly retail prices by province as HTML tables. English interface available.",
        "extraction_method": ["Web scraping"],
        "products": ["Gasoline 95 (Premium, RON 95)", "Gasoline (Regular)", "Diesel"],
        "source_keys": ["lao_state_fuel_oil_prices"],
        "publishes_on": "Monthly (irregular, price revisions)",
        "notes": "Parses paginated HTML tables with 'province' and 'date' columns. Subnational province-level data. Price range LAK 5,000–100,000/L. NOTE: site appears stale/outdated in recent checks; KPL notices may be more current.",
    },
    {
        "fetcher_fn": "fetch_lao_kpl",
        "country": "Lao PDR",
        "source_name": "KPL — Ministry of Industry & Commerce Fuel Price Notices",
        "url": "https://kpl.gov.la/En/News.aspx?cat=13",
        "description": "Official (Lao News Agency / Ministry of Industry and Commerce). Fuel price adjustment notices published as news articles with exact kip/litre values and effective dates.",
        "extraction_method": ["Web scraping"],
        "products": ["Gasoline (Premium/RON 95)", "Gasoline (Regular)", "Diesel"],
        "source_keys": ["lao_kpl_fuel_notices"],
        "publishes_on": "Per price adjustment (roughly 1–3x/month)",
        "notes": "Scans KPL General news listing for fuel-price articles; extracts prices via regex. National-level (no subnational breakdown).",
    },
]

import re
import time
from datetime import date

import pandas as pd
from bs4 import BeautifulSoup

from ..utils import get_session, make_hash, make_template

# ── Lao State Fuel Company (provincial prices) ────────────────────────────────

_TMPL_LAO = make_template(
    country="Lao PDR",
    wb_iso3="LAO",
    source_key="lao_state_fuel_oil_prices",
    source_name="Lao State Fuel Company — Provincial Retail Prices",
    source_url="https://www.laostatefuel.com/en/gas-price.html",
    currency="LAK",
    unit="L",
    consumer_segment="retail",
    publication_frequency="monthly",
    observation_method="reported",
    tax_status="tax_inclusive",
)

_PRODUCT_COLS = {
    "gasoline 95": ("Gasoline 95", "gasoline", "premium", 95),
    "95": ("Gasoline 95", "gasoline", "premium", 95),
    "regular": ("Regular Gasoline", "gasoline", "regular", None),
    "diesel": ("Diesel", "diesel", "regular", None),
}

_BASE_URL = "https://www.laostatefuel.com/en/gas-price.html"
_MAX_PAGES = 10  # incremental cap; increase for historical backfills


def _parse_lao_page(soup: BeautifulSoup, cutoff: date) -> tuple[list[dict], bool]:
    """Parse one page of laostatefuel.com tables.

    Returns (rows, stop) where stop=True means all dates were <= cutoff so
    further pages are not needed.
    """
    rows_out: list[dict] = []
    page_dates: list[date] = []
    found_table = False

    for table in soup.find_all("table"):
        trows = table.find_all("tr")
        if len(trows) < 3:
            continue

        header_cells = trows[0].find_all(["th", "td"])
        headers = [c.get_text(strip=True).lower() for c in header_cells]

        if "province" not in " ".join(headers) or "date" not in " ".join(headers):
            continue

        try:
            prov_col = next(i for i, h in enumerate(headers) if "province" in h)
            date_col = next(
                i for i, h in enumerate(headers) if "date" in h and "province" not in h
            )
        except StopIteration:
            continue

        price_cols: dict[int, tuple] = {}
        for col_idx, h in enumerate(headers):
            for key, meta in _PRODUCT_COLS.items():
                if key in h and col_idx not in (prov_col, date_col):
                    price_cols[col_idx] = meta
                    break

        if not price_cols:
            continue

        found_table = True
        for row in trows[1:]:
            cells = row.find_all(["th", "td"])
            if len(cells) <= max(date_col, prov_col):
                continue
            cell_texts = [c.get_text(strip=True) for c in cells]

            province = cell_texts[prov_col] if prov_col < len(cell_texts) else None
            date_str = cell_texts[date_col] if date_col < len(cell_texts) else None

            if not province or not date_str:
                continue

            m = re.match(r"(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})", date_str)
            if not m:
                continue
            try:
                obs_date = date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
            except ValueError:
                continue

            page_dates.append(obs_date)

            if obs_date <= cutoff:
                continue

            for col_idx, (prod_name, family, qg, ron) in price_cols.items():
                if col_idx >= len(cell_texts):
                    continue
                price_str = cell_texts[col_idx]
                try:
                    price = float(re.sub(r"[^0-9.]", "", price_str))
                    if price < 5000 or price > 100_000:
                        continue
                except (ValueError, TypeError):
                    continue

                r = _TMPL_LAO.copy()
                r.update(
                    {
                        "subnational_area": province,
                        "fuel_family": family,
                        "fuel_product": prod_name,
                        "quality_group": qg,
                        "octane_ron": ron,
                        "price_local": price,
                        "effective_from": str(obs_date),
                        "effective_to": str(obs_date),
                        "observation_date": str(obs_date),
                        "source_url": _BASE_URL,
                    }
                )
                r["observation_hash"] = make_hash(r)
                rows_out.append(r)

    if not found_table:
        return rows_out, True

    stop = bool(page_dates) and all(d <= cutoff for d in page_dates)
    return rows_out, stop


def fetch_lao(cutoff: date, max_pages: int = _MAX_PAGES) -> pd.DataFrame:
    """Fetch Lao State Fuel provincial prices from laostatefuel.com (paginated)."""
    print("  [lao] Fetching Lao PDR data...")
    print(f"  [lao] Cutoff: {cutoff}, max_pages: {max_pages}")

    session = get_session()
    all_rows: list[dict] = []

    for page in range(1, max_pages + 1):
        url = _BASE_URL if page == 1 else f"{_BASE_URL}/?page={page}"
        try:
            resp = session.get(url, timeout=30)
            resp.raise_for_status()
        except Exception as e:
            print(f"  [lao] Could not fetch page {page}: {e}")
            break

        soup = BeautifulSoup(resp.content, "lxml")
        page_rows, stop = _parse_lao_page(soup, cutoff)
        all_rows.extend(page_rows)

        if stop:
            print(f"  [lao] Stopped at page {page} (all dates <= cutoff)")
            break

        if page < max_pages:
            time.sleep(0.5)

    if all_rows:
        max_d = max(r["observation_date"] for r in all_rows)
        print(f"  [lao] Collected {len(all_rows)} new rows (max date: {max_d})")
    else:
        print(f"  [lao] No new rows after cutoff {cutoff}")

    return pd.DataFrame(all_rows) if all_rows else pd.DataFrame()


# ── KPL national fuel price notices ──────────────────────────────────────────

_TMPL_KPL = make_template(
    country="Lao PDR",
    wb_iso3="LAO",
    source_key="lao_kpl_fuel_notices",
    source_name="KPL — MoIC Fuel Price Notice",
    source_url="https://kpl.gov.la/En/News.aspx?cat=13",
    currency="LAK",
    unit="L",
    consumer_segment="retail",
    publication_frequency="irregular",
    observation_method="reported",
    tax_status="tax_inclusive",
)

_KPL_LISTING_URL = "https://kpl.gov.la/En/News.aspx?cat=13&page={page}"
_KPL_ARTICLE_URL = "https://kpl.gov.la/En/detail.aspx?id={article_id}"

_FUEL_TITLE_KEYWORDS = re.compile(
    r"\b(fuel|petrol|petroleum|gasoline|diesel|gas price)\b", re.IGNORECASE
)

_KPL_PRODUCTS = [
    # (regex pattern, prod_name, family, quality_group, octane_ron)
    (re.compile(r"premium\s+gasoline", re.I), "Gasoline 95", "gasoline", "premium", 95),
    (
        re.compile(r"gasoline\s+95|ron\s*95|octane.{0,5}95", re.I),
        "Gasoline 95",
        "gasoline",
        "premium",
        95,
    ),
    (
        re.compile(r"regular\s+gasoline|unleaded\s+petrol|gasoline\s+(?!9)", re.I),
        "Regular Gasoline",
        "gasoline",
        "regular",
        None,
    ),
    (re.compile(r"\bdiesel\b", re.I), "Diesel", "diesel", "regular", None),
]

_PRICE_RE = re.compile(r"([\d,]+)\s*kip\s*(?:per\s*(?:liter|litre|l))?", re.IGNORECASE)

_NEW_PRICE_RE = re.compile(r"\bto\s+([\d,]+)\s*kip\b", re.IGNORECASE)

_EFFECTIVE_DATE_RE = re.compile(
    r"effective(?:\s+from)?\s+(?:[^\d]*?)"
    r"(\w+\s+\d{1,2},?\s+\d{4}|\d{1,2}\s+\w+\s+\d{4}|\d{1,2}[/\-.]\d{1,2}[/\-.]\d{4})",
    re.IGNORECASE,
)

_MONTH_MAP = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}


def _parse_kpl_date(text: str) -> date | None:
    """Try to parse a date string from various KPL formats."""
    text = text.strip().rstrip(",")
    # "March 4, 2026" or "March 4 2026"
    m = re.match(r"([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})", text)
    if m:
        mon = _MONTH_MAP.get(m.group(1).lower())
        if mon:
            try:
                return date(int(m.group(3)), mon, int(m.group(2)))
            except ValueError:
                pass
    # "4 March 2026"
    m = re.match(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", text)
    if m:
        mon = _MONTH_MAP.get(m.group(2).lower())
        if mon:
            try:
                return date(int(m.group(3)), mon, int(m.group(1)))
            except ValueError:
                pass
    # "04/03/2026" or "4-3-2026"
    m = re.match(r"(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})", text)
    if m:
        try:
            return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            pass
    # "3/4/2026" US-style: try both
    return None


def _extract_prices_from_article(text: str) -> list[dict]:
    """Extract product/price pairs from KPL article text (deduplicated per article).

    When a sentence reports a price change ("from X kip to Y kip"), uses Y (new price).
    """
    results = []
    seen: set[tuple] = set()
    sentences = re.split(r"[.\n]", text)
    for sent in sentences:
        sent = sent.strip()
        # Prefer "to X kip" (new price) over the first kip value (old price)
        new_m = _NEW_PRICE_RE.search(sent)
        if new_m:
            price_str = new_m.group(1)
        else:
            price_m = _PRICE_RE.search(sent)
            if not price_m:
                continue
            price_str = price_m.group(1)
        try:
            price = float(price_str.replace(",", ""))
        except ValueError:
            continue
        if price < 5_000 or price > 150_000:
            continue
        for pat, prod_name, family, qg, ron in _KPL_PRODUCTS:
            if pat.search(sent):
                key = (prod_name, price)
                if key in seen:
                    break
                seen.add(key)
                results.append(
                    {
                        "fuel_product": prod_name,
                        "fuel_family": family,
                        "quality_group": qg,
                        "octane_ron": ron,
                        "price_local": price,
                    }
                )
                break
    return results


def _listing_article_ids(soup: BeautifulSoup) -> list[tuple[int, str]]:
    """Return (article_id, title) pairs from a KPL listing page."""
    results = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        m = re.search(r"detail\.aspx\?id=(\d+)", href, re.IGNORECASE)
        if not m:
            continue
        article_id = int(m.group(1))
        title = a.get_text(strip=True)
        results.append((article_id, title))
    return results


def fetch_lao_kpl(cutoff: date, max_listing_pages: int = 20) -> pd.DataFrame:
    """Fetch Lao fuel price notices from KPL (Lao News Agency)."""
    print("  [lao_kpl] Fetching KPL fuel price notices...")
    print(f"  [lao_kpl] Cutoff: {cutoff}")

    session = get_session()
    all_rows: list[dict] = []
    seen_ids: set[int] = set()

    for list_page in range(1, max_listing_pages + 1):
        url = _KPL_LISTING_URL.format(page=list_page)
        try:
            resp = session.get(url, timeout=30)
            resp.raise_for_status()
        except Exception as e:
            print(f"  [lao_kpl] Could not fetch listing page {list_page}: {e}")
            break

        soup = BeautifulSoup(resp.content, "lxml")
        article_list = _listing_article_ids(soup)
        if not article_list:
            break

        new_on_page_ids: set[int] = set()
        new_on_page: list[tuple[int, str]] = []
        for aid, title in article_list:
            if (
                aid not in seen_ids
                and aid not in new_on_page_ids
                and _FUEL_TITLE_KEYWORDS.search(title)
            ):
                new_on_page.append((aid, title))
                new_on_page_ids.add(aid)
        seen_ids.update(aid for aid, _ in article_list)

        if not new_on_page:
            continue

        for article_id, title in new_on_page:
            art_url = _KPL_ARTICLE_URL.format(article_id=article_id)
            try:
                art_resp = session.get(art_url, timeout=30)
                art_resp.raise_for_status()
            except Exception as e:
                print(f"  [lao_kpl]   Could not fetch article {article_id}: {e}")
                continue

            art_soup = BeautifulSoup(art_resp.content, "lxml")
            article_text = art_soup.get_text(" ", strip=True)

            # Try to extract effective date from article body
            obs_date: date | None = None
            eff_m = _EFFECTIVE_DATE_RE.search(article_text)
            if eff_m:
                obs_date = _parse_kpl_date(eff_m.group(1))

            # Fall back: look for any date near "effective" or "took effect"
            if obs_date is None:
                for pat in [
                    r"took effect[^\d]*(\w+ \d{1,2},? \d{4})",
                    r"(?:on|from)\s+(\w+ \d{1,2},? \d{4})",
                    r"(?:on|from)\s+(\d{1,2}[/\-.]\d{1,2}[/\-.]\d{4})",
                ]:
                    fm = re.search(pat, article_text, re.IGNORECASE)
                    if fm:
                        obs_date = _parse_kpl_date(fm.group(1))
                        if obs_date:
                            break

            if obs_date is None:
                continue

            if obs_date <= cutoff:
                continue

            price_rows = _extract_prices_from_article(article_text)
            if not price_rows:
                continue

            for pr in price_rows:
                r = _TMPL_KPL.copy()
                r.update(pr)
                r.update(
                    {
                        "subnational_area": "National",
                        "effective_from": str(obs_date),
                        "effective_to": str(obs_date),
                        "observation_date": str(obs_date),
                        "source_url": art_url,
                    }
                )
                r["observation_hash"] = make_hash(r)
                all_rows.append(r)

            time.sleep(0.3)

        time.sleep(0.5)

    if all_rows:
        max_d = max(r["observation_date"] for r in all_rows)
        print(f"  [lao_kpl] Collected {len(all_rows)} new rows (max date: {max_d})")
    else:
        print(f"  [lao_kpl] No new rows after cutoff {cutoff}")

    return pd.DataFrame(all_rows) if all_rows else pd.DataFrame()
