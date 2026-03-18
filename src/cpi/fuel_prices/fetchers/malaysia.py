"""Malaysia MOF weekly petroleum retail price fetcher + data.gov.my open data."""

# ruff: noqa: E402
SOURCE_META = [
    {
        "fetcher_fn": "fetch_malaysia_mof",
        "country": "Malaysia",
        "source_name": "Ministry of Finance Weekly Petroleum Prices",
        "url": "https://www.mof.gov.my/portal/en/news/press-release/retail-price",
        "description": "Official government (Malaysia Ministry of Finance). Weekly retail petroleum prices via press releases. Covers Peninsular + East Malaysia.",
        "extraction_method": ["Web scraping"],
        "products": [
            "Gasoline RON95 (Premium)",
            "Gasoline RON97 (Super Premium)",
            "Diesel (Peninsular)",
            "Diesel (East Malaysia)",
        ],
        "source_keys": ["my_mof_weekly_petroleum"],
        "publishes_on": "Wednesday",
        "notes": "Effective date extracted from URL slug (English and Malay date patterns). Generates one row per day within each weekly window. Price range MYR 1.0–6.0/L.",
    },
    {
        "fetcher_fn": "fetch_malaysia_datagovmy",
        "country": "Malaysia",
        "source_name": "data.gov.my Weekly Fuel Prices",
        "url": "https://data.gov.my/data-catalogue/fuelprice",
        "description": "Official Malaysia open data portal (data.gov.my). Weekly retail fuel prices from Ministry of Finance via structured CSV/parquet.",
        "extraction_method": ["Parquet/CSV download"],
        "products": [
            "Gasoline RON95 (Premium)",
            "Gasoline RON97 (Super Premium)",
            "Diesel (Peninsular Malaysia)",
        ],
        "source_keys": ["my_datagovmy_weekly_fuelprice"],
        "publishes_on": "Wednesday",
        "notes": "Downloads parquet (preferred) or CSV from storage.data.gov.my. Filters series_type=level. Price range MYR 1.0–6.0/L. CC BY 4.0 license.",
    },
]

import io
import re
import time
from datetime import date, timedelta

import pandas as pd
from bs4 import BeautifulSoup

from ..utils import get_session, make_hash, make_template

_TMPL_MY = make_template(
    country="Malaysia",
    wb_iso3="MYS",
    source_key="my_mof_weekly_petroleum",
    source_name="Malaysia Ministry of Finance — Weekly Petroleum Retail Prices",
    source_url="https://www.mof.gov.my/portal/en/news/press-release/retail-price",
    currency="MYR",
    unit="L",
    subnational_area="National",
    publication_frequency="weekly",
    observation_method="reported",
    tax_status="tax_inclusive",
)

_PRODUCTS = [
    ("RON95", "gasoline", "premium", 95),
    ("RON97", "gasoline", "super_premium", 97),
    ("Diesel (Peninsular Malaysia)", "diesel", "regular", None),
    ("Diesel (East Malaysia)", "diesel", "regular", None),
]

_ENGLISH_MONTHS = {
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
}

_MALAY_MONTHS = {
    "januari": 1,
    "februari": 2,
    "mac": 3,
    "april": 4,
    "mei": 5,
    "jun": 6,
    "julai": 7,
    "ogos": 8,
    "september": 9,
    "oktober": 10,
    "november": 11,
    "disember": 12,
}


def _parse_date_from_slug(slug: str) -> tuple[date | None, date | None]:
    """Extract (eff_from, eff_to) from a MOF URL slug."""
    en_pat = (
        r"from-(\d{1,2})-(january|february|march|april|may|june|july|august|"
        r"september|october|november|december)-(\d{4})-to-(\d{1,2})-"
        r"(january|february|march|april|may|june|july|august|"
        r"september|october|november|december)-(\d{4})"
    )
    m = re.search(en_pat, slug, re.IGNORECASE)
    if m:
        try:
            d1, mo1, y1 = int(m.group(1)), m.group(2).lower(), int(m.group(3))
            d2, mo2, y2 = int(m.group(4)), m.group(5).lower(), int(m.group(6))
            return (
                date(y1, _ENGLISH_MONTHS[mo1], d1),
                date(y2, _ENGLISH_MONTHS[mo2], d2),
            )
        except (KeyError, ValueError):
            pass

    # Malay slug: ...tempoh-12-november-2025-hingga-18-november-2025
    ms_pat = (
        r"tempoh-(\d{1,2})-(januari|februari|mac|april|mei|jun|julai|ogos|"
        r"september|oktober|november|disember)-(\d{4})-hingga-(\d{1,2})-"
        r"(januari|februari|mac|april|mei|jun|julai|ogos|"
        r"september|oktober|november|disember)-(\d{4})"
    )
    m = re.search(ms_pat, slug, re.IGNORECASE)
    if m:
        try:
            d1, mo1, y1 = int(m.group(1)), m.group(2).lower(), int(m.group(3))
            d2, mo2, y2 = int(m.group(4)), m.group(5).lower(), int(m.group(6))
            return (
                date(y1, _MALAY_MONTHS[mo1], d1),
                date(y2, _MALAY_MONTHS[mo2], d2),
            )
        except (KeyError, ValueError):
            pass

    # Malay slug variant: ...meningkat-dari-5-mac-2026-hingga-11-mac-2026
    ms_pat2 = (
        r"dari-(\d{1,2})-(januari|februari|mac|april|mei|jun|julai|ogos|"
        r"september|oktober|november|disember)-(\d{4})-hingga-(\d{1,2})-"
        r"(januari|februari|mac|april|mei|jun|julai|ogos|"
        r"september|oktober|november|disember)-(\d{4})"
    )
    m = re.search(ms_pat2, slug, re.IGNORECASE)
    if m:
        try:
            d1, mo1, y1 = int(m.group(1)), m.group(2).lower(), int(m.group(3))
            d2, mo2, y2 = int(m.group(4)), m.group(5).lower(), int(m.group(6))
            return (
                date(y1, _MALAY_MONTHS[mo1], d1),
                date(y2, _MALAY_MONTHS[mo2], d2),
            )
        except (KeyError, ValueError):
            pass

    return None, None


def _extract_mof_prices(html: str) -> dict[str, float]:
    """Extract fuel prices from a Malaysia MOF article HTML.

    Locates each product keyword in plain body text and finds the closest
    'RM X.XX' value within 300 characters after the keyword.
    Returns dict: {product_name: price} in MYR/L.
    """
    soup = BeautifulSoup(html, "lxml")
    for tag in soup.find_all(["head", "script", "style"]):
        tag.decompose()
    text = soup.get_text(separator=" ")
    text = re.sub(r"\s+", " ", text)

    rm_prices: list[tuple[int, float]] = []
    for m in re.finditer(r"RM\s*([0-9]+\.[0-9]{2})", text, re.IGNORECASE):
        try:
            rm_prices.append((m.start(), float(m.group(1))))
        except ValueError:
            pass

    def find_price_after_keyword(
        keywords: list[str],
        min_val: float,
        max_val: float,
        exclude: list[float] | None = None,
    ) -> float | None:
        for kw in keywords:
            for km in re.finditer(re.escape(kw), text, re.IGNORECASE):
                pos = km.end()
                for rm_position, rm_val in rm_prices:
                    if rm_position < pos:
                        continue
                    if rm_position - pos > 300:
                        break
                    if min_val <= rm_val <= max_val:
                        if exclude and rm_val in exclude:
                            continue
                        return rm_val
        return None

    prices: dict[str, float] = {}

    prices["RON95"] = find_price_after_keyword(
        [
            "non-subsidised RON95",
            "RON95 tanpa subsidi",
            "RON 95 tanpa",
            "petrol RON95",
            "RON95 petrol",
            "RON95",
        ],
        min_val=1.5,
        max_val=5.0,
        exclude=[1.99],
    )

    prices["RON97"] = find_price_after_keyword(
        ["RON97 petrol", "petrol RON97", "RON97"], min_val=1.5, max_val=6.0
    )

    prices["Diesel (Peninsular Malaysia)"] = find_price_after_keyword(
        [
            "Peninsular Malaysia",
            "Semenanjung Malaysia",
            "diesel in Peninsular",
            "diesel di Semenanjung",
        ],
        min_val=1.5,
        max_val=6.0,
    )

    prices["Diesel (East Malaysia)"] = find_price_after_keyword(
        [
            "Sabah, Sarawak and Labuan",
            "Sabah, Sarawak",
            "East Malaysia",
            "Sabah dan Sarawak",
        ],
        min_val=1.0,
        max_val=5.0,
    )

    return {k: v for k, v in prices.items() if v is not None}


def fetch_malaysia_mof(cutoff: date) -> pd.DataFrame:
    """Fetch Malaysia MOF weekly petroleum retail prices.

    Paginates through the MOF English portal listing, fetches each article,
    extracts prices from HTML body text, and generates one row per product
    per day within the effective date range.
    """
    print("  [mof] Fetching Malaysia MOF data...")
    print(f"  [mof] Cutoff: {cutoff}")

    session = get_session()
    today = date.today()

    base_listing = "https://www.mof.gov.my/portal/en/news/press-release/retail-price"
    article_urls = []
    seen: set[str] = set()

    for start in range(0, 50, 5):
        try:
            url = f"{base_listing}?start={start}"
            resp = session.get(url, timeout=20)
            if resp.status_code != 200:
                break
            soup = BeautifulSoup(resp.content, "lxml")
            links = [
                a["href"]
                for a in soup.find_all("a", href=True)
                if "retail-price/" in a["href"]
                and a["href"] != "/portal/en/news/press-release/retail-price"
            ]
            links = list(
                dict.fromkeys(
                    "https://www.mof.gov.my" + li if li.startswith("/") else li
                    for li in links
                )
            )
            added_any = False
            for li in links:
                if li not in seen:
                    seen.add(li)
                    article_urls.append(li)
                    added_any = True
            if not added_any:
                break
        except Exception as e:
            print(f"  [mof] Listing fetch error at start={start}: {e}")
            break
        time.sleep(0.5)

    print(f"  [mof] Found {len(article_urls)} article URLs")

    all_rows = []

    for art_url in article_urls:
        eff_from, eff_to = _parse_date_from_slug(art_url)
        if eff_from is None:
            print(f"  [mof] Could not parse date from: {art_url}")
            continue

        if eff_to <= cutoff:
            continue

        try:
            resp = session.get(art_url, timeout=20)
            if resp.status_code != 200:
                print(f"  [mof] HTTP {resp.status_code}: {art_url}")
                continue
            html = resp.text
        except Exception as e:
            print(f"  [mof] Fetch error {art_url}: {e}")
            continue

        prices_found = _extract_mof_prices(html)

        if not prices_found:
            print(f"  [mof] {eff_from}→{eff_to}: no prices from {art_url}")
            time.sleep(0.3)
            continue

        rows_added = 0
        for prod_name, family, qg, ron in _PRODUCTS:
            price = prices_found.get(prod_name)
            if price is None:
                continue
            d = max(eff_from, cutoff + timedelta(days=1))
            while d <= min(eff_to, today):
                r = _TMPL_MY.copy()
                r.update(
                    {
                        "fuel_family": family,
                        "fuel_product": prod_name,
                        "quality_group": qg,
                        "octane_ron": ron,
                        "price_local": price,
                        "effective_from": str(eff_from),
                        "effective_to": str(eff_to),
                        "observation_date": str(d),
                        "source_url": art_url,
                    }
                )
                r["observation_hash"] = make_hash(r)
                all_rows.append(r)
                rows_added += 1
                d += timedelta(days=1)

        print(
            f"  [mof] {eff_from}→{eff_to}: "
            f"{len(prices_found)} products, {rows_added} rows "
            f"({', '.join(f'{k}={v:.2f}' for k, v in prices_found.items())})"
        )
        time.sleep(0.4)

    if all_rows:
        print(f"  [mof] {len(all_rows)} new rows total")
    else:
        print("  [mof] No new rows")
    return pd.DataFrame(all_rows) if all_rows else pd.DataFrame()


# ── data.gov.my weekly fuel prices ───────────────────────────────────────────

_DATAGOVMY_PARQUET_URL = "https://storage.data.gov.my/commodities/fuelprice.parquet"
_DATAGOVMY_CSV_URL = "https://storage.data.gov.my/commodities/fuelprice.csv"

_TMPL_MY_DATAGOVMY = make_template(
    country="Malaysia",
    wb_iso3="MYS",
    source_key="my_datagovmy_weekly_fuelprice",
    source_name="data.gov.my — Weekly Fuel Prices",
    source_url="https://data.gov.my/data-catalogue/fuelprice",
    currency="MYR",
    unit="L",
    subnational_area="National",
    publication_frequency="weekly",
    observation_method="reported",
    tax_status="tax_inclusive",
    source_type="official",
)

# (column_name, fuel_product, fuel_family, quality_group, octane_ron, subnational)
_DATAGOVMY_PRODUCTS = [
    ("ron95", "RON95", "gasoline", "premium", 95, "National"),
    ("ron97", "RON97", "gasoline", "super_premium", 97, "National"),
    (
        "diesel",
        "Diesel (Peninsular Malaysia)",
        "diesel",
        "regular",
        None,
        "Peninsular Malaysia",
    ),
]


def fetch_malaysia_datagovmy(cutoff: date) -> pd.DataFrame:
    """Fetch Malaysia weekly fuel prices from data.gov.my (parquet/CSV)."""
    print("  [datagovmy] Fetching Malaysia data.gov.my fuel prices...")
    print(f"  [datagovmy] Cutoff: {cutoff}")

    session = get_session()
    df = None

    # Try parquet first
    try:
        resp = session.get(_DATAGOVMY_PARQUET_URL, timeout=60)
        resp.raise_for_status()
        df = pd.read_parquet(io.BytesIO(resp.content))
        print("  [datagovmy] Loaded parquet successfully")
    except Exception as e:
        print(f"  [datagovmy] Parquet failed ({e}), trying CSV...")

    # Fall back to CSV
    if df is None:
        try:
            resp = session.get(_DATAGOVMY_CSV_URL, timeout=60)
            resp.raise_for_status()
            df = pd.read_csv(io.BytesIO(resp.content), low_memory=False)
            print("  [datagovmy] Loaded CSV successfully")
        except Exception as e:
            print(f"  [datagovmy] CSV also failed: {e}")
            return pd.DataFrame()

    if df is None or df.empty:
        print("  [datagovmy] Empty dataset")
        return pd.DataFrame()

    # Filter to level rows only (exclude change_weekly)
    if "series_type" in df.columns:
        df = df[df["series_type"] == "level"]

    # Parse dates
    df["_date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["_date"])
    df["_date_d"] = df["_date"].dt.date

    # Filter to dates after cutoff
    df = df[df["_date_d"] > cutoff]
    if df.empty:
        print("  [datagovmy] No rows after cutoff")
        return pd.DataFrame()

    print(f"  [datagovmy] {len(df)} date rows to process")

    all_rows: list[dict] = []

    for _, row in df.iterrows():
        obs_date = row["_date_d"]
        for col, prod_name, family, qg, ron, subnational in _DATAGOVMY_PRODUCTS:
            if col not in row.index:
                continue
            try:
                price = float(row[col])
            except (ValueError, TypeError):
                continue
            if pd.isna(price) or not (1.0 <= price <= 6.0):
                continue

            r = _TMPL_MY_DATAGOVMY.copy()
            r.update(
                {
                    "fuel_family": family,
                    "fuel_product": prod_name,
                    "quality_group": qg,
                    "octane_ron": ron,
                    "subnational_area": subnational,
                    "price_local": round(price, 4),
                    "effective_from": str(obs_date),
                    "effective_to": str(obs_date),
                    "observation_date": str(obs_date),
                    "source_url": _DATAGOVMY_PARQUET_URL,
                }
            )
            r["observation_hash"] = make_hash(r)
            all_rows.append(r)

    if all_rows:
        print(f"  [datagovmy] {len(all_rows)} new rows total")
    else:
        print("  [datagovmy] No new rows")
    return pd.DataFrame(all_rows) if all_rows else pd.DataFrame()
