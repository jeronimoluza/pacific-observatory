"""Australia fuel price fetchers: AIP Terminal Gate Prices + ACCC quarterly retail."""

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

            note = (
                f"Mean of {len(prices_cpl)} stations; min={min(prices_cpl):.1f}cpl; "
                f"max={max(prices_cpl):.1f}cpl"
            )
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
                    "notes": note,
                }
            )
            row["observation_hash"] = make_hash(row)
            all_rows.append(row)

    if not all_rows:
        print("  [au_fuelwatch] No new rows")
        return pd.DataFrame()

    print(f"  [au_fuelwatch] {len(all_rows)} rows fetched")
    return pd.DataFrame(all_rows)
