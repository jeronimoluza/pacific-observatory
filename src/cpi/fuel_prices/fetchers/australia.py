"""Australia fuel price fetchers: AIP Terminal Gate Prices + ACCC quarterly retail."""

import io
import re
import time
from datetime import date, timedelta

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
                href = a["href"]
                if "AIP_TGP_Data_" in href and href.lower().endswith(".xlsx"):
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
