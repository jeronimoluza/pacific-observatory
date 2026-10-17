"""Thailand EPPO fetchers: P04 monthly retail table and the daily retail feed.

Ported unchanged from legacy pacific-observatory
``src/cpi/fuel_prices/fetchers/thailand.py`` (dev 2d60a353); the legacy module is
split across this file, ``thailand_retail.py`` and the NGV wrapper to stay
under 500 lines.
"""

import io
import json
import re
from datetime import date, timedelta

import pandas as pd

from fuel.fetchers._shared.eap.legacy import get_session, make_hash, make_template

# ── EPPO P04 Monthly Retail Petroleum ─────────────────────────────────────────

_TMPL_TH = make_template(
    country="Thailand",
    wb_iso3="THA",
    source_key="th_eppo_p04_monthly",
    source_name="Thailand EPPO Table P04 – Retail Prices of Petroleum Products",
    source_url="https://www.eppo.go.th/data-energy-statistic/energy-statistic/petro-price-energy-stat/%e0%b8%a3%e0%b8%b2%e0%b8%84%e0%b8%b2%e0%b8%9b%e0%b8%b4%e0%b9%82%e0%b8%95%e0%b8%a3%e0%b9%80%e0%b8%a5%e0%b8%b5%e0%b8%a2%e0%b8%a1/",
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

# EPPO's 2026 rebuild moved the P04 spreadsheet out of the old
# /epposite/images/... tree (now 404) into the WordPress uploads folder, where
# the path carries the upload month and so changes on every re-publish.
# Discover it from the petroleum-price statistics page instead of hardcoding.
_P04_PAGE_URL = (
    "https://www.eppo.go.th/data-energy-statistic/energy-statistic/"
    "petro-price-energy-stat/%e0%b8%a3%e0%b8%b2%e0%b8%84%e0%b8%b2"
    "%e0%b8%9b%e0%b8%b4%e0%b9%82%e0%b8%95%e0%b8%a3%e0%b9%80%e0%b8%a5"
    "%e0%b8%b5%e0%b8%a2%e0%b8%a1/"
)
_P04_HREF_RE = re.compile(
    r'href="(https://www\.eppo\.go\.th/wp-content/uploads/'
    r'\d{4}/\d{2}/P04[^"]*\.xls)"',
    re.IGNORECASE,
)
# Last known-good direct link, used only if the listing page is unreachable.
_P04_URL = "https://www.eppo.go.th/wp-content/uploads/2026/04/P04-1.xls"


def _discover_p04_url(session) -> str:
    """Return the current P04 spreadsheet URL, else the last known-good one."""
    try:
        resp = session.get(_P04_PAGE_URL, timeout=60)
        resp.raise_for_status()
    except Exception as e:
        print(f"  [th_eppo] Could not read P04 listing ({e}); using {_P04_URL}")
        return _P04_URL

    matches = _P04_HREF_RE.findall(resp.text)
    if not matches:
        print(f"  [th_eppo] No P04 link on listing page; using {_P04_URL}")
        return _P04_URL

    # Upload paths sort chronologically (.../YYYY/MM/...), so the last is newest.
    return sorted(matches)[-1]

# ── EPPO Retail Fuel Prices (Daily) ───────────────────────────────────────────

# EPPO's 2026 site rebuild retired the scraped price board at
# /petro/price/index.html (now 404) and publishes the same numbers as JSON.
# Human-readable equivalent: eppo.go.th -> data & statistics -> retail oil prices.
_TH_RETAIL_URL = "https://www.eppo.go.th/wp-json/oil-api/v1/oil-prices"

# Feed keys are "oil_<brand>_<suffix>"; the suffix identifies the grade.
# Suffixes gs95p/gs99p/gl95p are brand-specific premium gasohols with no
# entry in _TH_RETAIL_PRODUCTS, so they are deliberately not mapped.
_TH_API_PRODUCT_LABELS = {
    "gl95": "Benzine 95",
    "gh95": "Gasohol 95",
    "gh91": "Gasohol 91",
    "e20": "Gasohol E20",
    "e85": "Gasohol E85",
    "ds": "Diesel B7",
    "dsb10": "Diesel B10",
    "dsb20": "Diesel B20",
    "pds": "Premium Diesel",
}

# PTT is Thailand's reference retailer, so it is preferred; the remaining
# brands are consulted only when PTT does not quote a grade (the feed writes
# "-" for grades a brand does not sell). One row per product, as before.
_TH_API_BRAND_ORDER = (
    "ptt",
    "bcp",
    "shell",
    "esso",
    "caltex",
    "irpc",
    "pt",
    "susco1",
    "pure",
    "susco2",
)

_TMPL_TH_DAILY = make_template(
    country="Thailand",
    wb_iso3="THA",
    source_key="th_eppo_retail_daily",
    source_name="Thailand EPPO Retail Fuel Prices (Daily)",
    source_url=_TH_RETAIL_URL,
    currency="THB",
    unit="L",
    subnational_area="National",
    publication_frequency="daily",
    observation_method="reported",
    tax_status="tax_inclusive",
)

_TH_RETAIL_PRODUCTS = [
    {
        "patterns": [r"benzine\s*95", r"เบนซิน\s*95"],
        "fuel_product": "Benzine 95",
        "fuel_family": "gasoline",
        "quality_group": "premium",
        "octane_ron": 95,
        "ethanol_pct": 0,
    },
    {
        "patterns": [r"gasohol\s*95", r"แก๊สโซฮอล์\s*95"],
        "fuel_product": "Gasohol 95",
        "fuel_family": "gasoline",
        "quality_group": "regular",
        "octane_ron": 95,
        "ethanol_pct": 10,
    },
    {
        "patterns": [r"gasohol\s*91", r"แก๊สโซฮอล์\s*91"],
        "fuel_product": "Gasohol 91",
        "fuel_family": "gasoline",
        "quality_group": "regular",
        "octane_ron": 91,
        "ethanol_pct": 10,
    },
    {
        "patterns": [r"gasohol\s*e20", r"แก๊สโซฮอล์\s*e20"],
        "fuel_product": "Gasohol E20",
        "fuel_family": "gasoline",
        "quality_group": "regular",
        "octane_ron": 95,
        "ethanol_pct": 20,
    },
    {
        "patterns": [r"gasohol\s*e85", r"แก๊สโซฮอล์\s*e85"],
        "fuel_product": "Gasohol E85",
        "fuel_family": "gasoline",
        "quality_group": "biofuel",
        "octane_ron": None,
        "ethanol_pct": 85,
    },
    {
        "patterns": [r"diesel\s*b7", r"ดีเซล\s*b7"],
        "fuel_product": "Diesel B7",
        "fuel_family": "diesel",
        "quality_group": "regular",
    },
    {
        "patterns": [r"diesel\s*b10", r"ดีเซล\s*b10"],
        "fuel_product": "Diesel B10",
        "fuel_family": "diesel",
        "quality_group": "regular",
    },
    {
        "patterns": [r"diesel\s*b20", r"ดีเซล\s*b20"],
        "fuel_product": "Diesel B20",
        "fuel_family": "diesel",
        "quality_group": "regular",
    },
    {
        "patterns": [r"premium\s*diesel", r"ดีเซล\s*พรีเมียม", r"ดีเซลพรีเมียม"],
        "fuel_product": "Premium Diesel",
        "fuel_family": "diesel",
        "quality_group": "premium",
    },
]

def _match_th_retail_product(text: str) -> dict | None:
    key = (text or "").lower()
    for spec in _TH_RETAIL_PRODUCTS:
        for pattern in spec["patterns"]:
            if re.search(pattern, key, re.IGNORECASE):
                return spec
    return None


def _parse_iso_date(value) -> date | None:
    """Parse the feed's ISO "YYYY-MM-DD" date field, tolerating junk."""
    try:
        return date.fromisoformat(str(value).strip())
    except (TypeError, ValueError):
        return None


def _parse_price_value(text: str) -> float | None:
    if not text:
        return None
    candidates = re.findall(r"\d+[\d,]*(?:\.\d+)?", text)
    if not candidates:
        return None
    raw = candidates[-1].replace(",", "")
    try:
        return float(raw)
    except ValueError:
        return None

def fetch_th_eppo_retail_daily(cutoff: date) -> pd.DataFrame:
    """Fetch Thailand EPPO current retail fuel prices from the oil-price feed."""
    print("  [th_eppo_daily] Fetching Thailand EPPO retail daily prices...")
    print(f"  [th_eppo_daily] Cutoff: {cutoff}")

    session = get_session()
    try:
        resp = session.get(_TH_RETAIL_URL, timeout=45)
        resp.raise_for_status()
        # The feed is served with a UTF-8 BOM, which resp.json() rejects.
        payload = json.loads(resp.content.decode("utf-8-sig"))
    except Exception as e:
        print(f"  [th_eppo_daily] Could not fetch price feed: {e}")
        return pd.DataFrame()

    brands = payload.get("data") or {}
    if not brands:
        print("  [th_eppo_daily] Feed carried no data block")
        return pd.DataFrame()

    # Every brand stamps its own effective date and they move together, so the
    # first one present is the snapshot date for the whole feed.
    obs_date = None
    for brand in _TH_API_BRAND_ORDER:
        raw_date = (brands.get(brand) or {}).get(f"oil_{brand}_date")
        obs_date = _parse_iso_date(raw_date)
        if obs_date:
            break
    if obs_date is None:
        print("  [th_eppo_daily] Feed carried no parseable date")
        return pd.DataFrame()

    if obs_date <= cutoff:
        print(f"  [th_eppo_daily] Date {obs_date} not newer than cutoff {cutoff}")
        return pd.DataFrame()

    rows = []
    for suffix, label in _TH_API_PRODUCT_LABELS.items():
        spec = _match_th_retail_product(label)
        if not spec:
            continue
        for brand in _TH_API_BRAND_ORDER:
            block = brands.get(brand)
            if not block:
                continue
            price = _parse_price_value(block.get(f"oil_{brand}_{suffix}"))
            if price is None or not (5 <= price <= 120):
                continue

            row = _TMPL_TH_DAILY.copy()
            row.update(
                {
                    "fuel_family": spec.get("fuel_family"),
                    "fuel_product": spec.get("fuel_product"),
                    "quality_group": spec.get("quality_group"),
                    "octane_ron": spec.get("octane_ron"),
                    "ethanol_pct": spec.get("ethanol_pct"),
                    "price_local": round(price, 4),
                    "effective_from": str(obs_date),
                    "effective_to": str(obs_date),
                    "observation_date": str(obs_date),
                    "source_url": _TH_RETAIL_URL,
                    "notes": f"{label} ({brand.upper()})",
                }
            )
            row["observation_hash"] = make_hash(row)
            rows.append(row)
            break

    if not rows:
        print("  [th_eppo_daily] No rows parsed from feed")
        return pd.DataFrame()

    print(f"  [th_eppo_daily] {len(rows)} rows fetched for {obs_date}")
    return pd.DataFrame(rows)

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
    p04_url = _discover_p04_url(session)
    try:
        resp = session.get(p04_url, timeout=60)
        resp.raise_for_status()
    except Exception as e:
        print(f"  [th_eppo] Download error for {p04_url}: {e}")
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
