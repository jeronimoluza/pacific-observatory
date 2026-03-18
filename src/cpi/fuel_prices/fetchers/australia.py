"""Australia fuel price fetchers: AIP Terminal Gate Prices + ACCC quarterly retail + FuelWatch historic."""

# ruff: noqa: E402
SOURCE_META = [
    {
        "fetcher_fn": "fetch_au_aip_tgp",
        "country": "Australia",
        "source_name": "AIP Terminal Gate Prices",
        "url": "http://www.aip.com.au/historical-ulp-and-diesel-tgp-data",
        "description": "Official industry body (Australian Institute of Petroleum). Weekly wholesale terminal gate prices as Excel. 7 capital cities + national average.",
        "extraction_method": ["Web scraping", "Excel download"],
        "products": ["Gasoline (Regular)", "Diesel"],
        "source_keys": ["au_aip_tgp_weekly"],
        "publishes_on": "Friday",
        "notes": "Scrapes AIP website to find AIP_TGP_Data_*.xlsx link, then parses Excel. Price range AUD 0.50–4.00/L.",
    },
    {
        "fetcher_fn": "fetch_accc",
        "country": "Australia",
        "source_name": "ACCC Quarterly Retail Prices",
        "url": "https://www.accc.gov.au/by-industry/petrol-and-fuel",
        "description": "Official government regulator (ACCC). Quarterly retail price reports as web articles. Average across 5 largest cities.",
        "extraction_method": ["Web scraping"],
        "products": ["Gasoline (Regular)", "Diesel"],
        "source_keys": ["au_accc_5largestcities_quarterly"],
        "publishes_on": "Quarterly (Jan/Apr/Jul/Oct)",
        "notes": "Extracts price via regex (c/L pattern) from article body text. Fetches up to 5 most recent quarterly reports.",
    },
    {
        "fetcher_fn": "fetch_au_fuelwatch_perth",
        "country": "Australia",
        "source_name": "FuelWatch WA (Perth) Daily Prices",
        "url": "https://www.fuelwatch.wa.gov.au/fuelwatch/fuelWatchRSS",
        "description": "Western Australia government FuelWatch RSS feed. Aggregates station-level prices into a daily mean for Perth (North of River + South of River).",
        "extraction_method": ["RSS/XML"],
        "products": ["Unleaded", "Diesel"],
        "source_keys": ["au_fuelwatch_perth_daily"],
        "publishes_on": "Daily",
        "notes": "Fetches RSS for (Product=1,4) across Region=25 (North of River) and Region=26 (South of River). Converts cents/L to AUD/L and stores mean + station count in notes.",
    },
    {
        "fetcher_fn": "fetch_au_nsw_fuelcheck_history",
        "country": "Australia",
        "source_name": "NSW FuelCheck price history",
        "url": "https://data.nsw.gov.au/data/dataset/fuel-check",
        "description": "Official NSW government FuelCheck price history from Data.NSW (CKAN). Station-level prices with product codes.",
        "extraction_method": ["CKAN API", "CSV/XLSX download"],
        "products": ["Gasoline (E10/U91/P95/P98/E20/E85)", "Diesel", "LPG"],
        "source_keys": ["au_nsw_fuelcheck_history"],
        "publishes_on": "Monthly",
        "notes": "Selects most recent machine-readable resource (prefers price_history_checks_*.csv). Converts cents/L to AUD/L when needed; station details stored in notes.",
    },
    {
        "fetcher_fn": "fetch_au_fuelwatch_historic_csv",
        "country": "Australia",
        "source_name": "FuelWatch WA (Perth) Historic CSV",
        "url": "https://warsydprdstafuelwatch.blob.core.windows.net/historical-reports/",
        "description": "Western Australia government FuelWatch historic monthly CSVs from Azure Blob Storage. Station-level daily prices aggregated to Perth Metro regional means.",
        "extraction_method": ["CSV download"],
        "products": ["Unleaded", "Diesel"],
        "source_keys": ["au_fuelwatch_perth_daily"],
        "publishes_on": "Monthly (historic archive)",
        "notes": "Downloads monthly CSV (FuelWatchRetail-MM-YYYY.csv). Filters to Perth Metro (North of River + South of River), ULP + Diesel. Aggregates station prices to daily mean. Converts cents/L to AUD/L.",
    },
]

import io
import re
import time
from datetime import date, timedelta
from xml.etree import ElementTree as ET

import pandas as pd
from bs4 import BeautifulSoup

from ..utils import get_session, make_hash, make_template

# ── AIP Terminal Gate Prices (wholesale) ─────────────────────────────────────

_TMPL_AU_AIP = make_template(
    country="Australia",
    wb_iso3="AUS",
    source_key="au_aip_tgp_weekly",
    source_name="Australian Institute of Petroleum (AIP) Terminal Gate Prices",
    source_url="https://www.aip.com.au/aip-tgp-data",
    currency="AUD",
    unit="L",
    subnational_area="National",
    consumer_segment="wholesale",
    publication_frequency="weekly",
)

_AU_SHEET_MAP = {
    "petrol tgp": ("Unleaded", "gasoline", "regular", None),
    "diesel tgp": ("Diesel", "diesel", "regular", None),
}
_AU_NATIONAL_COL = 8

_AU_CITY_COLS = {
    1: ("Sydney", "Sydney"),
    2: ("Melbourne", "Melbourne"),
    3: ("Brisbane", "Brisbane"),
    4: ("Adelaide", "Adelaide"),
    5: ("Perth", "Perth"),
    6: ("Darwin", "Darwin"),
    7: ("Hobart", "Hobart"),
    8: (None, "National"),
}


def fetch_au_aip_tgp(cutoff: date) -> pd.DataFrame:
    """Fetch Australia AIP daily Terminal Gate Prices from Excel (full refresh)."""
    print("  [au_aip] Fetching AIP TGP data...")

    session = get_session()
    excel_url = None
    for page in [
        "http://www.aip.com.au/historical-ulp-and-diesel-tgp-data",
        "https://www.aip.com.au/pricing/terminal-gate-prices",
    ]:
        try:
            resp = session.get(page, timeout=20)
            if resp.status_code != 200:
                continue
            soup = BeautifulSoup(resp.content, "lxml")
            for a in soup.find_all("a", href=True):
                href = str(a.get("href") or "")
                href_lower = href.lower()
                if "AIP_TGP_Data_" in href and href_lower.endswith(".xlsx"):
                    excel_url = (
                        href
                        if href.startswith("http")
                        else "http://www.aip.com.au" + href
                    )
                    break
            if excel_url:
                break
        except Exception as e:
            print(f"  [au_aip] Page error {page}: {e}")

    if excel_url is None:
        print("  [au_aip] No weekly TGP Excel link found")
        return pd.DataFrame()

    excel_url = str(excel_url)
    print(f"  [au_aip] Downloading: {excel_url}")
    try:
        resp = session.get(excel_url, timeout=60)
        resp.raise_for_status()
    except Exception as e:
        print(f"  [au_aip] Download error: {e}")
        return pd.DataFrame()

    content = resp.content
    all_rows = []

    try:
        xf = pd.ExcelFile(io.BytesIO(content))
    except Exception as e:
        print(f"  [au_aip] Excel open error: {e}")
        return pd.DataFrame()

    for sheet in xf.sheet_names:
        sheet_lower = sheet.lower()
        if sheet_lower not in _AU_SHEET_MAP:
            continue
        prod_name, family, qg, ron = _AU_SHEET_MAP[sheet_lower]

        try:
            raw = pd.read_excel(io.BytesIO(content), sheet_name=sheet, header=0)
        except Exception:
            continue

        date_col_name = raw.columns[0]
        nat_col_name = (
            raw.columns[_AU_NATIONAL_COL] if raw.shape[1] > _AU_NATIONAL_COL else None
        )
        if nat_col_name is None:
            nat_col_name = next(
                (c for c in raw.columns if "national" in str(c).lower()), None
            )
        if nat_col_name is None:
            continue

        raw["_date"] = pd.to_datetime(raw[date_col_name], errors="coerce")
        new_mask = raw["_date"].dt.date > cutoff
        if not new_mask.any():
            print(f"  [au_aip] Sheet '{sheet}': no rows after cutoff {cutoff}")
            continue

        rows_this_sheet = 0
        for _, row in raw[new_mask].iterrows():
            obs_date = row["_date"].date()
            for col_idx, (city_name, sub_area) in _AU_CITY_COLS.items():
                if col_idx >= len(raw.columns):
                    continue
                col_name = raw.columns[col_idx]
                try:
                    price_cpl = float(row[col_name])
                except (ValueError, TypeError):
                    continue
                if pd.isna(price_cpl) or price_cpl <= 0:
                    continue
                price = round(price_cpl / 100, 4)
                if not (0.5 <= price <= 4.0):
                    continue

                r = _TMPL_AU_AIP.copy()
                r.update(
                    {
                        "fuel_family": family,
                        "fuel_product": prod_name,
                        "quality_group": qg,
                        "octane_ron": ron,
                        "city": city_name,
                        "subnational_area": sub_area,
                        "price_local": price,
                        "effective_from": str(obs_date),
                        "effective_to": str(obs_date),
                        "observation_date": str(obs_date),
                        "source_url": excel_url,
                    }
                )
                r["observation_hash"] = make_hash(r)
                all_rows.append(r)
                rows_this_sheet += 1

        print(f"  [au_aip] Sheet '{sheet}': {rows_this_sheet} new rows")

    if not all_rows:
        print("  [au_aip] No new AIP TGP rows")
    return pd.DataFrame(all_rows) if all_rows else pd.DataFrame()


# ── ACCC quarterly retail prices ─────────────────────────────────────────────

_TMPL_AU_ACCC = make_template(
    country="Australia",
    wb_iso3="AUS",
    source_key="au_accc_5largestcities_quarterly",
    source_name="ACCC Petrol Monitoring — 5 Largest Cities Quarterly Average",
    source_url="https://www.accc.gov.au/by-industry/petrol-and-fuel",
    currency="AUD",
    unit="L",
    subnational_area="National",
    consumer_segment="retail",
    publication_frequency="quarterly",
    observation_method="reported",
)


def fetch_accc(cutoff: date) -> pd.DataFrame:
    """Fetch Australia ACCC quarterly retail fuel prices."""
    print("  [accc] Fetching Australia ACCC data...")
    print(f"  [accc] Cutoff: {cutoff}")

    today = date.today()
    session = get_session()

    monitoring_url = "https://www.accc.gov.au/by-industry/petrol-and-fuel"
    try:
        resp = session.get(monitoring_url, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        print(f"  [accc] Could not fetch ACCC monitoring page: {e}")
        return pd.DataFrame()

    soup = BeautifulSoup(resp.content, "lxml")
    report_links = []
    for a in soup.find_all("a", href=True):
        href = str(a.get("href") or "")
        text_link = str(a.get_text(strip=True) or "").lower()
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

            cpl_match = re.search(
                r"(\d{3}\.\d)\s*(?:cents per litre|cpl)", text, re.IGNORECASE
            )
            if not cpl_match:
                cpl_candidates = re.findall(r"\b(\d{3}\.\d)\b", text)
                valid = [float(p) for p in cpl_candidates if 130 <= float(p) <= 280]
                if not valid:
                    print(f"  [accc] No price found in {url}")
                    continue
                avg_cpl = valid[0]
            else:
                avg_cpl = float(cpl_match.group(1))

            avg_price = round(avg_cpl / 100, 4)

            for prod_name, family, qg in PRODUCTS:
                for day_offset in range((eff_to - eff_from).days + 1):
                    obs_date = eff_from + timedelta(days=day_offset)
                    if obs_date > today:
                        break
                    r_row = _TMPL_AU_ACCC.copy()
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

            print(f"  [accc] {eff_from}–{eff_to}: {avg_cpl} cpl -> AUD {avg_price}/L")

        except Exception as e:
            print(f"  [accc] Error processing {url}: {e}")
        time.sleep(0.5)

    if not all_rows:
        print("  [accc] No new ACCC rows extracted")
    return pd.DataFrame(all_rows) if all_rows else pd.DataFrame()


# ── FuelWatch (WA) daily retail prices via RSS ───────────────────────────────

_FUELWATCH_BASE = "https://www.fuelwatch.wa.gov.au/fuelwatch/fuelWatchRSS"

_TMPL_AU_FUELWATCH = make_template(
    country="Australia",
    wb_iso3="AUS",
    source_key="au_fuelwatch_perth_daily",
    source_name="FuelWatch WA (Perth) Daily Prices",
    source_url=_FUELWATCH_BASE,
    currency="AUD",
    unit="L",
    consumer_segment="retail",
    publication_frequency="daily",
    observation_method="compiled",
    source_type="official",
)

_FUELWATCH_REGIONS = {
    25: "North of River",
    26: "South of River",
}

_FUELWATCH_PRODUCTS = {
    # product_id: (fuel_product, fuel_family, quality_group, octane_ron)
    1: ("Unleaded", "gasoline", "regular", None),
    4: ("Diesel", "diesel", "regular", None),
}


def _fuelwatch_rss_url(product_id: int, region_id: int) -> str:
    return f"{_FUELWATCH_BASE}?Product={product_id}&Region={region_id}"


def _parse_fuelwatch_rss(xml_bytes: bytes) -> tuple[date | None, list[float]]:
    """Return (observation_date, prices_cpl) from FuelWatch RSS XML."""
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return None, []

    prices: list[float] = []
    obs_date: date | None = None

    for item in root.findall("./channel/item"):
        d = (item.findtext("date") or "").strip()
        if d and obs_date is None:
            try:
                obs_date = date.fromisoformat(d)
            except ValueError:
                obs_date = None

        p = (item.findtext("price") or "").strip()
        try:
            val = float(p)
        except ValueError:
            continue
        # cents per litre range sanity
        if 20.0 <= val <= 400.0:
            prices.append(val)

    return obs_date, prices


def fetch_au_fuelwatch_perth(cutoff: date) -> pd.DataFrame:
    """Fetch WA FuelWatch RSS and aggregate Perth region daily averages."""
    print("  [au_fuelwatch] Fetching FuelWatch WA RSS (Perth)...")
    print(f"  [au_fuelwatch] Cutoff: {cutoff}")

    session = get_session()
    all_rows: list[dict] = []

    for region_id, region_name in _FUELWATCH_REGIONS.items():
        for product_id, (prod_name, family, qg, ron) in _FUELWATCH_PRODUCTS.items():
            url = _fuelwatch_rss_url(product_id, region_id)
            try:
                resp = session.get(url, timeout=30)
                resp.raise_for_status()
            except Exception as e:
                print(f"  [au_fuelwatch] Could not fetch {url}: {e}")
                continue

            obs_date, prices_cpl = _parse_fuelwatch_rss(resp.content)
            if obs_date is None:
                print(f"  [au_fuelwatch] Missing observation date in {url}")
                continue
            if obs_date <= cutoff:
                continue

            if not prices_cpl:
                print(f"  [au_fuelwatch] No station prices in {url}")
                continue

            mean_cpl = sum(prices_cpl) / len(prices_cpl)
            price = round(mean_cpl / 100.0, 4)
            if not (0.5 <= price <= 4.0):
                continue

            row = _TMPL_AU_FUELWATCH.copy()
            row.update(
                {
                    "fuel_family": family,
                    "fuel_product": prod_name,
                    "quality_group": qg,
                    "octane_ron": ron,
                    "subnational_area": region_name,
                    "city": "Perth",
                    "price_local": price,
                    "effective_from": str(obs_date),
                    "effective_to": str(obs_date),
                    "observation_date": str(obs_date),
                    "source_url": url,
                }
            )
            row["observation_hash"] = make_hash(row)
            all_rows.append(row)

    if not all_rows:
        print("  [au_fuelwatch] No new rows")
        return pd.DataFrame()

    print(f"  [au_fuelwatch] {len(all_rows)} rows fetched")
    return pd.DataFrame(all_rows)


# ── NSW FuelCheck price history (CKAN) ───────────────────────────────────────

_NSW_FUELCHECK_DATASET_URL = "https://data.nsw.gov.au/data/dataset/fuel-check"
_NSW_FUELCHECK_PACKAGE_URL = (
    "https://data.nsw.gov.au/data/api/3/action/package_show"
    "?id=a97a46fc-2bdd-4b90-ac7f-0cb1e8d7ac3b"
)

_TMPL_AU_NSW_FUELCHECK = make_template(
    country="Australia",
    wb_iso3="AUS",
    source_key="au_nsw_fuelcheck_history",
    source_name="NSW FuelCheck price history",
    source_url=_NSW_FUELCHECK_DATASET_URL,
    currency="AUD",
    unit="L",
    subnational_area="New South Wales",
    publication_frequency="monthly",
    observation_method="reported",
    source_type="official",
)

_FUELCHECK_CODE_MAP = {
    "E10": {
        "fuel_family": "gasoline",
        "fuel_product": "E10",
        "quality_group": "regular",
        "octane_ron": 91,
        "ethanol_pct": 10,
    },
    "U91": {
        "fuel_family": "gasoline",
        "fuel_product": "Unleaded 91",
        "quality_group": "regular",
        "octane_ron": 91,
        "ethanol_pct": 0,
    },
    "P95": {
        "fuel_family": "gasoline",
        "fuel_product": "Premium 95",
        "quality_group": "premium",
        "octane_ron": 95,
        "ethanol_pct": 0,
    },
    "P98": {
        "fuel_family": "gasoline",
        "fuel_product": "Premium 98",
        "quality_group": "premium",
        "octane_ron": 98,
        "ethanol_pct": 0,
    },
    "E85": {
        "fuel_family": "gasoline",
        "fuel_product": "E85",
        "quality_group": None,
        "octane_ron": None,
        "ethanol_pct": 85,
    },
    "E20": {
        "fuel_family": "gasoline",
        "fuel_product": "E20",
        "quality_group": None,
        "octane_ron": None,
        "ethanol_pct": 20,
    },
    "DL": {
        "fuel_family": "diesel",
        "fuel_product": "Diesel",
        "quality_group": "standard",
        "octane_ron": None,
        "ethanol_pct": None,
    },
    "LPG": {
        "fuel_family": "lpg",
        "fuel_product": "LPG",
        "quality_group": "standard",
        "octane_ron": None,
        "ethanol_pct": None,
    },
}


def _clean_text(val) -> str | None:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    text = str(val).strip()
    return text if text else None


def _format_postcode(val) -> str | None:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    if isinstance(val, (int, float)) and float(val).is_integer():
        return str(int(val))
    text = str(val).strip()
    return text if text else None


def _resource_format(resource: dict) -> str:
    fmt = str(resource.get("format") or "").strip().lower()
    if fmt:
        return fmt
    url = str(resource.get("url") or "")
    if "." not in url:
        return ""
    ext = url.split("?")[0].rsplit(".", 1)[-1].lower()
    return ext


_MONTHS_FULL = {
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
_MONTHS_ABBR = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}

_CKAN_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )
}


def _parse_resource_month(resource: dict) -> date | None:
    """Parse the reference month from a FuelCheck CKAN resource name or URL.

    Handles two patterns:
    - Full month in name: "FuelCheck Price History August 2021" → 2021-08-01
    - Abbreviated month in filename: "price_history_checks_jul2024.csv" → 2024-07-01
    """
    name = str(resource.get("name") or "")

    # Full month name at end of resource name field
    m = re.search(r"\b(\w+)\s+(\d{4})\s*$", name, re.IGNORECASE)
    if m:
        month_num = _MONTHS_FULL.get(m.group(1).lower())
        if month_num:
            try:
                return date(int(m.group(2)), month_num, 1)
            except ValueError:
                pass

    # Abbreviated month in filename portion of URL
    url = str(resource.get("url") or "")
    fname = url.split("/")[-1].split("?")[0].lower()
    m = re.search(r"([a-z]{3})(\d{4})", fname)
    if m:
        month_num = _MONTHS_ABBR.get(m.group(1))
        if month_num:
            try:
                return date(int(m.group(2)), month_num, 1)
            except ValueError:
                pass

    return None


def _read_fuelcheck_xlsx(content: bytes) -> pd.DataFrame:
    """Read a FuelCheck XLSX file, auto-detecting the header row.

    Some files have a title row (and sometimes a blank row) before the
    actual column headers:
      - header at row 0: standard layout
      - header at row 1: title in row 0
      - header at row 2: title in row 0, blank in row 1
    """
    preview = pd.read_excel(io.BytesIO(content), header=None, nrows=4)
    header_row = 0
    for i in range(min(4, len(preview))):
        vals = [str(v).strip() for v in preview.iloc[i].values]
        if "FuelCode" in vals or "Price" in vals:
            header_row = i
            break
    return pd.read_excel(io.BytesIO(content), header=header_row)


def fetch_au_nsw_fuelcheck_history(cutoff: date) -> pd.DataFrame:
    """Fetch NSW FuelCheck station-level price history via CKAN (all monthly resources)."""
    print("  [au_nsw_fuelcheck] Fetching NSW FuelCheck price history...")
    print(f"  [au_nsw_fuelcheck] Cutoff: {cutoff}")

    session = get_session()
    try:
        resp = session.get(
            _NSW_FUELCHECK_PACKAGE_URL,
            timeout=30,
            headers=_CKAN_BROWSER_HEADERS,
        )
        resp.raise_for_status()
        payload = resp.json()
    except Exception as e:
        print(f"  [au_nsw_fuelcheck] CKAN package_show error: {e}")
        return pd.DataFrame()

    result = payload.get("result") if isinstance(payload, dict) else None
    resources = result.get("resources", []) if isinstance(result, dict) else []

    # Collect all monthly resources whose reference month is >= cutoff
    eligible: list[tuple[date, dict]] = []
    for r in resources:
        if _resource_format(r) not in {"csv", "xlsx", "xls"}:
            continue
        resource_month = _parse_resource_month(r)
        if resource_month is None:
            continue
        if resource_month < cutoff:
            continue
        eligible.append((resource_month, r))

    if not eligible:
        print("  [au_nsw_fuelcheck] No resources found after cutoff")
        return pd.DataFrame()

    eligible.sort(key=lambda x: x[0])
    print(
        f"  [au_nsw_fuelcheck] {len(eligible)} resources to download (cutoff: {cutoff})"
    )

    all_rows: list[dict] = []

    for resource_month, resource in eligible:
        resource_url = str(resource.get("url") or "").strip()
        resource_format = _resource_format(resource)
        if not resource_url:
            continue

        print(
            f"  [au_nsw_fuelcheck] Downloading {resource_month:%Y-%m}: {resource_url}"
        )
        try:
            res = session.get(
                resource_url,
                timeout=120,
                headers=_CKAN_BROWSER_HEADERS,
            )
            res.raise_for_status()
        except Exception as e:
            print(f"  [au_nsw_fuelcheck] Download error ({resource_month:%Y-%m}): {e}")
            continue

        try:
            if resource_format == "csv":
                raw = pd.read_csv(io.BytesIO(res.content), low_memory=False)
            else:
                raw = _read_fuelcheck_xlsx(res.content)
        except Exception as e:
            print(f"  [au_nsw_fuelcheck] Parse error ({resource_month:%Y-%m}): {e}")
            continue

        raw = pd.DataFrame(raw)
        if raw.empty:
            print(f"  [au_nsw_fuelcheck] {resource_month:%Y-%m}: empty resource")
            continue

        col_lookup = {str(c).replace(" ", "").lower(): c for c in raw.columns}

        def pick_col(*names: str) -> str | None:
            for name in names:
                key = name.replace(" ", "").lower()
                if key in col_lookup:
                    return col_lookup[key]
            return None

        col_address = pick_col("Address")
        col_suburb = pick_col("Suburb")
        col_postcode = pick_col("Postcode")
        col_fuel = pick_col("FuelCode")
        col_updated = pick_col("PriceUpdatedDate")
        col_price = pick_col("Price")

        required = [col_fuel, col_updated, col_price]
        if any(c is None for c in required):
            print(
                f"  [au_nsw_fuelcheck] {resource_month:%Y-%m}: missing required columns"
            )
            continue

        raw["_obs_ts"] = pd.to_datetime(raw[col_updated], errors="coerce", utc=True)
        raw["_obs_date"] = raw["_obs_ts"].dt.date
        raw = raw.loc[raw["_obs_date"].notna()]
        raw = raw.loc[raw["_obs_date"] > cutoff]
        raw = raw.copy()

        if raw.empty:
            print(f"  [au_nsw_fuelcheck] {resource_month:%Y-%m}: no rows after cutoff")
            continue

        rows_this_resource = 0
        for _, row in raw.iterrows():
            obs_date = row.get("_obs_date")
            if obs_date is None or pd.isna(obs_date):
                continue

            try:
                price_val = float(row[col_price])
            except (TypeError, ValueError):
                continue

            if pd.isna(price_val) or price_val <= 0:
                continue

            if price_val >= 10:
                price_val = price_val / 100.0

            price_val = round(price_val, 4)
            if not (0.5 <= price_val <= 4.0):
                continue

            fuel_code = _clean_text(row[col_fuel])
            fuel_code = fuel_code.upper() if fuel_code else None
            mapping = _FUELCHECK_CODE_MAP.get(fuel_code or "", {})

            street = _clean_text(row[col_address]) if col_address else None
            suburb = _clean_text(row[col_suburb]) if col_suburb else None
            postcode = _format_postcode(row[col_postcode]) if col_postcode else None

            # Build a full address string from available parts
            addr_parts = [p for p in [street, suburb, postcode] if p]
            full_address = ", ".join(addr_parts) if addr_parts else None

            record = _TMPL_AU_NSW_FUELCHECK.copy()
            record.update(
                {
                    "fuel_family": mapping.get("fuel_family"),
                    "fuel_product": mapping.get("fuel_product") or fuel_code,
                    "quality_group": mapping.get("quality_group"),
                    "octane_ron": mapping.get("octane_ron"),
                    "ethanol_pct": mapping.get("ethanol_pct"),
                    "city": suburb,
                    "address": full_address,
                    "price_local": price_val,
                    "effective_from": str(obs_date),
                    "effective_to": str(obs_date),
                    "observation_date": str(obs_date),
                }
            )
            record["observation_hash"] = make_hash(record)
            all_rows.append(record)
            rows_this_resource += 1

        print(f"  [au_nsw_fuelcheck] {resource_month:%Y-%m}: {rows_this_resource} rows")
        time.sleep(0.5)

    if not all_rows:
        print("  [au_nsw_fuelcheck] No valid rows extracted")
        return pd.DataFrame()

    print(f"  [au_nsw_fuelcheck] Total: {len(all_rows)} rows fetched")
    return pd.DataFrame(all_rows)


# ── FuelWatch (WA) historic CSV from Azure Blob Storage ──────────────────────

_FUELWATCH_HISTORIC_URL = (
    "https://warsydprdstafuelwatch.blob.core.windows.net"
    "/historical-reports/FuelWatchRetail-03-2026.csv"
)

_FUELWATCH_CSV_PRODUCT_MAP = {
    "ULP": ("Unleaded", "gasoline", "regular", None),
    "Diesel": ("Diesel", "diesel", "regular", None),
}

_FUELWATCH_CSV_REGIONS = {"North of River", "South of River"}


def fetch_au_fuelwatch_historic_csv(cutoff: date) -> pd.DataFrame:
    """Fetch FuelWatch WA historic CSV and aggregate to daily Perth Metro means."""
    print("  [au_fuelwatch_csv] Fetching FuelWatch historic CSV...")
    print(f"  [au_fuelwatch_csv] Cutoff: {cutoff}")

    session = get_session()
    try:
        resp = session.get(_FUELWATCH_HISTORIC_URL, timeout=120)
        resp.raise_for_status()
    except Exception as e:
        print(f"  [au_fuelwatch_csv] Download error: {e}")
        return pd.DataFrame()

    try:
        raw = pd.read_csv(io.BytesIO(resp.content), low_memory=False)
    except Exception as e:
        print(f"  [au_fuelwatch_csv] CSV parse error: {e}")
        return pd.DataFrame()

    if raw.empty:
        print("  [au_fuelwatch_csv] Empty CSV")
        return pd.DataFrame()

    # Parse dates (DD/MM/YYYY format)
    raw["_date"] = pd.to_datetime(
        raw["PUBLISH_DATE"], format="%d/%m/%Y", errors="coerce"
    )
    raw = raw.dropna(subset=["_date"])
    raw["_date_d"] = raw["_date"].dt.date

    # Filter to dates after cutoff
    raw = raw[raw["_date_d"] > cutoff]
    if raw.empty:
        print("  [au_fuelwatch_csv] No rows after cutoff")
        return pd.DataFrame()

    # Filter to Perth Metro regions
    raw = raw[raw["AREA_DESCRIPTION"].isin(_FUELWATCH_CSV_REGIONS)]
    if raw.empty:
        print("  [au_fuelwatch_csv] No Perth Metro rows")
        return pd.DataFrame()

    # Filter to target products
    raw = raw[raw["PRODUCT_DESCRIPTION"].isin(_FUELWATCH_CSV_PRODUCT_MAP)]
    if raw.empty:
        print("  [au_fuelwatch_csv] No ULP/Diesel rows")
        return pd.DataFrame()

    # Parse prices
    raw["_price"] = pd.to_numeric(raw["PRODUCT_PRICE"], errors="coerce")
    raw = raw.dropna(subset=["_price"])
    raw = raw[raw["_price"] > 0]

    # Group by (date, product, area) and compute mean price
    grouped = (
        raw.groupby(["_date_d", "PRODUCT_DESCRIPTION", "AREA_DESCRIPTION"])["_price"]
        .mean()
        .reset_index()
    )

    all_rows: list[dict] = []
    for _, g in grouped.iterrows():
        obs_date = g["_date_d"]
        product = g["PRODUCT_DESCRIPTION"]
        area = g["AREA_DESCRIPTION"]
        mean_cpl = g["_price"]

        prod_name, family, qg, ron = _FUELWATCH_CSV_PRODUCT_MAP[product]

        # Convert cents/L to AUD/L
        price = round(mean_cpl / 100.0, 4)
        if not (0.5 <= price <= 4.0):
            continue

        row = _TMPL_AU_FUELWATCH.copy()
        row.update(
            {
                "fuel_family": family,
                "fuel_product": prod_name,
                "quality_group": qg,
                "octane_ron": ron,
                "subnational_area": area,
                "city": "Perth",
                "price_local": price,
                "effective_from": str(obs_date),
                "effective_to": str(obs_date),
                "observation_date": str(obs_date),
                "source_url": _FUELWATCH_HISTORIC_URL,
            }
        )
        row["observation_hash"] = make_hash(row)
        all_rows.append(row)

    if not all_rows:
        print("  [au_fuelwatch_csv] No valid rows after aggregation")
        return pd.DataFrame()

    print(f"  [au_fuelwatch_csv] {len(all_rows)} rows fetched")
    return pd.DataFrame(all_rows)
