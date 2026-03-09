"""Thailand fuel price fetchers — EPPO P04 monthly retail and NGV retail."""

# ruff: noqa: E402
SOURCE_META = [
    {
        "fetcher_fn": "fetch_th_eppo_p04",
        "country": "Thailand",
        "source_name": "EPPO P04 Monthly Retail Petroleum",
        "url": "https://www.eppo.go.th/epposite/images/Energy-Statistics/energyinformation/Energy_Statistics/Petroleum_Prices/P04.xls",
        "description": "Official government source (Energy Policy and Planning Office, Ministry of Energy). Publishes monthly retail petroleum price statistics as a public XLS file (P04 table). Includes biofuel blends.",
        "extraction_method": "Excel download (XLS)",
        "products": [
            "Gasoline 95 (ULG95)",
            "Gasoline 91 (UGR91)",
            "Kerosene",
            "Diesel HSD",
            "Diesel LSD",
            "Gasohol E10",
            "Gasohol E20",
            "Gasohol E85",
        ],
        "frequency": "Monthly",
        "output": "Secondary CSV",
        "notes": "Direct XLS download; uses xlrd engine. Locates header row by scanning for product keywords. Dates encoded as MON-DD with year from preceding year-marker rows. Price range THB 10–200/L.",
    },
    {
        "fetcher_fn": "fetch_th_eppo_p04",
        "country": "Thailand",
        "source_name": "EPPO P04 Monthly Retail Petroleum",
        "url": "https://www.eppo.go.th/epposite/images/Energy-Statistics/energyinformation/Energy_Statistics/Petroleum_Prices/P04.xls",
        "description": "Official government (EPPO/Ministry of Energy). Monthly retail petroleum stats as public XLS (P04 table). Includes biofuel blends.",
        "extraction_method": ["Excel download"],
        "products": [
            "Gasoline 95 (ULG95)",
            "Gasoline 91 (UGR91)",
            "Kerosene",
            "Diesel HSD",
            "Diesel LSD",
            "Gasohol E10",
            "Gasohol E20",
            "Gasohol E85",
        ],
        "source_keys": ["th_eppo_p04_monthly"],
        "publishes_on": "Monthly",
        "notes": "Direct XLS download; xlrd engine. Locates header row by scanning for product keywords. Dates encoded as MON-DD with year from preceding year-marker rows. Price range THB 10–200/L.",
    },
    {
        "fetcher_fn": "fetch_thailand_eppo_ngv",
        "country": "Thailand",
        "source_name": "EPPO NGV Bangkok Retail Prices",
        "url": "https://www.eppo.go.th/images/petroleum/price/retail-priceNGV/NGVPrice.xls",
        "description": "Official government (EPPO/Ministry of Energy). Monthly NGV retail prices in Bangkok as public XLS file.",
        "extraction_method": ["Excel download"],
        "products": ["Natural Gas for Vehicles (NGV)"],
        "source_keys": ["th_eppo_ngv_bangkok_2025"],
        "publishes_on": "Monthly",
        "notes": "Direct XLS download; auto-detects date and price columns. Bangkok only. Unit: kg. Price range THB 5–30/kg.",
    },
]

import io
import re
from datetime import date, timedelta
from io import BytesIO

import pandas as pd

from ..utils import get_session, make_hash, make_template

# ── EPPO P04 Monthly Retail Petroleum ─────────────────────────────────────────

_TMPL_TH = make_template(
    country="Thailand",
    wb_iso3="THA",
    source_key="th_eppo_p04_monthly",
    source_name="Thailand EPPO Table P04 – Retail Prices of Petroleum Products",
    source_url="https://www.eppo.go.th/epposite/images/Energy-Statistics/energyinformation/Energy_Statistics/Petroleum_Prices/P04.xls",
    currency="THB",
    unit="L",
    subnational_area="National",
    publication_frequency="monthly",
    observation_method="reported",
)

_TH_EPPO_PRODUCTS = [
    ("ULG95", "Gasoline 95", "gasoline", "premium", 95),
    ("UGR91", "Gasoline 91", "gasoline", "regular", 91),
    ("KERO", "Kerosene", "kerosene", "regular", None),
    ("HSD", "Diesel (HSD)", "diesel", "regular", None),
    ("LSD", "Diesel (LSD)", "diesel", "premium", None),
    ("E10", "Gasohol E10", "gasoline", "regular", 91),
    ("E20", "Gasohol E20", "gasoline", "regular", 91),
    ("E85", "Gasohol E85", "gasoline", "biofuel", None),
]

_TH_PRICE_MIN, _TH_PRICE_MAX = 10.0, 200.0

_TH_MONTH_ABBR = {
    "JAN": 1,
    "FEB": 2,
    "MAR": 3,
    "APR": 4,
    "MAY": 5,
    "JUN": 6,
    "JUL": 7,
    "AUG": 8,
    "SEP": 9,
    "OCT": 10,
    "NOV": 11,
    "DEC": 12,
}

_P04_URL = "https://www.eppo.go.th/epposite/images/Energy-Statistics/energyinformation/Energy_Statistics/Petroleum_Prices/P04.xls"


def _parse_th_date(cell, current_year: int) -> date | tuple | None:
    """Parse 'MON-DD' or year integer from a P04 Excel cell."""
    s = str(cell).strip().upper()
    if s in ("AVERAGE", "NAN", "DATE", ""):
        return None
    try:
        yr = int(float(s))
        if 1990 <= yr <= 2100:
            return ("year", yr)
    except (ValueError, TypeError):
        pass
    m = re.match(r"([A-Z]{3})-(\d{1,2})$", s)
    if m and m.group(1) in _TH_MONTH_ABBR:
        mo = _TH_MONTH_ABBR[m.group(1)]
        day = int(m.group(2))
        try:
            return date(current_year, mo, day)
        except ValueError:
            return None
    return None


def fetch_th_eppo_p04(cutoff: date) -> pd.DataFrame:
    """Full-refresh fetch of Thailand EPPO P04 monthly retail petroleum prices."""
    print("  [th_eppo] Fetching Thailand EPPO P04 data (full refresh)...")
    print(f"  [th_eppo] Cutoff: {cutoff}")

    session = get_session()
    try:
        resp = session.get(_P04_URL, timeout=60)
        resp.raise_for_status()
    except Exception as e:
        print(f"  [th_eppo] Download error: {e}")
        return pd.DataFrame()

    content = resp.content
    try:
        raw = pd.read_excel(io.BytesIO(content), engine="xlrd", header=None)
    except Exception:
        try:
            raw = pd.read_excel(io.BytesIO(content), header=None)
        except Exception as e:
            print(f"  [th_eppo] Excel parse error: {e}")
            return pd.DataFrame()

    header_row_idx = None
    col_map: dict[int, tuple] = {}
    for row_idx in range(min(20, len(raw))):
        row_vals = [str(v).upper() for v in raw.iloc[row_idx]]
        matches: dict[int, tuple] = {}
        for col_idx, cell in enumerate(row_vals):
            for kw, prod_name, family, qg, ron in _TH_EPPO_PRODUCTS:
                if kw in cell:
                    matches[col_idx] = (prod_name, family, qg, ron)
                    break
        if len(matches) >= 2:
            header_row_idx = row_idx
            col_map = matches
            break

    if header_row_idx is None:
        print("  [th_eppo] Could not locate header row with product keywords")
        return pd.DataFrame()

    date_col = 1
    all_rows = []
    current_year = None

    for row_idx in range(header_row_idx + 1, len(raw)):
        row = raw.iloc[row_idx]
        cell = row.iloc[date_col]
        parsed = _parse_th_date(cell, current_year or 2000)
        if parsed is None:
            continue
        if isinstance(parsed, tuple) and parsed[0] == "year":
            current_year = parsed[1]
            continue
        if current_year is None:
            continue
        obs_date = parsed
        if obs_date <= cutoff:
            continue

        if obs_date.month == 12:
            eff_to = date(obs_date.year, 12, 31)
        else:
            eff_to = date(obs_date.year, obs_date.month + 1, 1) - timedelta(days=1)

        for col_idx, (prod_name, family, qg, ron) in col_map.items():
            if col_idx >= len(row):
                continue
            try:
                price = float(row.iloc[col_idx])
            except (ValueError, TypeError):
                continue
            if not (_TH_PRICE_MIN <= price <= _TH_PRICE_MAX):
                continue

            r = _TMPL_TH.copy()
            r.update(
                {
                    "fuel_family": family,
                    "fuel_product": prod_name,
                    "quality_group": qg,
                    "octane_ron": ron,
                    "price_local": price,
                    "effective_from": str(obs_date),
                    "effective_to": str(eff_to),
                    "observation_date": str(obs_date),
                    "source_url": _P04_URL,
                }
            )
            r["observation_hash"] = make_hash(r)
            all_rows.append(r)

    if all_rows:
        print(f"  [th_eppo] {len(all_rows)} new rows")
    else:
        print("  [th_eppo] No new rows")
    return pd.DataFrame(all_rows) if all_rows else pd.DataFrame()


# ── EPPO NGV Bangkok ──────────────────────────────────────────────────────────

_TMPL_TH_NGV = make_template(
    country="Thailand",
    wb_iso3="THA",
    source_key="th_eppo_ngv_bangkok_2025",
    source_name="Thailand EPPO NGV Retail Prices — Bangkok",
    source_url="https://www.eppo.go.th/images/petroleum/price/retail-priceNGV/NGVPrice.xls",
    currency="THB",
    unit="kg",
    subnational_area="Bangkok",
    publication_frequency="monthly",
    observation_method="reported",
    fuel_product="NGV retail price",
    fuel_family="natural_gas",
    quality_group="regular",
)

_NGV_URL = "https://www.eppo.go.th/images/petroleum/price/retail-priceNGV/NGVPrice.xls"


def fetch_thailand_eppo_ngv(cutoff: date) -> pd.DataFrame:
    """Fetch Thailand EPPO NGV retail prices from Bangkok (monthly XLS)."""
    print("  [th_eppo_ngv] Fetching Thailand EPPO NGV data...")
    print(f"  [th_eppo_ngv] Cutoff: {cutoff}")

    session = get_session()
    try:
        resp = session.get(_NGV_URL, timeout=60)
        resp.raise_for_status()
    except Exception as e:
        print(f"  [th_eppo_ngv] Could not download XLS: {e}")
        return pd.DataFrame()

    try:
        import xlrd  # noqa: F401

        engine = "xlrd"
    except ImportError:
        engine = "openpyxl"

    all_rows = []
    try:
        xf = pd.ExcelFile(BytesIO(resp.content), engine=engine)
        for sheet in xf.sheet_names:
            try:
                raw = pd.read_excel(
                    BytesIO(resp.content), sheet_name=sheet, header=None, engine=engine
                )
            except Exception:
                continue

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

                r = _TMPL_TH_NGV.copy()
                r.update(
                    {
                        "price_local": round(price, 4),
                        "effective_from": str(obs_date),
                        "effective_to": str(obs_date),
                        "observation_date": str(obs_date),
                        "source_url": _NGV_URL,
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
        print("  [th_eppo_ngv] No new rows")
    return pd.DataFrame(all_rows) if all_rows else pd.DataFrame()
