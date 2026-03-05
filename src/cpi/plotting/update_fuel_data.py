#!/usr/bin/env python3
"""
update_fuel_data.py — Fix data quality issues and fetch 2026 data.

Reads eap_fuel_prices_pilot.csv, applies all fixes, attempts to fetch
updated data from stale official sources, and overwrites the CSV.

Usage:
    python src/cpi/plotting/update_fuel_data.py

Fixes applied:
    1a. Australia AUDc → AUD (÷100)
    1b. quality_group for diesel/kerosene rows
    1c. Japan ANRE kerosene 18L → L (÷18)
    1d. fuel_family inference for blank rows

Sources attempted:
    - Japan ANRE (Excel download)
    - Indonesia Pertamina (HTML current prices)
    - Malaysia MOF (weekly URL construction + HTML)
    - Cambodia MOC (sequential news ID scan)
    - Lao State Fuel (HTML table)
    - Korea Opinet (news/press release scraping)
    - Fiji FCCC (SPC PDF page)
    - Australia ACCC (ACCC press release)
"""

import hashlib
import re
import time
from datetime import date, datetime, timedelta
from io import BytesIO
from pathlib import Path

import urllib3

import pandas as pd
import requests
import requests.packages
from bs4 import BeautifulSoup

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ── Paths ──────────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parents[3]
CSV_PATH = (
    PROJECT_ROOT / "data" / "cpi" / "fuel_prices_pilot" / "eap_fuel_prices_pilot.csv"
)
SCRAPE_TS = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# ── Helpers ────────────────────────────────────────────────────────────────────


def make_hash(row: dict) -> str:
    """Generate a SHA-256 observation_hash from key identifying fields."""
    key = "|".join(
        [
            str(row.get("country", "")),
            str(row.get("source_key", "")),
            str(row.get("observation_date", "")),
            str(row.get("fuel_product", "")),
            str(row.get("subnational_area", "")),
            str(row.get("city", "")),
            str(row.get("price_local", "")),
        ]
    )
    return hashlib.sha256(key.encode()).hexdigest()


def base_row(source_key: str, df_existing: pd.DataFrame) -> dict:
    """Return a template dict with constant fields from the source's first row."""
    src = df_existing[df_existing["source_key"] == source_key].iloc[0]

    def val(col):
        v = src.get(col)
        return None if pd.isna(v) else v

    return {
        "country": val("country"),
        "wb_iso3": val("wb_iso3"),
        "subnational_area": val("subnational_area"),
        "city": val("city"),
        "fuel_family": None,
        "fuel_product": None,
        "quality_group": None,
        "octane_ron": None,
        "ethanol_pct": None,
        "sulfur_standard": None,
        "gas_type": None,
        "delivery_type": val("delivery_type"),
        "consumer_segment": val("consumer_segment"),
        "price_local": None,
        "currency": val("currency"),
        "unit": val("unit"),
        "tax_status": val("tax_status"),
        "source_key": source_key,
        "source_name": val("source_name"),
        "source_url": val("source_url"),
        "source_type": val("source_type"),
        "scrape_ts": SCRAPE_TS,
        "effective_from": None,
        "effective_to": None,
        "observation_date": None,
        "publication_frequency": val("publication_frequency"),
        "observation_method": val("observation_method"),
        "status": "Final",
        "notes": val("notes"),
        "observation_hash": None,
    }


def get_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(HEADERS)
    return s


def last_date(df_existing: pd.DataFrame, source_key: str) -> date:
    """Return the max observation_date for a given source."""
    src = df_existing[df_existing["source_key"] == source_key]
    return pd.to_datetime(src["observation_date"]).max().date()


# ── Step 1: Data Fixes ─────────────────────────────────────────────────────────


def fix_australia_units(df: pd.DataFrame) -> pd.DataFrame:
    """Convert AUDc (cents) → AUD (dollars) by dividing price by 100."""
    mask = df["currency"] == "AUDc"
    df.loc[mask, "price_local"] = df.loc[mask, "price_local"] / 100
    df.loc[mask, "currency"] = "AUD"
    print(
        f"  [fix_au] {mask.sum()} Australia AUDc rows → AUD (÷100). "
        f"Price range: {df.loc[mask, 'price_local'].min():.2f}–{df.loc[mask, 'price_local'].max():.2f}"
    )
    return df


def fix_quality_group(df: pd.DataFrame) -> pd.DataFrame:
    """Fill missing quality_group for diesel/kerosene rows."""
    # Simple direct-source fixes (fuel_product exact or prefix match)
    specs = [
        # (source_key, product_regex, quality_group)
        ("jp_anre_weekly_petroleum_2025", r"^Diesel$", "regular"),
        ("jp_anre_weekly_petroleum_2025", r"^Kerosene", "regular"),
        ("my_mof_weekly_petroleum", r"^Diesel", "regular"),
        ("ph_doe_retail_pump_prices", r"(?i)^diesel", "regular"),
        ("fiji_fccc_monthly_prices", r"^Diesel$", "regular"),
        ("fiji_fccc_monthly_prices", r"^Kerosene$", "regular"),
        (
            "fiji_fccc_monthly_prices",
            r"(?i)^(Autogas|Bulk LPG|\d+\.?\d* Kg Cylinder)$",
            "regular",
        ),
        ("kh_moc_fuel_notices", r"^Diesel$", "regular"),
        ("kr_opinet_weekly_national_sampled_2025", r"^Diesel", "regular"),
    ]
    for src, prod_pat, qg in specs:
        mask = (
            (df["source_key"] == src)
            & df["fuel_product"].str.match(prod_pat, na=False)
            & df["quality_group"].isna()
        )
        if mask.sum():
            df.loc[mask, "quality_group"] = qg
            print(
                f"  [fix_qg] {mask.sum()} rows → quality_group='{qg}' ({src}, /{prod_pat}/)"
            )

    # Pertamina diesel products: specific quality tiers
    pert_mask = df["source_key"] == "id_pertamina_jakarta_2025_series"
    pertamina_specs = [
        (r"^Biosolar", "regular"),
        (r"^Dexlite$", "premium"),
        (r"^Pertamina Dex$", "super_premium"),
    ]
    for pat, qg in pertamina_specs:
        mask = (
            pert_mask
            & df["fuel_product"].str.match(pat, na=False)
            & df["quality_group"].isna()
        )
        if mask.sum():
            df.loc[mask, "quality_group"] = qg
            print(
                f"  [fix_qg] {mask.sum()} Pertamina rows → quality_group='{qg}' (/{pat}/)"
            )

    return df


def fix_anre_kerosene_unit(df: pd.DataFrame) -> pd.DataFrame:
    """Convert Japan ANRE kerosene from per-18L can to per-litre."""
    mask = (df["unit"] == "18L") & (df["source_key"] == "jp_anre_weekly_petroleum_2025")
    before = df.loc[mask, "price_local"].mean()
    df.loc[mask, "price_local"] = df.loc[mask, "price_local"] / 18
    df.loc[mask, "unit"] = "L"
    after = df.loc[mask, "price_local"].mean()
    print(
        f"  [fix_ker] {mask.sum()} ANRE kerosene rows: 18L→L (÷18). "
        f"Mean price: {before:.1f}→{after:.1f} JPY/L"
    )
    return df


def fix_fuel_family(df: pd.DataFrame) -> pd.DataFrame:
    """Infer fuel_family for rows where it is blank, using product name keywords."""
    blank = df["fuel_family"].isna() | (df["fuel_family"].astype(str).str.strip() == "")

    keyword_map = [
        ("diesel", ["diesel", "biosolar", "dexlite", "dầu diesel", "mazut", "ado"]),
        (
            "gasoline",
            [
                "petrol",
                "gasoline",
                "ron",
                "motor spirit",
                "benzine",
                "xăng",
                "pertalite",
                "pertamax",
                "regular gasoline",
                "autogas",
            ],
        ),
        ("kerosene", ["kerosene", "kerosin", "dầu hỏa"]),
        ("lpg", ["lpg", "propane", "cylinder", "autogas"]),
        ("natural_gas", ["ngv", "natural gas", "cng", "town gas"]),
    ]

    count = 0
    for idx in df[blank].index:
        p = str(df.at[idx, "fuel_product"]).lower()
        for family, keywords in keyword_map:
            if any(kw in p for kw in keywords):
                df.at[idx, "fuel_family"] = family
                count += 1
                break

    if count:
        print(f"  [fix_ff] Inferred fuel_family for {count} blank rows")
    return df


def fix_column_homogenization(df: pd.DataFrame) -> pd.DataFrame:
    """
    Homogenize fuel_family, fuel_product, and quality_group columns.

    quality_group:
      - Infer from product name for rows where it is NULL.
      - Remap non-canonical values (e.g. 'octane_95') to canonical ones.
    fuel_product:  preserve original names (no renames).
    fuel_family:   already canonical; no changes needed.
    """
    # ── 1. Remap non-canonical quality_group values ────────────────────────────
    # 'octane_95' is not a canonical tier; Gasoline (Octane-95) is premium grade.
    QG_REMAP = [
        ("octane_95", "gasoline", "premium"),
    ]
    remap_total = 0
    for old_qg, family, new_qg in QG_REMAP:
        mask = (df["quality_group"] == old_qg) & (df["fuel_family"] == family)
        if mask.sum():
            df.loc[mask, "quality_group"] = new_qg
            remap_total += mask.sum()
            print(
                f"  [fix_homog] {mask.sum()} rows: quality_group '{old_qg}' → '{new_qg}' "
                f"(family={family})"
            )
    if remap_total:
        print(f"  [fix_homog] Total quality_group remapped: {remap_total} rows")

    # ── 2. Infer quality_group for NULL rows ───────────────────────────────────
    # Map (fuel_product pattern, fuel_family) → quality_group
    # Order matters: more specific patterns first
    QG_INFER = [
        # diesel
        (r"(?i)^Premium Diesel$", "diesel", "premium"),
        (r"(?i)^Diesel", "diesel", "regular"),
        (r"(?i)^Low Sulphur Diesel", "diesel", "regular"),
        # kerosene
        (r"(?i)^Kerosene", "kerosene", "regular"),
        # lpg
        (r"(?i)^Propane LPG$", "lpg", "regular"),
        # natural gas
        (r"(?i)^NGV retail price$", "natural_gas", "regular"),
    ]

    total = 0
    for pat, family, qg in QG_INFER:
        mask = (
            df["quality_group"].isna()
            & (df["fuel_family"] == family)
            & df["fuel_product"].str.match(pat, na=False)
        )
        if mask.sum():
            df.loc[mask, "quality_group"] = qg
            total += mask.sum()
            print(
                f"  [fix_homog] {mask.sum()} rows → quality_group='{qg}' "
                f"(family={family}, /{pat}/)"
            )

    print(f"  [fix_homog] Total quality_group filled: {total} rows")
    return df


# ── Step 2: Fetch functions ────────────────────────────────────────────────────

# ---------- Japan ANRE ----------


def fetch_anre_2026(df_existing: pd.DataFrame) -> pd.DataFrame:
    """
    Fetch Japan ANRE weekly petroleum data for 2026 from their Excel download.

    ANRE page: https://www.enecho.meti.go.jp/statistics/petroleum_and_lpgas/pl007/results.html
    The page contains links to Excel/ZIP files with weekly national average prices.
    """
    print("  [anre] Fetching Japan ANRE 2026 data...")
    cutoff = last_date(df_existing, "jp_anre_weekly_petroleum_2025")
    print(f"  [anre] Last existing date: {cutoff}")

    session = get_session()
    base_url = "https://www.enecho.meti.go.jp"
    page_url = f"{base_url}/statistics/petroleum_and_lpgas/pl007/results.html"

    try:
        resp = session.get(page_url, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        print(f"  [anre] Could not fetch page: {e}")
        return pd.DataFrame()

    soup = BeautifulSoup(resp.content, "lxml")

    # Collect all Excel/ZIP links on the page
    download_links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if any(ext in href.lower() for ext in [".xls", ".xlsx", ".zip", ".csv"]):
            full = href if href.startswith("http") else base_url + href
            download_links.append(full)

    if not download_links:
        print("  [anre] No download links found on ANRE page")
        return pd.DataFrame()

    print(f"  [anre] Found {len(download_links)} download links")

    # Try each download link, looking for one that contains 2026 data
    all_rows = []
    tmpl = base_row("jp_anre_weekly_petroleum_2025", df_existing)

    # Product column mapping (Japanese → schema)
    # ANRE Excel column names vary but typically contain these substrings
    PRODUCT_MAP = {
        "regular": ("Regular Gasoline", "gasoline", "regular", None),
        "premium": ("High-octane gasoline", "gasoline", "premium", None),
        "diesel": ("Diesel", "diesel", "regular", None),
        "kerosene_delivery": ("Kerosene (delivery)", "kerosene", "regular", None),
        "kerosene_store": ("Kerosene (in-store)", "kerosene", "regular", None),
    }

    for dl_url in download_links[:10]:  # Try first 10 links
        try:
            r = session.get(dl_url, timeout=60)
            r.raise_for_status()
            content = r.content

            # Handle ZIP files
            if dl_url.lower().endswith(".zip") or r.headers.get(
                "content-type", ""
            ).startswith("application/zip"):
                import zipfile

                zf = zipfile.ZipFile(BytesIO(content))
                excel_files = [
                    n for n in zf.namelist() if n.lower().endswith((".xls", ".xlsx"))
                ]
                if not excel_files:
                    continue
                content = zf.read(excel_files[0])

            xf = pd.ExcelFile(BytesIO(content))
            print(f"  [anre] Opened: {dl_url} → sheets: {xf.sheet_names}")

            for sheet in xf.sheet_names:
                try:
                    raw = pd.read_excel(BytesIO(content), sheet_name=sheet, header=None)
                except Exception:
                    continue

                # Find rows with dates (look for date-like values in first few columns)
                # ANRE format: date column followed by price columns
                date_col = None
                for col_idx in range(min(5, raw.shape[1])):
                    col = raw.iloc[:, col_idx]
                    dates_found = pd.to_datetime(col, errors="coerce").notna().sum()
                    if dates_found > 20:
                        date_col = col_idx
                        break

                if date_col is None:
                    continue

                # Parse dates
                raw["_date"] = pd.to_datetime(raw.iloc[:, date_col], errors="coerce")
                raw_new = raw[raw["_date"].dt.date > cutoff].copy()

                if raw_new.empty:
                    continue

                print(
                    f"  [anre] Sheet '{sheet}': {len(raw_new)} new rows after {cutoff}"
                )

                # Find header row (row before first data row with a date)
                first_data_idx = raw[raw["_date"].notna()].index[0]
                header_row = raw.iloc[max(0, first_data_idx - 1)]

                # Try to identify price columns by header text
                price_cols_found = {}
                for col_idx in range(raw.shape[1]):
                    hdr = str(header_row.iloc[col_idx]).lower()
                    if col_idx == date_col:
                        continue
                    if "regular" in hdr or "ハイオク以外" in hdr or "レギュラー" in hdr:
                        price_cols_found["regular"] = col_idx
                    elif "premium" in hdr or "ハイオク" in hdr or "high" in hdr:
                        price_cols_found["premium"] = col_idx
                    elif "diesel" in hdr or "軽油" in hdr:
                        price_cols_found["diesel"] = col_idx
                    elif "delivery" in hdr or "配達" in hdr or "灯油" in hdr:
                        price_cols_found["kerosene_delivery"] = col_idx
                    elif "store" in hdr or "店頭" in hdr:
                        price_cols_found["kerosene_store"] = col_idx

                if not price_cols_found:
                    # Try positional: if we have date col + N price cols, assume order
                    non_date_cols = [i for i in range(raw.shape[1]) if i != date_col]
                    if len(non_date_cols) >= 2:
                        # Default guesses based on sheet name
                        sn = str(sheet).lower()
                        if "gas" in sn or "レギュラー" in sn or "ガソリン" in sn:
                            if len(non_date_cols) >= 2:
                                price_cols_found["regular"] = non_date_cols[0]
                                price_cols_found["premium"] = non_date_cols[1]
                        elif "diesel" in sn or "軽油" in sn:
                            price_cols_found["diesel"] = non_date_cols[0]
                        elif "kerosene" in sn or "灯油" in sn:
                            if len(non_date_cols) >= 2:
                                price_cols_found["kerosene_store"] = non_date_cols[0]
                                price_cols_found["kerosene_delivery"] = non_date_cols[1]

                if not price_cols_found:
                    continue

                for _, row in raw_new.iterrows():
                    obs_date = row["_date"].date()
                    # Determine effective_to (next week - 1 day)
                    eff_to = obs_date + timedelta(days=6)

                    for prod_key, col_idx in price_cols_found.items():
                        try:
                            price = float(row.iloc[col_idx])
                        except (ValueError, TypeError):
                            continue
                        if pd.isna(price) or price <= 0:
                            continue

                        prod_name, family, qg, ron = PRODUCT_MAP.get(
                            prod_key, (prod_key, "gasoline", "regular", None)
                        )

                        # Kerosene is per-18L in ANRE → convert to per-L
                        unit = "L"
                        if "kerosene" in prod_key:
                            price = price / 18

                        r = tmpl.copy()
                        r.update(
                            {
                                "fuel_family": family,
                                "fuel_product": prod_name,
                                "quality_group": qg,
                                "octane_ron": ron,
                                "price_local": round(price, 4),
                                "unit": unit,
                                "effective_from": str(obs_date),
                                "effective_to": str(eff_to),
                                "observation_date": str(obs_date),
                            }
                        )
                        r["observation_hash"] = make_hash(r)
                        all_rows.append(r)

        except Exception as e:
            print(f"  [anre] Error processing {dl_url}: {e}")
            continue

    if all_rows:
        print(f"  [anre] Collected {len(all_rows)} new ANRE rows")
    else:
        print("  [anre] No new ANRE rows extracted (check Excel format)")

    return pd.DataFrame(all_rows) if all_rows else pd.DataFrame()


# ---------- Indonesia Pertamina ----------


def fetch_pertamina_2026(df_existing: pd.DataFrame) -> pd.DataFrame:
    """
    Fetch current Pertamina fuel prices from the MyPertamina/Pertamina Patra Niaga page.
    The page shows current retail prices with their effective date.
    """
    print("  [pertamina] Fetching Indonesia Pertamina 2026 prices...")
    cutoff = last_date(df_existing, "id_pertamina_jakarta_2025_series")
    print(f"  [pertamina] Last existing date: {cutoff}")

    session = get_session()
    url = "https://pertaminapatraniaga.com/page/harga-terbaru-bbm"

    try:
        resp = session.get(url, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        print(f"  [pertamina] Could not fetch page: {e}")
        return pd.DataFrame()

    soup = BeautifulSoup(resp.content, "lxml")
    text = soup.get_text(separator="\n")

    # Look for effective date
    obs_date = None
    date_patterns = [
        r"(\d{1,2})\s+(Januari|Februari|Maret|April|Mei|Juni|Juli|Agustus|September|Oktober|November|Desember)\s+(20\d{2})",
        r"(20\d{2})-(\d{2})-(\d{2})",
        r"(\d{1,2})/(\d{1,2})/(20\d{2})",
    ]
    INDO_MONTHS = {
        "Januari": 1,
        "Februari": 2,
        "Maret": 3,
        "April": 4,
        "Mei": 5,
        "Juni": 6,
        "Juli": 7,
        "Agustus": 8,
        "September": 9,
        "Oktober": 10,
        "November": 11,
        "Desember": 12,
    }

    for pat in date_patterns[:1]:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            try:
                d, month_name, y = m.group(1), m.group(2), m.group(3)
                month_num = INDO_MONTHS.get(month_name.capitalize(), None)
                if month_num:
                    obs_date = date(int(y), month_num, int(d))
                    break
            except Exception:
                pass

    # Also try ISO date
    if obs_date is None:
        m2 = re.search(r"(20\d{2})-(\d{2})-(\d{2})", text)
        if m2:
            try:
                obs_date = date(int(m2.group(1)), int(m2.group(2)), int(m2.group(3)))
            except Exception:
                pass

    # Default to today if no date found
    if obs_date is None:
        obs_date = date.today()
        print(f"  [pertamina] No date found on page, using today: {obs_date}")
    else:
        print(f"  [pertamina] Effective date from page: {obs_date}")

    if obs_date <= cutoff:
        print(f"  [pertamina] Date {obs_date} is not newer than {cutoff}, skipping")
        return pd.DataFrame()

    # Product → (fuel_family, quality_group) mapping
    PRODUCT_SPECS = {
        "Biosolar": ("Biosolar (subsidi)", "diesel", "regular", None),
        "Dexlite": ("Dexlite", "diesel", "premium", None),
        "Pertamina Dex": ("Pertamina Dex", "diesel", "super_premium", None),
        "Pertalite": ("Pertalite", "gasoline", "regular", None),
        "Pertamax Turbo": ("Pertamax Turbo", "gasoline", "super_premium", None),
        "Pertamax Green 95": ("Pertamax Green 95", "gasoline", "premium", 95),
        "Pertamax": ("Pertamax", "gasoline", "premium", None),
    }

    tmpl = base_row("id_pertamina_jakarta_2025_series", df_existing)
    all_rows = []

    for product_key, (prod_name, family, qg, ron) in PRODUCT_SPECS.items():
        # Search for price near the product name
        patterns = [
            rf"{re.escape(product_key)}[^0-9]*?(\d{{4,6}})",
            rf"(\d{{4,6}})[^0-9]*?{re.escape(product_key)}",
        ]
        price = None
        for pat in patterns:
            m = re.search(pat, text, re.IGNORECASE | re.DOTALL)
            if m:
                try:
                    candidate = int(m.group(1))
                    if 5000 <= candidate <= 25000:  # plausible IDR/L range
                        price = float(candidate)
                        break
                except ValueError:
                    pass

        if price is None:
            continue

        r = tmpl.copy()
        r.update(
            {
                "fuel_family": family,
                "fuel_product": prod_name,
                "quality_group": qg,
                "octane_ron": ron,
                "price_local": price,
                "effective_from": str(obs_date),
                "effective_to": str(obs_date + timedelta(days=30)),  # approximate
                "observation_date": str(obs_date),
            }
        )
        r["observation_hash"] = make_hash(r)
        all_rows.append(r)
        print(f"  [pertamina] {prod_name}: IDR {price:,.0f}/L on {obs_date}")

    return pd.DataFrame(all_rows) if all_rows else pd.DataFrame()


# ---------- Malaysia MOF ----------

ENGLISH_MONTHS_PARSE = {
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

MALAY_MONTHS = {
    1: "januari",
    2: "februari",
    3: "mac",
    4: "april",
    5: "mei",
    6: "jun",
    7: "julai",
    8: "ogos",
    9: "september",
    10: "oktober",
    11: "november",
    12: "disember",
}

MALAY_MONTHS_PARSE = {v: k for k, v in MALAY_MONTHS.items()}


def _parse_date_from_slug(slug: str) -> tuple[date | None, date | None]:
    """Extract (eff_from, eff_to) from a MOF URL slug."""
    # English slug: ...from-25-december-2025-to-31-december-2025
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
                date(y1, ENGLISH_MONTHS_PARSE[mo1], d1),
                date(y2, ENGLISH_MONTHS_PARSE[mo2], d2),
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
                date(y1, MALAY_MONTHS_PARSE[mo1], d1),
                date(y2, MALAY_MONTHS_PARSE[mo2], d2),
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
                date(y1, MALAY_MONTHS_PARSE[mo1], d1),
                date(y2, MALAY_MONTHS_PARSE[mo2], d2),
            )
        except (KeyError, ValueError):
            pass

    return None, None


def _extract_mof_prices(html: str) -> dict[str, float]:
    """
    Extract fuel prices from a Malaysia MOF article HTML.

    Strategy:
    1. Extract ONLY the article body text (strip HTML tags and head content)
       so we don't accidentally match "ron97" in URL slugs or HTML attributes.
    2. Locate each product keyword in the plain text.
    3. Find the closest "RM X.XX" value within 300 characters AFTER the keyword.

    Returns dict: {product_name: price} in MYR/L.
    """
    # Extract plain text from body only — avoids matching "ron97" in URL slugs/attributes
    soup = BeautifulSoup(html, "lxml")
    # Remove head, script, style
    for tag in soup.find_all(["head", "script", "style"]):
        tag.decompose()
    text = soup.get_text(separator=" ")
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text)

    # Find all RM price positions in the plain text
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
        """Find the first RM price within 300 chars after any of the keywords."""
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

    # Non-subsidised RON95 (BUDI95 subsidised at RM1.99 is excluded)
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

    # RON97
    prices["RON97"] = find_price_after_keyword(
        ["RON97 petrol", "petrol RON97", "RON97"], min_val=1.5, max_val=6.0
    )

    # Diesel Peninsular Malaysia (higher price, typically 2.5–4.5 MYR/L)
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

    # Diesel East Malaysia (Sabah/Sarawak/Labuan — subsidised, lower ~2.15 MYR/L)
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


def fetch_malaysia_mof_2026(df_existing: pd.DataFrame) -> pd.DataFrame:
    """
    Fetch Malaysia MOF weekly petroleum retail prices.

    Strategy:
    1. Collect article URLs from English portal listing (paginated with ?start=N)
    2. For each article, extract prices from HTML body text using regex
    3. Extract date range from URL slug
    4. Generate one row per product per day within the date range

    Products: RON95 (premium), RON97 (super_premium),
              Diesel Peninsular Malaysia (regular), Diesel East Malaysia (regular).
    """
    print("  [mof] Fetching Malaysia MOF 2026 data...")
    cutoff = last_date(df_existing, "my_mof_weekly_petroleum")
    print(f"  [mof] Last existing date: {cutoff}")

    session = get_session()
    today = date.today()

    # Collect all article URLs from English portal listing
    base_listing = "https://www.mof.gov.my/portal/en/news/press-release/retail-price"
    article_urls = []
    seen = set()

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
            # Normalise to full URLs and deduplicate within page
            links = list(
                dict.fromkeys(
                    "https://www.mof.gov.my" + li if li.startswith("/") else li
                    for li in links
                )
            )
            # Only add URLs not yet seen
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

    # Product definitions
    PRODUCTS = [
        ("RON95", "gasoline", "premium", 95),
        ("RON97", "gasoline", "super_premium", 97),
        ("Diesel (Peninsular Malaysia)", "diesel", "regular", None),
        ("Diesel (East Malaysia)", "diesel", "regular", None),
    ]

    tmpl = base_row("my_mof_weekly_petroleum", df_existing)
    all_rows = []

    for art_url in article_urls:
        # Extract date range from URL slug
        eff_from, eff_to = _parse_date_from_slug(art_url)
        if eff_from is None:
            print(f"  [mof] Could not parse date from: {art_url}")
            continue

        # Skip articles within or before the existing data
        if eff_to <= cutoff:
            continue

        # Fetch article
        try:
            resp = session.get(art_url, timeout=20)
            if resp.status_code != 200:
                print(f"  [mof] HTTP {resp.status_code}: {art_url}")
                continue
            html = resp.text
        except Exception as e:
            print(f"  [mof] Fetch error {art_url}: {e}")
            continue

        # Extract prices
        prices_found = _extract_mof_prices(html)

        if not prices_found:
            print(f"  [mof] {eff_from}→{eff_to}: no prices from {art_url}")
            time.sleep(0.3)
            continue

        rows_added = 0
        for prod_name, family, qg, ron in PRODUCTS:
            price = prices_found.get(prod_name)
            if price is None:
                continue
            # One row per day in the effective period
            d = max(eff_from, cutoff + timedelta(days=1))
            while d <= min(eff_to, today):
                r = tmpl.copy()
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

    return pd.DataFrame(all_rows) if all_rows else pd.DataFrame()


# ---------- Cambodia MOC ----------


def fetch_cambodia_moc_2026(df_existing: pd.DataFrame) -> pd.DataFrame:
    """
    Fetch Cambodia MOC fuel prices.

    The MOC commodity-values page (https://moc.gov.kh/commodity-values) is a
    Next.js app that loads data via GraphQL from https://graphql.moc.gov.kh/graphql.
    That endpoint requires Bearer authentication (403 without token).

    Fallback: scan sequential news IDs on moc.gov.kh/kh/news/{id} for fuel
    price notices. These appear every 10 days in Khmer.
    """
    print("  [kh_moc] Fetching Cambodia MOC 2026 data...")
    cutoff = last_date(df_existing, "kh_moc_fuel_notices")
    print(f"  [kh_moc] Last existing date: {cutoff}")

    session = get_session()
    tmpl = base_row("kh_moc_fuel_notices", df_existing)
    all_rows = []
    today = date.today()

    # ── Attempt 1: commodity-values page GraphQL API (requires auth) ──────────
    graphql_url = "https://graphql.moc.gov.kh/graphql"
    gql_headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "apollo-require-preflight": "true",
        "Referer": "https://moc.gov.kh/commodity-values",
        "Origin": "https://moc.gov.kh",
    }
    # Khmer product IDs for fuel (ប្រេងម៉ាស៊ូត=diesel, ប្រេងសាំងធម្មតា=regular gasoline)
    # Try to query price history without auth to see if public
    try:
        introspect = {"query": "{ __schema { queryType { fields { name } } } }"}
        r = session.post(graphql_url, json=introspect, headers=gql_headers, timeout=10)
        if r.status_code == 200 and "data" in r.text:
            print("  [kh_moc] GraphQL accessible — introspection succeeded")
            # TODO: implement full query once auth token is available
        else:
            print(
                f"  [kh_moc] GraphQL: HTTP {r.status_code} (requires auth or unavailable)"
            )
    except Exception as e:
        print(f"  [kh_moc] GraphQL error: {e}")

    # ── Attempt 2: scan sequential news IDs ────────────────────────────────────
    src = df_existing[df_existing["source_key"] == "kh_moc_fuel_notices"]
    last_id = 3035  # Fallback
    for url_str in src["source_url"].dropna().unique():
        m = re.search(r"/(\d+)$", str(url_str))
        if m:
            last_id = max(last_id, int(m.group(1)))

    print(f"  [kh_moc] Scanning news IDs from {last_id + 1}...")

    consecutive_non_fuel = 0
    for notice_id in range(last_id + 1, last_id + 2000):
        if consecutive_non_fuel > 50:
            print(
                f"  [kh_moc] Stopping after 50 consecutive non-fuel pages at ID {notice_id}"
            )
            break

        url = f"https://moc.gov.kh/kh/news/{notice_id}"
        try:
            resp = session.get(url, timeout=15)
            if resp.status_code in (404, 302):
                consecutive_non_fuel += 1
                time.sleep(0.05)
                continue
            if resp.status_code != 200:
                consecutive_non_fuel += 1
                time.sleep(0.2)
                continue

            soup = BeautifulSoup(resp.content, "lxml")
            text = soup.get_text(separator="\n")

            # Check if this is a fuel price notice (Khmer keywords for oil/fuel)
            # ប្រេង = oil/fuel; ឥន្ធនៈ = fuel; ថ្លៃ = price
            is_fuel_notice = (
                ("ប្រេង" in text and "ថ្លៃ" in text)
                or "ឥន្ធនៈ" in text
                or ("diesel" in text.lower() and any(c.isdigit() for c in text))
            )

            if not is_fuel_notice:
                consecutive_non_fuel += 1
                time.sleep(0.05)
                continue

            consecutive_non_fuel = 0

            # Extract dates (DD/MM/YYYY or ISO)
            eff_from = None
            eff_to = None
            iso_matches = re.findall(r"(20\d{2})[/\-](\d{2})[/\-](\d{2})", text)
            dmy_matches = re.findall(r"(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})", text)

            if iso_matches:
                dates = []
                for y, mo, d in iso_matches:
                    try:
                        dates.append(date(int(y), int(mo), int(d)))
                    except ValueError:
                        pass
                if dates:
                    eff_from, eff_to = min(dates), max(dates)
            elif dmy_matches:
                dates = []
                for g1, g2, y in dmy_matches:
                    try:
                        dates.append(date(int(y), int(g2), int(g1)))
                    except ValueError:
                        try:
                            dates.append(date(int(y), int(g1), int(g2)))
                        except ValueError:
                            pass
                if dates:
                    eff_from, eff_to = min(dates), max(dates)

            if eff_from is None or eff_from <= cutoff:
                if eff_from is not None:
                    consecutive_non_fuel += 1
                continue

            if eff_to is None or eff_to < eff_from:
                eff_to = eff_from + timedelta(days=9)

            # Extract KHR fuel prices (4-digit numbers in plausible range)
            price_candidates = sorted(
                {
                    int(p)
                    for p in re.findall(r"\b(\d{4})\b", text)
                    if 2500 <= int(p) <= 6500
                }
            )

            if not price_candidates:
                consecutive_non_fuel += 1
                continue

            # Try to label diesel vs gasoline from Khmer proximity
            # ប្រេងម៉ាស៊ូត = diesel, ប្រេងសាំងធម្មតា = regular gasoline
            diesel_price = None
            gas_price = None

            diesel_m = re.search(r"ម៉ាស៊ូត[^\d]{0,50}(\d{4})", text)
            gas_m = re.search(r"សាំងធម្មតា[^\d]{0,50}(\d{4})", text)

            if diesel_m and 2500 <= int(diesel_m.group(1)) <= 6500:
                diesel_price = float(diesel_m.group(1))
            if gas_m and 2500 <= int(gas_m.group(1)) <= 6500:
                gas_price = float(gas_m.group(1))

            # Fallback: use sorted price candidates (diesel typically lowest)
            if diesel_price is None and price_candidates:
                diesel_price = float(price_candidates[0])
            if gas_price is None and len(price_candidates) >= 2:
                gas_price = float(price_candidates[1])

            products = []
            if diesel_price:
                products.append(("Diesel", "diesel", "regular", None, diesel_price))
            if gas_price and gas_price != diesel_price:
                products.append(
                    ("Regular Gasoline", "gasoline", "regular", None, gas_price)
                )

            if not products:
                continue

            rows_added = 0
            for prod_name, family, qg, ron, price in products:
                d = eff_from
                while d <= min(eff_to, today):
                    if d > cutoff:
                        r = tmpl.copy()
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
                                "source_url": url,
                            }
                        )
                        r["observation_hash"] = make_hash(r)
                        all_rows.append(r)
                        rows_added += 1
                    d += timedelta(days=1)

            if rows_added:
                print(
                    f"  [kh_moc] ID {notice_id}: {eff_from}–{eff_to}, "
                    f"{len(products)} products, {rows_added} rows"
                )

        except Exception as e:
            print(f"  [kh_moc] ID {notice_id}: error: {e}")
            consecutive_non_fuel += 1

        time.sleep(0.15)

    return pd.DataFrame(all_rows) if all_rows else pd.DataFrame()


# ---------- Lao State Fuel ----------


def fetch_lao_2026(df_existing: pd.DataFrame) -> pd.DataFrame:
    """
    Fetch Lao State Fuel Company provincial prices for 2026.

    The page at laostatefuel.com/en/gas-price.html has a table with columns:
      [No., Province, Date (DD/MM/YYYY), Gasoline 95, Regular, Diesel]

    Each row is one province with its own observation date in DD/MM/YYYY format.
    Prices are in LAK/L with format like "28,780 KIP".
    """
    print("  [lao] Fetching Lao PDR 2026 data...")
    cutoff = last_date(df_existing, "lao_state_fuel_oil_prices")
    print(f"  [lao] Last existing date: {cutoff}")

    session = get_session()
    url = "https://www.laostatefuel.com/en/gas-price.html"

    try:
        resp = session.get(url, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        print(f"  [lao] Could not fetch page: {e}")
        return pd.DataFrame()

    soup = BeautifulSoup(resp.content, "lxml")

    # Product column definitions (header substring → product metadata)
    PRODUCT_COLS = {
        "gasoline 95": ("Gasoline 95", "gasoline", "premium", 95),
        "95": ("Gasoline 95", "gasoline", "premium", 95),
        "regular": ("Regular Gasoline", "gasoline", "regular", None),
        "diesel": ("Diesel", "diesel", "regular", None),
    }

    tmpl = base_row("lao_state_fuel_oil_prices", df_existing)
    all_rows = []

    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if len(rows) < 3:
            continue

        header_cells = rows[0].find_all(["th", "td"])
        headers = [c.get_text(strip=True).lower() for c in header_cells]

        # Detect expected structure: must have Province and Date columns
        if "province" not in " ".join(headers) or "date" not in " ".join(headers):
            continue

        # Find column indices
        try:
            prov_col = next(i for i, h in enumerate(headers) if "province" in h)
            date_col = next(
                i for i, h in enumerate(headers) if "date" in h and "province" not in h
            )
        except StopIteration:
            continue

        # Map price columns
        price_cols = {}
        for col_idx, h in enumerate(headers):
            for key, meta in PRODUCT_COLS.items():
                if key in h and col_idx not in (prov_col, date_col):
                    price_cols[col_idx] = meta
                    break

        if not price_cols:
            continue

        for row in rows[1:]:
            cells = row.find_all(["th", "td"])
            if len(cells) <= max(date_col, prov_col):
                continue
            cell_texts = [c.get_text(strip=True) for c in cells]

            province = cell_texts[prov_col] if prov_col < len(cell_texts) else None
            date_str = cell_texts[date_col] if date_col < len(cell_texts) else None

            if not province or not date_str:
                continue

            # Parse DD/MM/YYYY date from the Date column
            m = re.match(r"(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})", date_str)
            if not m:
                continue
            try:
                obs_date = date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
            except ValueError:
                continue

            if obs_date <= cutoff:
                continue  # Not newer than existing data

            for col_idx, (prod_name, family, qg, ron) in price_cols.items():
                if col_idx >= len(cell_texts):
                    continue
                price_str = cell_texts[col_idx]
                try:
                    price = float(re.sub(r"[^0-9.]", "", price_str))
                    if price < 5000 or price > 100000:  # plausible LAK/L range
                        continue
                except (ValueError, TypeError):
                    continue

                r = tmpl.copy()
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
                        "source_url": url,
                    }
                )
                r["observation_hash"] = make_hash(r)
                all_rows.append(r)

    if all_rows:
        max_d = max(r["observation_date"] for r in all_rows)
        print(f"  [lao] Collected {len(all_rows)} new rows (max date: {max_d})")
    else:
        # Report the latest date seen even if not new
        all_dates = []
        for table in soup.find_all("table"):
            for table_row in table.find_all("tr")[1:]:
                for cell in table_row.find_all(["th", "td"]):
                    m = re.match(
                        r"(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})",
                        cell.get_text(strip=True),
                    )
                    if m:
                        try:
                            all_dates.append(
                                date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
                            )
                        except ValueError:
                            pass
        latest = max(all_dates) if all_dates else None
        print(f"  [lao] No new rows (site date: {latest}, cutoff: {cutoff})")

    return pd.DataFrame(all_rows) if all_rows else pd.DataFrame()


# ---------- Korea Opinet ----------


def fetch_korea_opinet_2026(df_existing: pd.DataFrame) -> pd.DataFrame:
    """
    Fetch Korea Opinet weekly national average fuel prices for 2026.

    Opinet publishes weekly averages. We attempt to find press releases
    citing Opinet weekly data via news search.
    """
    print("  [opinet] Fetching Korea Opinet 2026 data...")
    cutoff = last_date(df_existing, "kr_opinet_weekly_national_sampled_2025")
    print(f"  [opinet] Last existing date: {cutoff}")

    session = get_session()

    # Attempt Opinet API with recent dates
    tmpl = base_row("kr_opinet_weekly_national_sampled_2025", df_existing)
    all_rows = []

    PRODUCTS = [
        ("Regular gasoline average", "gasoline", "regular", "B027"),
        ("Diesel average", "diesel", "regular", "D047"),
    ]
    today = date.today()
    # Try fetching weekly data for each week after cutoff
    week = cutoff + timedelta(days=1)
    while week.weekday() != 0:  # Monday
        week += timedelta(days=1)

    api_base = "https://www.opinet.co.kr/api/avgAllOil.do"

    for product_name, family, qg, prodcd in PRODUCTS:
        current_week = week
        while current_week <= today:
            date_str = current_week.strftime("%Y%m%d")
            api_url = f"{api_base}?code=F220BFBC98&out=json&prodcd={prodcd}&area=00&date={date_str}"
            try:
                resp = session.get(api_url, timeout=15)
                if resp.status_code == 200:
                    data = resp.json()
                    # Parse Opinet API response
                    oil_data = data.get("OilInfo", {}).get("item", [])
                    if isinstance(oil_data, dict):
                        oil_data = [oil_data]
                    for item in oil_data:
                        try:
                            price = float(item.get("price", 0))
                            if price < 1000 or price > 3000:
                                continue
                            obs_date = pd.to_datetime(
                                item.get("date", date_str), format="%Y%m%d"
                            ).date()
                            if obs_date <= cutoff:
                                continue
                            r = tmpl.copy()
                            r.update(
                                {
                                    "fuel_family": family,
                                    "fuel_product": product_name,
                                    "quality_group": qg,
                                    "price_local": price,
                                    "effective_from": str(obs_date),
                                    "effective_to": str(obs_date + timedelta(days=6)),
                                    "observation_date": str(obs_date),
                                    "source_url": api_url,
                                }
                            )
                            r["observation_hash"] = make_hash(r)
                            all_rows.append(r)
                        except Exception:
                            pass
            except Exception:
                pass
            current_week += timedelta(days=7)
            time.sleep(0.3)

    if all_rows:
        print(f"  [opinet] Collected {len(all_rows)} rows via API")
    else:
        print("  [opinet] API attempt unsuccessful (check Opinet API key/format)")

    return pd.DataFrame(all_rows) if all_rows else pd.DataFrame()


# ---------- Fiji FCCC ----------


def fetch_fiji_fccc_2026(df_existing: pd.DataFrame) -> pd.DataFrame:
    """
    Fetch Fiji FCCC monthly fuel prices for 2026 from SPC page.

    Attempts: prdrse4all.spc.int/node/4/content/fiji-wholesale-and-retail-fuel-prices-2026
    Falls back to 2025 URL to check for updated content.
    """
    print("  [fiji] Fetching Fiji FCCC 2026 data...")
    cutoff = last_date(df_existing, "fiji_fccc_monthly_prices")
    print(f"  [fiji] Last existing date: {cutoff}")

    session = get_session()
    urls_to_try = [
        "https://prdrse4all.spc.int/node/4/content/fiji-wholesale-and-retail-fuel-prices-2026",
        "https://prdrse4all.spc.int/node/4/content/fiji-wholesale-and-retail-fuel-prices-2025",
        "https://prdrse4all.spc.int/system/files/country-files/Fiji_fuel_prices.pdf",
    ]

    tmpl = base_row("fiji_fccc_monthly_prices", df_existing)

    PRODUCT_MAP = {
        "Diesel": ("Diesel", "diesel", "regular"),
        "Motor Spirit": ("Motor Spirit", "gasoline", "premium"),
        "Premix": ("Premix", "gasoline", "premix"),
        "Kerosene": ("Kerosene", "kerosene", "regular"),
        "Autogas": ("Autogas", "lpg", None),
    }

    all_rows = []

    for page_url in urls_to_try:
        try:
            resp = session.get(page_url, timeout=30)
            if resp.status_code != 200:
                continue

            content_type = resp.headers.get("content-type", "")

            if "pdf" in content_type or page_url.endswith(".pdf"):
                # Try pdfplumber
                try:
                    import pdfplumber

                    with pdfplumber.open(BytesIO(resp.content)) as pdf:
                        for page in pdf.pages:
                            text = page.extract_text() or ""
                            # Parse month/price table
                            lines = text.split("\n")
                            for line in lines:
                                # Look for month price data
                                month_match = re.match(
                                    r"(January|February|March|April|May|June|July|August|"
                                    r"September|October|November|December)\s+(20\d{2})\s+([\d.]+)",
                                    line,
                                    re.IGNORECASE,
                                )
                                if month_match:
                                    month_name = month_match.group(1)
                                    # Further parsing needed for multi-product lines
                                    # year_str = month_match.group(2)
                                    # price_str = month_match.group(3)
                except ImportError:
                    print("  [fiji] pdfplumber not installed, skipping PDF")
                except Exception as e:
                    print(f"  [fiji] PDF parse error: {e}")
            else:
                # HTML page
                soup = BeautifulSoup(resp.content, "lxml")
                text = soup.get_text(separator="\n")

                MONTH_MAP = {
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

                # Look for tables with month-level prices
                tables = soup.find_all("table")
                for table in tables:
                    rows_html = table.find_all("tr")
                    if len(rows_html) < 2:
                        continue
                    headers = [
                        c.get_text(strip=True)
                        for c in rows_html[0].find_all(["th", "td"])
                    ]

                    # Identify product columns
                    prod_cols = {}
                    for col_idx, hdr in enumerate(headers):
                        h_lower = hdr.lower()
                        for prod_key in PRODUCT_MAP:
                            if prod_key.lower() in h_lower:
                                prod_cols[prod_key] = col_idx

                    if not prod_cols:
                        continue

                    for row in rows_html[1:]:
                        cells = [
                            c.get_text(strip=True) for c in row.find_all(["th", "td"])
                        ]
                        if not cells:
                            continue
                        # First cell: date
                        date_str = cells[0]
                        obs_date = None
                        for month_name, month_num in MONTH_MAP.items():
                            if month_name in date_str.lower():
                                year_m = re.search(r"(20\d{2})", date_str)
                                if year_m:
                                    try:
                                        obs_date = date(
                                            int(year_m.group(1)), month_num, 1
                                        )
                                    except ValueError:
                                        pass
                                break

                        if obs_date is None or obs_date <= cutoff:
                            continue

                        for prod_key, col_idx in prod_cols.items():
                            if col_idx >= len(cells):
                                continue
                            try:
                                price = float(re.sub(r"[^0-9.]", "", cells[col_idx]))
                                if price <= 0:
                                    continue
                            except (ValueError, TypeError):
                                continue

                            prod_name, family, qg = PRODUCT_MAP[prod_key]

                            # One row per month (use 1st of month as observation date)
                            r = tmpl.copy()
                            r.update(
                                {
                                    "fuel_family": family,
                                    "fuel_product": prod_name,
                                    "quality_group": qg,
                                    "price_local": price,
                                    "effective_from": str(obs_date),
                                    "effective_to": str(
                                        (
                                            obs_date.replace(day=28) + timedelta(days=4)
                                        ).replace(day=1)
                                        - timedelta(days=1)
                                    ),
                                    "observation_date": str(obs_date),
                                    "source_url": page_url,
                                }
                            )
                            r["observation_hash"] = make_hash(r)
                            all_rows.append(r)

            if all_rows:
                print(
                    f"  [fiji] Collected {len(all_rows)} new Fiji rows from {page_url}"
                )
                break

        except Exception as e:
            print(f"  [fiji] Error fetching {page_url}: {e}")
            continue

    if not all_rows:
        print("  [fiji] No new Fiji rows extracted")

    return pd.DataFrame(all_rows) if all_rows else pd.DataFrame()


# ---------- Australia ACCC ----------


def fetch_accc_2026(df_existing: pd.DataFrame) -> pd.DataFrame:
    """
    Fetch Australia ACCC quarterly retail fuel prices for Q4 2025 and Q1 2026.
    ACCC publishes quarterly averages across 5 largest cities.
    Prices are in AUDc/L (cents per litre).
    """
    print("  [accc] Fetching Australia ACCC 2026 data...")
    cutoff = last_date(df_existing, "au_accc_5largestcities_quarterly")
    print(f"  [accc] Last existing date: {cutoff}")

    today = date.today()
    session = get_session()
    tmpl = base_row("au_accc_5largestcities_quarterly", df_existing)

    # After our fix, currency will be AUD; new rows should also use AUD
    tmpl["currency"] = "AUD"

    # ACCC petrol monitoring page (has links to quarterly report media releases)
    # Note: URL is /media-release/ (singular), not /media-releases/ (plural)
    monitoring_url = "https://www.accc.gov.au/by-industry/petrol-and-fuel"

    try:
        resp = session.get(monitoring_url, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        print(f"  [accc] Could not fetch ACCC monitoring page: {e}")
        return pd.DataFrame()

    soup = BeautifulSoup(resp.content, "lxml")

    # Find links to quarterly petrol media releases
    report_links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        text_link = a.get_text(strip=True).lower()
        if "petrol" in text_link and "quarter" in text_link:
            if any(yr in href or yr in text_link for yr in ["2025", "2026"]):
                full = (
                    href
                    if href.startswith("http")
                    else "https://www.accc.gov.au" + href
                )
                if full not in report_links:
                    report_links.append(full)

    all_rows = []

    PRODUCTS = [
        ("Diesel average", "diesel", None),
        ("Unleaded petrol average", "gasoline", "regular"),
    ]

    for url in report_links[:5]:
        try:
            r = session.get(url, timeout=20)
            if r.status_code != 200:
                continue
            art = BeautifulSoup(r.content, "lxml").find("main") or BeautifulSoup(
                r.content, "lxml"
            )
            text = re.sub(r"\s+", " ", art.get_text(separator=" "))

            # Detect quarter: "September quarter 2025" or "December quarter 2025" etc.
            quarter_match = re.search(
                r"(December|September|June|March)\s+quarter\s+(20\d{2})",
                text,
                re.IGNORECASE,
            )
            if not quarter_match:
                continue

            quarter_month = quarter_match.group(1).capitalize()
            year_str = quarter_match.group(2)
            quarter_map = {
                "March": (1, 3),
                "June": (4, 6),
                "September": (7, 9),
                "December": (10, 12),
            }
            q_months = quarter_map[quarter_month]
            eff_from = date(int(year_str), q_months[0], 1)
            eff_to = date(int(year_str), q_months[1], 28) + timedelta(days=4)
            eff_to = eff_to.replace(day=1) - timedelta(days=1)

            if eff_from <= cutoff:
                print(
                    f"  [accc] {quarter_month} {year_str} already covered (cutoff: {cutoff})"
                )
                continue

            # Extract 5-city average price in cpl (cents per litre)
            # Pattern like "178.8 cents per litre" or "178.8 cpl"
            cpl_match = re.search(
                r"(\d{3}\.\d)\s*(?:cents per litre|cpl)", text, re.IGNORECASE
            )
            if not cpl_match:
                # Fallback: look for a standalone 3-digit price like "178.8"
                cpl_candidates = re.findall(r"\b(\d{3}\.\d)\b", text)
                valid = [float(p) for p in cpl_candidates if 130 <= float(p) <= 280]
                if not valid:
                    print(f"  [accc] No price found in {url}")
                    continue
                avg_cpl = valid[0]
            else:
                avg_cpl = float(cpl_match.group(1))

            avg_price = round(avg_cpl / 100, 4)  # Convert cpl → AUD/L

            for prod_name, family, qg in PRODUCTS:
                for day_offset in range((eff_to - eff_from).days + 1):
                    obs_date = eff_from + timedelta(days=day_offset)
                    if obs_date > today:
                        break
                    r_row = tmpl.copy()
                    r_row.update(
                        {
                            "fuel_family": family,
                            "fuel_product": prod_name,
                            "quality_group": qg,
                            "price_local": avg_price,
                            "effective_from": str(eff_from),
                            "effective_to": str(eff_to),
                            "observation_date": str(obs_date),
                            "source_url": url,
                        }
                    )
                    r_row["observation_hash"] = make_hash(r_row)
                    all_rows.append(r_row)

            print(f"  [accc] {eff_from}–{eff_to}: {avg_cpl} cpl → AUD {avg_price}/L")

        except Exception as e:
            print(f"  [accc] Error processing {url}: {e}")
        time.sleep(0.5)

    if not all_rows:
        print("  [accc] No new ACCC rows extracted")

    return pd.DataFrame(all_rows) if all_rows else pd.DataFrame()


# ---------- Mongolia data.mn ----------


def fetch_mongolia_data_mn_2026(df_existing: pd.DataFrame) -> pd.DataFrame:
    """
    Fetch Mongolia data.mn weekly fuel prices for 2026.

    Three datasets:
      - mn_data_mn_a92_aimags:        weekly A-92 prices by aimag
      - mn_data_mn_diesel_aimags:     weekly diesel prices by aimag
      - mn_data_mn_fuel_ulaanbaatar:  weekly fuel prices in Ulaanbaatar

    data.mn pages render a table with columns: Date, [region/product columns].
    """
    print("  [mn_data] Fetching Mongolia data.mn 2026 data...")

    SOURCES = [
        (
            "mn_data_mn_a92_aimags",
            "https://data.mn/en/data/weekly-gasoline-prices-aimags",
            "Petrol A-92",
            "gasoline",
            "regular",
            None,
        ),
        (
            "mn_data_mn_diesel_aimags",
            "https://data.mn/en/data/weekly-diesel-prices-aimags",
            "Diesel",
            "diesel",
            "regular",
            None,
        ),
        (
            "mn_data_mn_fuel_ulaanbaatar",
            "https://data.mn/en/data/weekly-fuel-prices-ulaanbaatar",
            None,
            None,
            None,
            None,
        ),  # multiple products
    ]

    session = get_session()
    all_rows = []

    # Ulaanbaatar product map (column header → product meta)
    UB_PRODUCTS = {
        "a-80": ("Petrol A-80", "gasoline", "regular", None),
        "a80": ("Petrol A-80", "gasoline", "regular", None),
        "a-92": ("Petrol A-92", "gasoline", "regular", None),
        "a92": ("Petrol A-92", "gasoline", "regular", None),
        "diesel": ("Diesel", "diesel", "regular", None),
    }

    for (
        source_key,
        url,
        default_prod,
        default_family,
        default_qg,
        default_ron,
    ) in SOURCES:
        cutoff = last_date(df_existing, source_key)
        print(f"  [mn_data] {source_key}: last date {cutoff}")
        tmpl = base_row(source_key, df_existing)

        try:
            resp = session.get(url, timeout=30)
            resp.raise_for_status()
        except Exception as e:
            print(f"  [mn_data] Could not fetch {url}: {e}")
            continue

        soup = BeautifulSoup(resp.content, "lxml")

        for table in soup.find_all("table"):
            rows_html = table.find_all("tr")
            if len(rows_html) < 3:
                continue
            headers = [
                c.get_text(strip=True).lower()
                for c in rows_html[0].find_all(["th", "td"])
            ]

            # Find date column
            date_col = next(
                (i for i, h in enumerate(headers) if "date" in h or "огноо" in h), None
            )
            if date_col is None:
                continue

            # For aimag tables: find "national" or "average" column, or use first price col
            if source_key != "mn_data_mn_fuel_ulaanbaatar":
                # Find a national/average column
                price_col = None
                for i, h in enumerate(headers):
                    if i == date_col:
                        continue
                    if any(
                        kw in h for kw in ["national", "average", "улсын", "дундаж"]
                    ):
                        price_col = i
                        break
                if price_col is None:
                    # Use last numeric column as national average
                    price_col = max(
                        (i for i in range(len(headers)) if i != date_col), default=None
                    )
                if price_col is None:
                    continue

                for row in rows_html[1:]:
                    cells = [c.get_text(strip=True) for c in row.find_all(["th", "td"])]
                    if len(cells) <= max(date_col, price_col):
                        continue
                    date_str = cells[date_col]
                    # Try YYYY-MM-DD or DD/MM/YYYY
                    obs_date = None
                    for pat in [
                        r"(20\d{2})[/\-](\d{2})[/\-](\d{2})",
                        r"(\d{2})[/\-](\d{2})[/\-](20\d{2})",
                    ]:
                        m = re.match(pat, date_str)
                        if m:
                            try:
                                if pat.startswith(r"(20"):
                                    obs_date = date(
                                        int(m.group(1)),
                                        int(m.group(2)),
                                        int(m.group(3)),
                                    )
                                else:
                                    obs_date = date(
                                        int(m.group(3)),
                                        int(m.group(2)),
                                        int(m.group(1)),
                                    )
                                break
                            except ValueError:
                                pass
                    if obs_date is None or obs_date <= cutoff:
                        continue
                    try:
                        price = float(re.sub(r"[^0-9.]", "", cells[price_col]))
                        if price < 500 or price > 10000:  # plausible MNT/L
                            continue
                    except (ValueError, TypeError):
                        continue

                    r = tmpl.copy()
                    r.update(
                        {
                            "fuel_family": default_family,
                            "fuel_product": default_prod,
                            "quality_group": default_qg,
                            "octane_ron": default_ron,
                            "price_local": price,
                            "effective_from": str(obs_date),
                            "effective_to": str(obs_date + timedelta(days=6)),
                            "observation_date": str(obs_date),
                            "source_url": url,
                        }
                    )
                    r["observation_hash"] = make_hash(r)
                    all_rows.append(r)

            else:
                # Ulaanbaatar: multiple product columns
                prod_cols = {}
                for i, h in enumerate(headers):
                    if i == date_col:
                        continue
                    for key, meta in UB_PRODUCTS.items():
                        if key in h:
                            prod_cols[i] = meta
                            break

                if not prod_cols:
                    continue

                for row in rows_html[1:]:
                    cells = [c.get_text(strip=True) for c in row.find_all(["th", "td"])]
                    if not cells:
                        continue
                    date_str = cells[date_col] if date_col < len(cells) else ""
                    obs_date = None
                    for pat in [
                        r"(20\d{2})[/\-](\d{2})[/\-](\d{2})",
                        r"(\d{2})[/\-](\d{2})[/\-](20\d{2})",
                    ]:
                        m = re.match(pat, date_str)
                        if m:
                            try:
                                if pat.startswith(r"(20"):
                                    obs_date = date(
                                        int(m.group(1)),
                                        int(m.group(2)),
                                        int(m.group(3)),
                                    )
                                else:
                                    obs_date = date(
                                        int(m.group(3)),
                                        int(m.group(2)),
                                        int(m.group(1)),
                                    )
                                break
                            except ValueError:
                                pass
                    if obs_date is None or obs_date <= cutoff:
                        continue

                    for col_idx, (prod_name, family, qg, ron) in prod_cols.items():
                        if col_idx >= len(cells):
                            continue
                        try:
                            price = float(re.sub(r"[^0-9.]", "", cells[col_idx]))
                            if price < 500 or price > 10000:
                                continue
                        except (ValueError, TypeError):
                            continue
                        r = tmpl.copy()
                        r.update(
                            {
                                "fuel_family": family,
                                "fuel_product": prod_name,
                                "quality_group": qg,
                                "octane_ron": ron,
                                "price_local": price,
                                "effective_from": str(obs_date),
                                "effective_to": str(obs_date + timedelta(days=6)),
                                "observation_date": str(obs_date),
                                "source_url": url,
                            }
                        )
                        r["observation_hash"] = make_hash(r)
                        all_rows.append(r)

        rows_for_source = [r for r in all_rows if r["source_key"] == source_key]
        print(f"  [mn_data] {source_key}: {len(rows_for_source)} new rows")

    return pd.DataFrame(all_rows) if all_rows else pd.DataFrame()


# ---------- New Zealand MBIE ----------


def fetch_nz_mbie_2026(df_existing: pd.DataFrame) -> pd.DataFrame:
    """
    Fetch New Zealand MBIE weekly fuel price monitoring data for 2026.

    MBIE publishes a long-format tidy CSV at:
    https://www.mbie.govt.nz/assets/Data-Files/Energy/Weekly-fuel-price-monitoring/weekly-table.csv

    Columns: Week, Date, Fuel, Variable, Value, Unit, Status
    We filter on Variable == "Adjusted retail price" for Diesel, Regular Petrol,
    Premium Petrol 95R. Unit is "NZD c/L" so we divide by 100.
    """
    print("  [nz_mbie] Fetching NZ MBIE 2026 data...")
    cutoff = last_date(df_existing, "nz_mbie_weekly_fuel")
    print(f"  [nz_mbie] Last existing date: {cutoff}")

    session = get_session()
    # Visit the homepage first to establish a session cookie that bypasses Incapsula
    session.get("https://www.mbie.govt.nz/", timeout=20)

    csv_url = (
        "https://www.mbie.govt.nz/assets/Data-Files/Energy/Weekly-fuel-price-monitoring/"
        "weekly-table.csv"
    )
    try:
        resp = session.get(csv_url, timeout=60)
        resp.raise_for_status()
        if b"Incapsula" in resp.content[:500] or b"<html" in resp.content[:10]:
            print("  [nz_mbie] Blocked by Incapsula / not a CSV response")
            return pd.DataFrame()
    except Exception as e:
        print(f"  [nz_mbie] Could not download CSV: {e}")
        return pd.DataFrame()

    try:
        raw = pd.read_csv(
            BytesIO(resp.content),
            encoding="utf-8",
            encoding_errors="replace",
        )
    except Exception as e:
        print(f"  [nz_mbie] Could not parse CSV: {e}")
        return pd.DataFrame()

    print(f"  [nz_mbie] Downloaded CSV → shape {raw.shape}")

    # Validate expected columns
    required_cols = {"Date", "Fuel", "Variable", "Value", "Unit"}
    if not required_cols.issubset(set(raw.columns)):
        print(f"  [nz_mbie] Unexpected columns: {raw.columns.tolist()}")
        return pd.DataFrame()

    # Filter to adjusted retail prices only
    retail = raw[raw["Variable"] == "Adjusted retail price"].copy()
    retail["_date"] = pd.to_datetime(retail["Date"], errors="coerce")
    retail_new = retail[retail["_date"].dt.date > cutoff].copy()

    if retail_new.empty:
        print("  [nz_mbie] No new retail rows (all dates ≤ cutoff)")
        return pd.DataFrame()

    PRODUCT_MAP = {
        "Regular Petrol": ("Regular Petrol", "gasoline", "regular", None),
        "Premium Petrol 95R": ("Premium Petrol 95R", "gasoline", "premium", 95),
        "Diesel": ("Diesel", "diesel", "regular", None),
    }

    tmpl = base_row("nz_mbie_weekly_fuel", df_existing)
    all_rows = []

    for _, row in retail_new.iterrows():
        fuel = str(row["Fuel"]).strip()
        if fuel not in PRODUCT_MAP:
            continue
        try:
            # Values are in NZD c/L → convert to NZD/L
            price_cl = float(row["Value"])
            if pd.isna(price_cl) or not (100 <= price_cl <= 500):
                continue
            price = round(price_cl / 100, 4)
        except (ValueError, TypeError):
            continue

        obs_date = row["_date"].date()
        prod_name, family, qg, ron = PRODUCT_MAP[fuel]
        r_row = tmpl.copy()
        r_row.update(
            {
                "fuel_family": family,
                "fuel_product": prod_name,
                "quality_group": qg,
                "octane_ron": ron,
                "price_local": price,
                "effective_from": str(obs_date),
                "effective_to": str(obs_date + timedelta(days=6)),
                "observation_date": str(obs_date),
                "source_url": csv_url,
                "notes": "Adjusted retail price (NZD c/L ÷ 100)",
            }
        )
        r_row["observation_hash"] = make_hash(r_row)
        all_rows.append(r_row)

    if all_rows:
        print(
            f"  [nz_mbie] {len(all_rows)} new rows ({retail_new['_date'].min().date()} → {retail_new['_date'].max().date()})"
        )
    else:
        print("  [nz_mbie] No new NZ MBIE rows extracted")

    return pd.DataFrame(all_rows) if all_rows else pd.DataFrame()


# ---------- Thailand EPPO NGV ----------


def fetch_thailand_eppo_ngv_2026(df_existing: pd.DataFrame) -> pd.DataFrame:
    """
    Fetch Thailand EPPO NGV retail prices in Bangkok for 2026.

    Direct Excel download: https://www.eppo.go.th/images/petroleum/price/retail-priceNGV/NGVPrice.xls
    Columns: Date (month), Price (THB/kg).
    """
    print("  [th_eppo_ngv] Fetching Thailand EPPO NGV 2026 data...")
    cutoff = last_date(df_existing, "th_eppo_ngv_bangkok_2025")
    print(f"  [th_eppo_ngv] Last existing date: {cutoff}")

    session = get_session()
    xls_url = (
        "https://www.eppo.go.th/images/petroleum/price/retail-priceNGV/NGVPrice.xls"
    )

    try:
        resp = session.get(xls_url, timeout=60)
        resp.raise_for_status()
    except Exception as e:
        print(f"  [th_eppo_ngv] Could not download XLS: {e}")
        return pd.DataFrame()

    tmpl = base_row("th_eppo_ngv_bangkok_2025", df_existing)
    all_rows = []

    # Try xlrd for legacy .xls; fall back to openpyxl
    engine = "xlrd"
    try:
        import xlrd  # noqa: F401
    except ImportError:
        engine = "openpyxl"

    try:
        xf = pd.ExcelFile(BytesIO(resp.content), engine=engine)
        for sheet in xf.sheet_names:
            try:
                raw = pd.read_excel(
                    BytesIO(resp.content), sheet_name=sheet, header=None, engine=engine
                )
            except Exception:
                continue

            # Find date column
            date_col = None
            for col_idx in range(min(3, raw.shape[1])):
                parsed = pd.to_datetime(raw.iloc[:, col_idx], errors="coerce")
                if parsed.notna().sum() > 10:
                    date_col = col_idx
                    break

            if date_col is None:
                continue

            raw["_date"] = pd.to_datetime(raw.iloc[:, date_col], errors="coerce")
            raw_new = raw[raw["_date"].dt.date > cutoff].copy()

            if raw_new.empty:
                continue

            # Price column: first non-date numeric column with plausible THB/kg range (5–20)
            price_col = None
            for col_idx in range(raw.shape[1]):
                if col_idx == date_col:
                    continue
                vals = pd.to_numeric(raw.iloc[:, col_idx], errors="coerce").dropna()
                if vals.empty:
                    continue
                if vals.between(5, 30).sum() > 5:
                    price_col = col_idx
                    break

            if price_col is None:
                continue

            for _, row in raw_new.iterrows():
                obs_date = row["_date"].date()
                try:
                    price = float(row.iloc[price_col])
                    if pd.isna(price) or not (5 <= price <= 30):
                        continue
                except (ValueError, TypeError):
                    continue

                r = tmpl.copy()
                r.update(
                    {
                        "fuel_family": "natural_gas",
                        "fuel_product": "NGV retail price",
                        "quality_group": "regular",
                        "price_local": round(price, 4),
                        "effective_from": str(obs_date),
                        "effective_to": str(obs_date),
                        "observation_date": str(obs_date),
                        "source_url": xls_url,
                    }
                )
                r["observation_hash"] = make_hash(r)
                all_rows.append(r)

            if all_rows:
                print(f"  [th_eppo_ngv] Sheet '{sheet}': {len(all_rows)} new rows")
                break

    except Exception as e:
        if "zip" in str(e).lower() or "xlrd" in str(e).lower():
            print("  [th_eppo_ngv] Legacy .xls requires xlrd: pip install xlrd>=2.0.1")
        else:
            print(f"  [th_eppo_ngv] Error parsing XLS: {e}")

    if not all_rows:
        print("  [th_eppo_ngv] No new EPPO NGV rows extracted")

    return pd.DataFrame(all_rows) if all_rows else pd.DataFrame()


# ---------- Timor-Leste ANP ----------


def fetch_timor_anp_2026(df_existing: pd.DataFrame) -> pd.DataFrame:
    """
    Fetch Timor-Leste ANP daily fuel prices for 2026.

    ANP publishes station-level prices at https://www.anp.tl/daily-fuel-price/
    The page contains a table of petrol and diesel prices per station/city.
    We compute the national average and record it.
    """
    print("  [tl_anp] Fetching Timor-Leste ANP 2026 data...")
    cutoff = last_date(df_existing, "tl_anp_daily_fuel_price")
    print(f"  [tl_anp] Last existing date: {cutoff}")

    session = get_session()
    url = "https://www.anp.tl/daily-fuel-price/"

    try:
        resp = session.get(url, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        print(f"  [tl_anp] Could not fetch page: {e}")
        return pd.DataFrame()

    soup = BeautifulSoup(resp.content, "lxml")
    text = soup.get_text(separator="\n")

    # Try to find a date on the page
    obs_date = None
    date_matches = re.findall(r"(\d{1,2})[/\-\.](\d{1,2})[/\-\.](20\d{2})", text)
    iso_matches = re.findall(r"(20\d{2})[/\-](\d{2})[/\-](\d{2})", text)

    if iso_matches:
        try:
            obs_date = date(
                int(iso_matches[0][0]), int(iso_matches[0][1]), int(iso_matches[0][2])
            )
        except ValueError:
            pass
    elif date_matches:
        try:
            obs_date = date(
                int(date_matches[0][2]),
                int(date_matches[0][1]),
                int(date_matches[0][0]),
            )
        except ValueError:
            pass

    if obs_date is None:
        obs_date = date.today()
        print(f"  [tl_anp] No date found on page, using today: {obs_date}")
    else:
        print(f"  [tl_anp] Effective date from page: {obs_date}")

    if obs_date <= cutoff:
        print(f"  [tl_anp] Date {obs_date} not newer than cutoff {cutoff}, skipping")
        return pd.DataFrame()

    tmpl = base_row("tl_anp_daily_fuel_price", df_existing)
    all_rows = []

    PRODUCTS = [
        ("Petrol", "gasoline", "regular", None, r"(?i)petrol|gasoline|benzina"),
        ("Diesel", "diesel", "regular", None, r"(?i)diesel|gasoleo"),
    ]

    for table in soup.find_all("table"):
        rows_html = table.find_all("tr")
        if len(rows_html) < 3:
            continue
        headers = [
            c.get_text(strip=True).lower() for c in rows_html[0].find_all(["th", "td"])
        ]

        # Find price columns by product type
        for prod_name, family, qg, ron, prod_pat in PRODUCTS:
            price_col = next(
                (i for i, h in enumerate(headers) if re.search(prod_pat, h)), None
            )
            if price_col is None:
                continue

            prices = []
            for row in rows_html[1:]:
                cells = [c.get_text(strip=True) for c in row.find_all(["th", "td"])]
                if price_col >= len(cells):
                    continue
                try:
                    p = float(re.sub(r"[^0-9.]", "", cells[price_col]))
                    if 0.5 <= p <= 5.0:  # plausible USD/L for Timor
                        prices.append(p)
                except (ValueError, TypeError):
                    pass

            if not prices:
                continue

            avg_price = round(sum(prices) / len(prices), 4)
            r = tmpl.copy()
            r.update(
                {
                    "fuel_family": family,
                    "fuel_product": prod_name,
                    "quality_group": qg,
                    "octane_ron": ron,
                    "price_local": avg_price,
                    "effective_from": str(obs_date),
                    "effective_to": str(obs_date),
                    "observation_date": str(obs_date),
                    "source_url": url,
                    "notes": f"National average of {len(prices)} station prices",
                }
            )
            r["observation_hash"] = make_hash(r)
            all_rows.append(r)
            print(
                f"  [tl_anp] {prod_name}: avg {avg_price:.4f} USD/L ({len(prices)} stations) on {obs_date}"
            )

    if not all_rows:
        # Fallback: extract prices from plain text
        for prod_name, family, qg, ron, prod_pat in PRODUCTS:
            pattern = rf"{prod_pat}[^\d]{{0,80}}(\d+\.\d{{2,3}})"
            matches = re.findall(pattern, text, re.IGNORECASE | re.DOTALL)
            prices = [float(p) for p in matches if 0.5 <= float(p) <= 5.0]
            if prices:
                avg_price = round(sum(prices) / len(prices), 4)
                r = tmpl.copy()
                r.update(
                    {
                        "fuel_family": family,
                        "fuel_product": prod_name,
                        "quality_group": qg,
                        "price_local": avg_price,
                        "effective_from": str(obs_date),
                        "effective_to": str(obs_date),
                        "observation_date": str(obs_date),
                        "source_url": url,
                    }
                )
                r["observation_hash"] = make_hash(r)
                all_rows.append(r)

    if not all_rows:
        print("  [tl_anp] No new Timor ANP rows extracted")

    return pd.DataFrame(all_rows) if all_rows else pd.DataFrame()


# ---------- Papua New Guinea ICCC ----------


def fetch_png_iccc_2026(df_existing: pd.DataFrame) -> pd.DataFrame:
    """
    Fetch Papua New Guinea ICCC Indicative Retail Fuel Prices for 2026.

    ICCC publishes monthly Port Moresby fuel prices at:
    https://iccc.gov.pg/category/fuel-prices/
    Each post contains a table or text with petrol, diesel, kerosene prices in PGK/L.
    """
    print("  [png_iccc] Fetching PNG ICCC 2026 data...")
    cutoff = last_date(df_existing, "pg_iccc_monthly_irp")
    print(f"  [png_iccc] Last existing date: {cutoff}")

    session = get_session()
    listing_url = "https://iccc.gov.pg/category/fuel-prices/"

    try:
        resp = session.get(listing_url, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        print(f"  [png_iccc] Could not fetch listing: {e}")
        return pd.DataFrame()

    soup = BeautifulSoup(resp.content, "lxml")

    # Collect article links from the category page
    article_links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if (
            "iccc.gov.pg" in href
            and "/fuel-price" in href
            and href not in article_links
        ):
            article_links.append(href)
        elif href.startswith("/") and "/fuel-price" in href:
            full = "https://iccc.gov.pg" + href
            if full not in article_links:
                article_links.append(full)

    # Also check for pagination
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "category/fuel-prices/page/" in href:
            try:
                r2 = session.get(href, timeout=20)
                if r2.status_code == 200:
                    s2 = BeautifulSoup(r2.content, "lxml")
                    for a2 in s2.find_all("a", href=True):
                        h2 = a2["href"]
                        if (
                            "iccc.gov.pg" in h2
                            and "/fuel-price" in h2
                            and h2 not in article_links
                        ):
                            article_links.append(h2)
            except Exception:
                pass

    print(f"  [png_iccc] Found {len(article_links)} article links")

    tmpl = base_row("pg_iccc_monthly_irp", df_existing)
    all_rows = []

    PRODUCTS = [
        ("Petrol", "gasoline", "regular", None, r"(?i)petrol|gasoline|mogas"),
        ("Diesel", "diesel", "regular", None, r"(?i)diesel"),
        ("Kerosene", "kerosene", "regular", None, r"(?i)kerosene|kero"),
    ]

    MONTH_MAP = {
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

    for art_url in article_links[:20]:
        try:
            r = session.get(art_url, timeout=20)
            if r.status_code != 200:
                continue
            art_soup = BeautifulSoup(r.content, "lxml")
            text = art_soup.get_text(separator="\n")

            # Extract month/year from title or text
            obs_date = None
            for month_name, month_num in MONTH_MAP.items():
                if month_name in text.lower():
                    year_m = re.search(r"\b(20\d{2})\b", text)
                    if year_m:
                        try:
                            obs_date = date(int(year_m.group(1)), month_num, 1)
                            break
                        except ValueError:
                            pass

            if obs_date is None or obs_date <= cutoff:
                continue

            # Extract prices (PGK/L, typically 3–6 PGK/L)
            rows_added = 0
            for prod_name, family, qg, ron, prod_pat in PRODUCTS:
                m = re.search(
                    rf"{prod_pat}[^\d]{{0,100}}([\d]+\.[\d]{{2,3}})",
                    text,
                    re.IGNORECASE | re.DOTALL,
                )
                if not m:
                    continue
                try:
                    price = float(m.group(1))
                    if not (1.0 <= price <= 20.0):  # plausible PGK/L
                        continue
                except ValueError:
                    continue

                r_row = tmpl.copy()
                r_row.update(
                    {
                        "fuel_family": family,
                        "fuel_product": prod_name,
                        "quality_group": qg,
                        "octane_ron": ron,
                        "price_local": price,
                        "effective_from": str(obs_date),
                        "effective_to": str(
                            (obs_date.replace(day=28) + timedelta(days=4)).replace(
                                day=1
                            )
                            - timedelta(days=1)
                        ),
                        "observation_date": str(obs_date),
                        "source_url": art_url,
                    }
                )
                r_row["observation_hash"] = make_hash(r_row)
                all_rows.append(r_row)
                rows_added += 1

            if rows_added:
                print(f"  [png_iccc] {obs_date}: {rows_added} products from {art_url}")

        except Exception as e:
            print(f"  [png_iccc] Error {art_url}: {e}")
        time.sleep(0.3)

    if not all_rows:
        print("  [png_iccc] No new PNG ICCC rows extracted")

    return pd.DataFrame(all_rows) if all_rows else pd.DataFrame()


# ---------- Samoa MOF ----------


def fetch_samoa_mof_2026(df_existing: pd.DataFrame) -> pd.DataFrame:
    """
    Fetch Samoa Ministry of Finance monthly fuel prices for 2026.

    MOF publishes monthly press releases at https://www.mof.gov.ws/press-releases-mof
    Each release contains petrol, diesel, kerosene prices in WST/L.
    """
    print("  [ws_mof] Fetching Samoa MOF 2026 data...")
    cutoff = last_date(df_existing, "ws_mof_monthly_fuel_prices")
    print(f"  [ws_mof] Last existing date: {cutoff}")

    session = get_session()
    listing_url = "https://www.mof.gov.ws/press-releases-mof"

    try:
        resp = session.get(listing_url, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        print(f"  [ws_mof] Could not fetch listing: {e}")
        return pd.DataFrame()

    soup = BeautifulSoup(resp.content, "lxml")

    # Collect press release links containing "fuel" or "petroleum"
    article_links = []
    seen = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        link_text = a.get_text(strip=True).lower()
        if any(
            kw in link_text or kw in href.lower()
            for kw in ["fuel", "petrol", "diesel", "price"]
        ):
            full = href if href.startswith("http") else "https://www.mof.gov.ws" + href
            if full not in seen:
                seen.add(full)
                article_links.append(full)

    print(f"  [ws_mof] Found {len(article_links)} candidate article links")

    tmpl = base_row("ws_mof_monthly_fuel_prices", df_existing)
    all_rows = []

    PRODUCTS = [
        ("Petrol", "gasoline", "regular", None, r"(?i)\bpetrol\b|\bgasoline\b"),
        ("Diesel", "diesel", "regular", None, r"(?i)\bdiesel\b"),
        ("Kerosene", "kerosene", "regular", None, r"(?i)\bkerosene\b|\bkero\b"),
    ]

    MONTH_MAP = {
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

    for art_url in article_links[:20]:
        try:
            r = session.get(art_url, timeout=20)
            if r.status_code != 200:
                continue
            art_soup = BeautifulSoup(r.content, "lxml")
            text = art_soup.get_text(separator="\n")

            # Extract month/year
            obs_date = None
            for month_name, month_num in MONTH_MAP.items():
                if month_name in text.lower():
                    year_m = re.search(r"\b(20\d{2})\b", text)
                    if year_m:
                        try:
                            obs_date = date(int(year_m.group(1)), month_num, 1)
                            break
                        except ValueError:
                            pass

            if obs_date is None or obs_date <= cutoff:
                continue

            rows_added = 0
            for prod_name, family, qg, ron, prod_pat in PRODUCTS:
                # Look for price near product keyword (WST/L, typically 3–7 WST/L)
                m = re.search(
                    rf"{prod_pat}[^\d]{{0,150}}(\d+\.\d{{2,3}})",
                    text,
                    re.IGNORECASE | re.DOTALL,
                )
                if not m:
                    continue
                try:
                    price = float(m.group(1))
                    if not (1.0 <= price <= 15.0):
                        continue
                except ValueError:
                    continue

                r_row = tmpl.copy()
                r_row.update(
                    {
                        "fuel_family": family,
                        "fuel_product": prod_name,
                        "quality_group": qg,
                        "octane_ron": ron,
                        "price_local": price,
                        "effective_from": str(obs_date),
                        "effective_to": str(
                            (obs_date.replace(day=28) + timedelta(days=4)).replace(
                                day=1
                            )
                            - timedelta(days=1)
                        ),
                        "observation_date": str(obs_date),
                        "source_url": art_url,
                    }
                )
                r_row["observation_hash"] = make_hash(r_row)
                all_rows.append(r_row)
                rows_added += 1

            if rows_added:
                print(f"  [ws_mof] {obs_date}: {rows_added} products from {art_url}")

        except Exception as e:
            print(f"  [ws_mof] Error {art_url}: {e}")
        time.sleep(0.3)

    if not all_rows:
        print("  [ws_mof] No new Samoa MOF rows extracted")

    return pd.DataFrame(all_rows) if all_rows else pd.DataFrame()


# ---------- Vanuatu DOE ----------


def fetch_vanuatu_doe_2026(df_existing: pd.DataFrame) -> pd.DataFrame:
    """
    Fetch Vanuatu Department of Energy retail fuel prices for 2026.

    DOE publishes fuel price notices at https://doe.gov.vu/index.php/news-events/news
    Prices in VUV/L for petrol and diesel.
    """
    print("  [vu_doe] Fetching Vanuatu DOE 2026 data...")
    cutoff = last_date(df_existing, "vu_doe_retail_petrol_diesel_2025")
    print(f"  [vu_doe] Last existing date: {cutoff}")

    session = get_session()
    listing_url = "https://doe.gov.vu/index.php/news-events/news"

    try:
        resp = session.get(listing_url, timeout=30, verify=False)
        resp.raise_for_status()
    except Exception as e:
        print(f"  [vu_doe] Could not fetch listing: {e}")
        return pd.DataFrame()

    soup = BeautifulSoup(resp.content, "lxml")

    article_links = []
    seen = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        link_text = a.get_text(strip=True).lower()
        if any(
            kw in link_text or kw in href.lower()
            for kw in ["fuel", "petrol", "diesel", "price"]
        ):
            full = href if href.startswith("http") else "https://doe.gov.vu" + href
            if full not in seen:
                seen.add(full)
                article_links.append(full)

    # Also collect all news links and scan them
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "doe.gov.vu" in href and "/news" in href and href not in seen:
            seen.add(href)
            article_links.append(href)
        elif href.startswith("/") and "/news" in href:
            full = "https://doe.gov.vu" + href
            if full not in seen:
                seen.add(full)
                article_links.append(full)

    print(f"  [vu_doe] Found {len(article_links)} candidate links")

    tmpl = base_row("vu_doe_retail_petrol_diesel_2025", df_existing)
    all_rows = []

    PRODUCTS = [
        (
            "Unleaded Petrol 95RON",
            "gasoline",
            "premium",
            95,
            r"(?i)(unleaded|petrol|gasoline|essence)",
        ),
        ("Low Sulphur Diesel 10PPM", "diesel", "regular", None, r"(?i)diesel|gasoil"),
    ]

    MONTH_MAP = {
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

    for art_url in article_links[:25]:
        try:
            r = session.get(art_url, timeout=20, verify=False)
            if r.status_code != 200:
                continue
            art_soup = BeautifulSoup(r.content, "lxml")
            text = art_soup.get_text(separator="\n")

            if not any(kw in text.lower() for kw in ["fuel", "petrol", "diesel"]):
                continue

            # Extract date
            obs_date = None
            for month_name, month_num in MONTH_MAP.items():
                if month_name in text.lower():
                    year_m = re.search(r"\b(20\d{2})\b", text)
                    if year_m:
                        try:
                            obs_date = date(int(year_m.group(1)), month_num, 1)
                            break
                        except ValueError:
                            pass
            if obs_date is None:
                iso_m = re.search(r"(20\d{2})[/\-](\d{2})[/\-](\d{2})", text)
                if iso_m:
                    try:
                        obs_date = date(
                            int(iso_m.group(1)),
                            int(iso_m.group(2)),
                            int(iso_m.group(3)),
                        )
                    except ValueError:
                        pass

            if obs_date is None or obs_date <= cutoff:
                continue

            rows_added = 0
            for prod_name, family, qg, ron, prod_pat in PRODUCTS:
                # VUV/L typically 150–250
                m = re.search(
                    rf"{prod_pat}[^\d]{{0,150}}(\d{{3,4}}(?:\.\d{{1,2}})?)",
                    text,
                    re.IGNORECASE | re.DOTALL,
                )
                if not m:
                    continue
                try:
                    price = float(m.group(1))
                    if not (100 <= price <= 500):
                        continue
                except ValueError:
                    continue

                r_row = tmpl.copy()
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
                print(f"  [vu_doe] {obs_date}: {rows_added} products from {art_url}")

        except Exception as e:
            print(f"  [vu_doe] Error {art_url}: {e}")
        time.sleep(0.3)

    if not all_rows:
        print("  [vu_doe] No new Vanuatu DOE rows extracted")

    return pd.DataFrame(all_rows) if all_rows else pd.DataFrame()


# ---------- Solomon Islands price control ----------


def fetch_solomon_islands_2026(df_existing: pd.DataFrame) -> pd.DataFrame:
    """
    Fetch Solomon Islands gazette petroleum and LPG price-control orders for 2026.

    The Solomon Islands Government site at https://solomons.gov.sb/ publishes
    price control gazette notices. We scan the site for petroleum and LPG notices.
    """
    print("  [sb] Fetching Solomon Islands 2026 data...")

    SOURCES = {
        "sb_price_control_petroleum_2025": {
            "products": [
                ("Diesel (ADO)", "diesel", None, None, r"(?i)diesel|ado|automotive"),
                (
                    "Petrol (PMS)",
                    "gasoline",
                    "regular",
                    None,
                    r"(?i)petrol|pms|motor spirit",
                ),
            ],
            "price_range": (5, 30),  # SBD/L
        },
        "sb_price_control_lpg_2025": {
            "products": [
                ("Propane LPG", "lpg", "regular", None, r"(?i)lpg|propane"),
            ],
            "price_range": (10, 200),  # SBD/kg
        },
    }

    session = get_session()
    base_url = "https://solomons.gov.sb/"
    all_rows_by_source: dict = {sk: [] for sk in SOURCES}

    MONTH_MAP = {
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

    # Scan the government site for fuel/price control notices
    scan_urls = [
        base_url,
        base_url + "category/media-releases/",
        base_url + "category/press-releases/",
        base_url + "search/?q=fuel+price",
        base_url + "search/?q=price+control+petroleum",
        base_url + "search/?q=lpg+price",
    ]

    article_links = set()
    for scan_url in scan_urls:
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
                    for kw in ["fuel", "petrol", "diesel", "lpg", "price control"]
                ):
                    full = (
                        href
                        if href.startswith("http")
                        else base_url.rstrip("/") + "/" + href.lstrip("/")
                    )
                    article_links.add(full)
        except Exception:
            pass
        time.sleep(0.3)

    print(f"  [sb] Found {len(article_links)} candidate links")

    for art_url in list(article_links)[:30]:
        try:
            r = session.get(art_url, timeout=20)
            if r.status_code != 200:
                continue
            art_soup = BeautifulSoup(r.content, "lxml")
            text = art_soup.get_text(separator="\n")

            if not any(
                kw in text.lower() for kw in ["fuel", "petrol", "diesel", "lpg"]
            ):
                continue

            # Determine which source this belongs to
            is_lpg = bool(re.search(r"(?i)\blpg\b|\bpropane\b", text))
            is_petrol = bool(
                re.search(r"(?i)\bpetrol\b|\bdiesel\b|\bpms\b|\bado\b", text)
            )

            # Extract date
            obs_date = None
            for month_name, month_num in MONTH_MAP.items():
                if month_name in text.lower():
                    year_m = re.search(r"\b(20\d{2})\b", text)
                    if year_m:
                        try:
                            obs_date = date(int(year_m.group(1)), month_num, 1)
                            break
                        except ValueError:
                            pass
            if obs_date is None:
                iso_m = re.search(r"(20\d{2})[/\-](\d{2})[/\-](\d{2})", text)
                if iso_m:
                    try:
                        obs_date = date(
                            int(iso_m.group(1)),
                            int(iso_m.group(2)),
                            int(iso_m.group(3)),
                        )
                    except ValueError:
                        pass

            if obs_date is None:
                continue

            for source_key, spec in SOURCES.items():
                cutoff = last_date(df_existing, source_key)
                if obs_date <= cutoff:
                    continue
                if source_key == "sb_price_control_lpg_2025" and not is_lpg:
                    continue
                if source_key == "sb_price_control_petroleum_2025" and not is_petrol:
                    continue

                tmpl = base_row(source_key, df_existing)
                min_p, max_p = spec["price_range"]

                for prod_name, family, qg, ron, prod_pat in spec["products"]:
                    m = re.search(
                        rf"{prod_pat}[^\d]{{0,150}}(\d+(?:\.\d{{1,2}})?)",
                        text,
                        re.IGNORECASE | re.DOTALL,
                    )
                    if not m:
                        continue
                    try:
                        price = float(m.group(1))
                        if not (min_p <= price <= max_p):
                            continue
                    except ValueError:
                        continue

                    r_row = tmpl.copy()
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
                    all_rows_by_source[source_key].append(r_row)

        except Exception as e:
            print(f"  [sb] Error {art_url}: {e}")
        time.sleep(0.2)

    combined = []
    for source_key, rows in all_rows_by_source.items():
        print(f"  [sb] {source_key}: {len(rows)} new rows")
        combined.extend(rows)

    return pd.DataFrame(combined) if combined else pd.DataFrame()


# ---------- Myanmar GNLM ----------


def fetch_myanmar_gnlm_2026(df_existing: pd.DataFrame) -> pd.DataFrame:
    """
    Fetch Myanmar GNLM (Global New Light of Myanmar) fuel reference prices for 2026.

    GNLM publishes weekly reference-price articles at https://www.gnlm.com.mm/
    We scan the news/article listing for fuel price notices (typically in English or Burmese).
    Prices in MMK/L for octane 92/95 and diesel.
    """
    print("  [mm_gnlm] Fetching Myanmar GNLM 2026 data...")
    cutoff = last_date(df_existing, "mm_gnlm_fuel_reference_prices")
    print(f"  [mm_gnlm] Last existing date: {cutoff}")

    session = get_session()
    tmpl = base_row("mm_gnlm_fuel_reference_prices", df_existing)
    all_rows = []
    today = date.today()

    scan_urls = [
        "https://www.gnlm.com.mm/?s=fuel+price",
        "https://www.gnlm.com.mm/?s=petroleum+price",
        "https://www.gnlm.com.mm/?s=petrol+price",
        "https://www.gnlm.com.mm/",
    ]

    PRODUCTS = [
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

    MONTH_MAP = {
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

    article_links = set()
    for scan_url in scan_urls:
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

            # Extract date
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
                for month_name, month_num in MONTH_MAP.items():
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
            for prod_name, family, qg, ron, prod_pat in PRODUCTS:
                # MMK/L: typically 1500–3000 range
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

                r_row = tmpl.copy()
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

    if not all_rows:
        print("  [mm_gnlm] No new Myanmar GNLM rows extracted")

    return pd.DataFrame(all_rows) if all_rows else pd.DataFrame()


# ---------- Philippines DOE ----------


def fetch_philippines_doe_2026(df_existing: pd.DataFrame) -> pd.DataFrame:
    """
    Fetch Philippines DOE retail pump prices for 2026.

    DOE publishes weekly PDF tables at:
    https://doe.gov.ph/site/vfo/articles/group/liquid-fuels?category=Retail+Pump+Prices

    Strategy:
    1. Scrape the listing page for recent PDF/article links
    2. For each article, try to extract prices from HTML body text (summary table)
       or fall back to PDF extraction via pdfplumber if available.
    Prices in PHP/L for RON 91, RON 95, diesel.
    """
    print("  [ph_doe] Fetching Philippines DOE 2026 data...")
    cutoff = last_date(df_existing, "ph_doe_retail_pump_prices")
    print(f"  [ph_doe] Last existing date: {cutoff}")

    session = get_session()
    listing_url = (
        "https://doe.gov.ph/site/vfo/articles/group/liquid-fuels"
        "?category=Retail+Pump+Prices&display_type=Card"
    )

    today = date.today()

    try:
        resp = session.get(listing_url, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        print(f"  [ph_doe] Could not fetch listing: {e}")
        return pd.DataFrame()

    soup = BeautifulSoup(resp.content, "lxml")

    article_links = []
    seen = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if (
            "retail" in href.lower()
            or "pump" in href.lower()
            or "price" in href.lower()
        ):
            full = href if href.startswith("http") else "https://doe.gov.ph" + href
            if full not in seen:
                seen.add(full)
                article_links.append(full)

    print(f"  [ph_doe] Found {len(article_links)} article links")

    tmpl = base_row("ph_doe_retail_pump_prices", df_existing)
    all_rows = []

    PRODUCTS = [
        ("RON 91", "gasoline", "regular", 91, r"(?i)ron.{0,5}91\b|91\b"),
        ("RON95", "gasoline", "premium", 95, r"(?i)ron.{0,5}95\b|95\b"),
        ("DIESEL PLUS", "diesel", "regular", None, r"(?i)diesel\s?plus|diesel\+"),
        ("Diesel", "diesel", "regular", None, r"(?i)\bdiesel\b"),
    ]

    MONTH_MAP = {
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

    for art_url in article_links[:20]:
        try:
            r = session.get(art_url, timeout=30)
            if r.status_code != 200:
                continue

            content_type = r.headers.get("content-type", "")

            if "pdf" in content_type or art_url.lower().endswith(".pdf"):
                # Try PDF extraction via pdfplumber; skip if not available
                try:
                    import pdfplumber  # noqa: PLC0415

                    with pdfplumber.open(BytesIO(r.content)) as pdf:
                        text = "\n".join(p.extract_text() or "" for p in pdf.pages)
                except ImportError:
                    # pdfplumber not installed — attempt raw text extraction fallback
                    try:
                        text = r.content.decode("latin-1", errors="replace")
                        # Strip binary noise: keep only printable ASCII lines
                        lines = [
                            ln
                            for ln in text.splitlines()
                            if ln.isprintable() and len(ln.strip()) > 3
                        ]
                        text = "\n".join(lines)
                    except Exception:
                        continue
                except Exception as e:
                    print(f"  [ph_doe] PDF parse error {art_url}: {e}")
                    continue
            else:
                art_soup = BeautifulSoup(r.content, "lxml")
                text = art_soup.get_text(separator="\n")

            if not any(
                kw in text.lower() for kw in ["petrol", "diesel", "ron", "fuel"]
            ):
                continue

            # Extract date
            obs_date = None
            for month_name, month_num in MONTH_MAP.items():
                if month_name in text.lower():
                    year_m = re.search(r"\b(20\d{2})\b", text)
                    if year_m:
                        try:
                            obs_date = date(int(year_m.group(1)), month_num, 1)
                            break
                        except ValueError:
                            pass
            if obs_date is None:
                iso_m = re.search(r"(20\d{2})[/\-](\d{2})[/\-](\d{2})", text)
                if iso_m:
                    try:
                        obs_date = date(
                            int(iso_m.group(1)),
                            int(iso_m.group(2)),
                            int(iso_m.group(3)),
                        )
                    except ValueError:
                        pass

            if obs_date is None or obs_date <= cutoff or obs_date > today:
                continue

            rows_added = 0
            # PHP/L: typically 40–90
            for prod_name, family, qg, ron, prod_pat in PRODUCTS:
                m = re.search(
                    rf"{prod_pat}[^\d]{{0,150}}(\d{{2,3}}(?:\.\d{{1,2}})?)",
                    text,
                    re.IGNORECASE | re.DOTALL,
                )
                if not m:
                    continue
                try:
                    price = float(m.group(1))
                    if not (30 <= price <= 120):
                        continue
                except ValueError:
                    continue

                r_row = tmpl.copy()
                r_row.update(
                    {
                        "fuel_family": family,
                        "fuel_product": prod_name,
                        "quality_group": qg,
                        "octane_ron": ron,
                        "price_local": price,
                        "effective_from": str(obs_date),
                        "effective_to": str(obs_date + timedelta(days=6)),
                        "observation_date": str(obs_date),
                        "source_url": art_url,
                    }
                )
                r_row["observation_hash"] = make_hash(r_row)
                all_rows.append(r_row)
                rows_added += 1

            if rows_added:
                print(f"  [ph_doe] {obs_date}: {rows_added} products from {art_url}")

        except Exception as e:
            print(f"  [ph_doe] Error {art_url}: {e}")
        time.sleep(0.4)

    if not all_rows:
        print("  [ph_doe] No new Philippines DOE rows extracted")

    return pd.DataFrame(all_rows) if all_rows else pd.DataFrame()


# ── Step 3: Deduplicate and merge ──────────────────────────────────────────────


def merge_new_rows(
    df_existing: pd.DataFrame, new_rows: pd.DataFrame, source_name: str
) -> pd.DataFrame:
    """Append new rows, deduplicating by observation_hash."""
    if new_rows.empty:
        return df_existing

    existing_hashes = set(df_existing["observation_hash"].dropna())

    if "observation_hash" not in new_rows.columns:
        new_rows = new_rows.copy()
        new_rows["observation_hash"] = new_rows.apply(make_hash, axis=1)

    new_unique = new_rows[~new_rows["observation_hash"].isin(existing_hashes)].copy()
    dupes = len(new_rows) - len(new_unique)

    if new_unique.empty:
        print(
            f"  [{source_name}] All {len(new_rows)} fetched rows are duplicates — no changes"
        )
        return df_existing

    print(
        f"  [{source_name}] Appending {len(new_unique)} new rows "
        f"({dupes} duplicates dropped)"
    )

    # Align columns
    for col in df_existing.columns:
        if col not in new_unique.columns:
            new_unique[col] = None
    new_unique = new_unique[df_existing.columns]

    combined = pd.concat([df_existing, new_unique], ignore_index=True)
    combined = combined.sort_values(
        ["country", "source_key", "observation_date"]
    ).reset_index(drop=True)

    return combined


# ── Main ───────────────────────────────────────────────────────────────────────


def main():
    print(f"Loading {CSV_PATH} ...")
    df = pd.read_csv(CSV_PATH, low_memory=False)
    orig_len = len(df)
    print(f"  {orig_len:,} rows loaded")

    # ── Step 1: Apply fixes ────────────────────────────────────────────────────
    print("\nStep 1: Applying data fixes...")
    df = fix_australia_units(df)
    df = fix_quality_group(df)
    df = fix_anre_kerosene_unit(df)
    df = fix_fuel_family(df)
    df = fix_column_homogenization(df)

    # ── Step 2: Fetch new data ─────────────────────────────────────────────────
    print("\nStep 2: Fetching new data from official sources...")

    FETCHERS = [
        ("Japan ANRE", "jp_anre_weekly_petroleum_2025", fetch_anre_2026),
        (
            "Indonesia Pertamina",
            "id_pertamina_jakarta_2025_series",
            fetch_pertamina_2026,
        ),
        ("Malaysia MOF", "my_mof_weekly_petroleum", fetch_malaysia_mof_2026),
        ("Cambodia MOC", "kh_moc_fuel_notices", fetch_cambodia_moc_2026),
        ("Lao State Fuel", "lao_state_fuel_oil_prices", fetch_lao_2026),
        (
            "Korea Opinet",
            "kr_opinet_weekly_national_sampled_2025",
            fetch_korea_opinet_2026,
        ),
        ("Fiji FCCC", "fiji_fccc_monthly_prices", fetch_fiji_fccc_2026),
        ("Australia ACCC", "au_accc_5largestcities_quarterly", fetch_accc_2026),
        ("Mongolia data.mn", "mn_data_mn_a92_aimags", fetch_mongolia_data_mn_2026),
        ("New Zealand MBIE", "nz_mbie_weekly_fuel", fetch_nz_mbie_2026),
        ("Thailand EPPO NGV", "th_eppo_ngv_bangkok_2025", fetch_thailand_eppo_ngv_2026),
        ("Timor-Leste ANP", "tl_anp_daily_fuel_price", fetch_timor_anp_2026),
        ("PNG ICCC", "pg_iccc_monthly_irp", fetch_png_iccc_2026),
        ("Samoa MOF", "ws_mof_monthly_fuel_prices", fetch_samoa_mof_2026),
        ("Vanuatu DOE", "vu_doe_retail_petrol_diesel_2025", fetch_vanuatu_doe_2026),
        (
            "Solomon Islands",
            "sb_price_control_petroleum_2025",
            fetch_solomon_islands_2026,
        ),
        ("Myanmar GNLM", "mm_gnlm_fuel_reference_prices", fetch_myanmar_gnlm_2026),
        ("Philippines DOE", "ph_doe_retail_pump_prices", fetch_philippines_doe_2026),
    ]

    for display_name, source_key, fetcher in FETCHERS:
        print(f"\n  --- {display_name} ---")
        try:
            new_rows = fetcher(df)
            if new_rows is not None and not new_rows.empty:
                df = merge_new_rows(df, new_rows, display_name)
            else:
                print(f"  [{display_name}] No new rows returned")
        except Exception as e:
            print(f"  [{display_name}] Unhandled error: {e}")

    # ── Step 3: Save ───────────────────────────────────────────────────────────
    added = len(df) - orig_len
    print(f"\nStep 3: Saving {len(df):,} rows (+{added:,} new) to {CSV_PATH} ...")
    df.to_csv(CSV_PATH, index=False)
    print("Done.")

    # ── Verification summary ───────────────────────────────────────────────────
    print("\n=== Verification ===")
    print("Australia price range (should be 1.5–2.5 AUD):")
    au = df[(df["country"] == "Australia") & (df["currency"] == "AUD")]
    if not au.empty:
        print(
            f"  min={au['price_local'].min():.3f}, max={au['price_local'].max():.3f}, "
            f"rows={len(au)}"
        )
    residual_audc = df[df["currency"] == "AUDc"]
    if not residual_audc.empty:
        print(f"  WARNING: {len(residual_audc)} residual AUDc rows still present!")

    print("\nJapan ANRE kerosene price range (should be ~125–145 JPY/L after fix):")
    jp_ker = df[
        (df["source_key"] == "jp_anre_weekly_petroleum_2025")
        & df["fuel_product"].str.startswith("Kerosene", na=False)
    ]
    if not jp_ker.empty:
        print(
            f"  min={jp_ker['price_local'].min():.2f}, max={jp_ker['price_local'].max():.2f} JPY/L"
        )
    residual_18l = df[df["unit"] == "18L"]
    if not residual_18l.empty:
        print(f"  WARNING: {len(residual_18l)} residual 18L unit rows still present!")

    print("\nMax observation_date by official source:")
    official_keys = [sk for _, sk, _ in FETCHERS]
    src_dates = (
        df[df["source_key"].isin(official_keys)]
        .groupby("source_key")["observation_date"]
        .max()
        .sort_values()
    )
    for src, max_d in src_dates.items():
        print(f"  {src}: {max_d}")

    print(
        "\nNull quality_group counts for diesel sources (should be 0 for fixed sources):"
    )
    check_sources = [
        "jp_anre_weekly_petroleum_2025",
        "my_mof_weekly_petroleum",
        "ph_doe_retail_pump_prices",
        "id_pertamina_jakarta_2025_series",
        "fiji_fccc_monthly_prices",
        "kh_moc_fuel_notices",
    ]
    for src in check_sources:
        null_q = df[
            (df["source_key"] == src)
            & (df["fuel_family"] == "diesel")
            & df["quality_group"].isna()
        ]
        status = "OK" if null_q.empty else f"WARNING: {len(null_q)} nulls"
        print(f"  {src}: {status}")


if __name__ == "__main__":
    main()
