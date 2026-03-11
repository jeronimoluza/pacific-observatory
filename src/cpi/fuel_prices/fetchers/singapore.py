"""Singapore Department of Statistics (SingStat) TableBuilder fuel prices.

This uses SingStat's TableBuilder JSON endpoints to pull monthly average retail prices
for petrol (98/95/92 RON), diesel, and LPG.
"""

from __future__ import annotations

# ruff: noqa: E402
SOURCE_META = [
    {
        "fetcher_fn": "fetch_sg_singstat_avg_retail_prices",
        "country": "Singapore",
        "source_name": "Singapore Department of Statistics (SingStat) TableBuilder",
        "url": "https://tablebuilder.singstat.gov.sg/table/TS/M213761",
        "description": "Monthly average retail prices (Singapore) for petrol (98/95/92), diesel, and LPG from SingStat TableBuilder.",
        "extraction_method": ["REST API"],
        "products": [
            "Petrol, 98 Octane (Per Litre)",
            "Petrol, 95 Octane (Per Litre)",
            "Petrol, 92 Octane (Per Litre)",
            "Diesel (Per Litre)",
            "Liquefied Petroleum Gas (LPG) (Per Kilogram)",
        ],
        "source_keys": ["sg_singstat_avg_retail_prices_monthly"],
        "publishes_on": "Monthly",
        "notes": "Uses /api/doswebcontent/1/StatisticTableFileUpload/StatisticTable/<matrixNumber> to get the table UUID, then /Row/<uuid> to discover per-series rowdata JSON paths under /rowdata/*.json.",
    },
    {
        "fetcher_fn": "fetch_sg_spc_latest_pump_prices",
        "country": "Singapore",
        "source_name": "SPC Latest Pump Prices",
        "url": "https://www.spc.com.sg/our-business/spc-service-station/latest-pump-price/",
        "description": "Daily pump prices for SPC service stations (Levo 98/95/92 and diesel) from SPC's official website.",
        "extraction_method": ["Web scraping"],
        "products": [
            "Petrol 98 RON",
            "Petrol 95 RON",
            "Petrol 92 RON",
            "Diesel",
        ],
        "source_keys": ["sg_spc_pump_prices_daily"],
        "publishes_on": "Daily or irregular",
        "notes": "Page reports latest pump prices before discounts; scraper reads data-price attributes and last updated timestamp.",
    },
    {
        "fetcher_fn": "fetch_sg_caltex_pump_prices",
        "country": "Singapore",
        "source_name": "Caltex Singapore Fuel Prices",
        "url": "https://www.caltex.com/sg/motorists/fuel-prices.html",
        "description": "Pump prices published on Caltex Singapore official site (Regular 92, Premium 95, Platinum 98, Diesel). Uses the 'before site discount' table values.",
        "extraction_method": ["Web scraping"],
        "products": [
            "Regular 92 with Techron (Per Litre)",
            "Premium 95 with Techron (Per Litre)",
            "Platinum 98 with Techron (Per Litre)",
            "Diesel with Techron D (Per Litre)",
        ],
        "source_keys": ["sg_caltex_pump_prices_daily"],
        "publishes_on": "Daily or irregular",
        "notes": "Reads Caltex fuel prices table and parses the Last Updated timestamp. Uses before-site-discount prices (pump board, pre-discount).",
    },
]

import re
from datetime import date, datetime, timedelta
from urllib.parse import urlparse

import pandas as pd
from bs4 import BeautifulSoup

from ..utils import MONTH_MAP_EN, get_session, make_hash, make_template


_TABLE_URL = "https://tablebuilder.singstat.gov.sg/table/TS/M213761"
_API_META = (
    "https://tablebuilder.singstat.gov.sg"
    "/api/doswebcontent/1/StatisticTableFileUpload/StatisticTable/M213761"
)
_SPC_URL = "https://www.spc.com.sg/our-business/spc-service-station/latest-pump-price/"
_CALTEX_URL = "https://www.caltex.com/sg/motorists/fuel-prices.html"


_TMPL_SG = make_template(
    country="Singapore",
    wb_iso3="SGP",
    source_key="sg_singstat_avg_retail_prices_monthly",
    source_name="Singapore Department of Statistics (SingStat) TableBuilder",
    source_url=_TABLE_URL,
    source_type="official",
    currency="SGD",
    subnational_area="National",
    publication_frequency="monthly",
    observation_method="reported",
)

_TMPL_SG_SPC = make_template(
    country="Singapore",
    wb_iso3="SGP",
    source_key="sg_spc_pump_prices_daily",
    source_name="SPC Latest Pump Prices",
    source_url=_SPC_URL,
    source_type="compiled_web",
    currency="SGD",
    unit="L",
    subnational_area="National",
    publication_frequency="daily",
    observation_method="reported",
    tax_status="tax_inclusive",
)

_TMPL_SG_CALTEX = make_template(
    country="Singapore",
    wb_iso3="SGP",
    source_key="sg_caltex_pump_prices_daily",
    source_name="Caltex Singapore Fuel Prices",
    source_url=_CALTEX_URL,
    source_type="official",
    currency="SGD",
    unit="L",
    subnational_area="National",
    publication_frequency="daily",
    observation_method="reported",
    tax_status="tax_inclusive",
)


_PRODUCTS = {
    "petrol, 98 octane (per litre)": {
        "fuel_family": "gasoline",
        "fuel_product": "Petrol 98 RON",
        "quality_group": "premium",
        "octane_ron": 98,
        "unit": "L",
    },
    "petrol, 95 octane (per litre)": {
        "fuel_family": "gasoline",
        "fuel_product": "Petrol 95 RON",
        "quality_group": "regular",
        "octane_ron": 95,
        "unit": "L",
    },
    "petrol, 92 octane (per litre)": {
        "fuel_family": "gasoline",
        "fuel_product": "Petrol 92 RON",
        "quality_group": "regular",
        "octane_ron": 92,
        "unit": "L",
    },
    "diesel (per litre)": {
        "fuel_family": "diesel",
        "fuel_product": "Diesel",
        "quality_group": "standard",
        "octane_ron": None,
        "unit": "L",
    },
    "liquefied petroleum gas (lpg) (per kilogram)": {
        "fuel_family": "lpg",
        "fuel_product": "LPG",
        "quality_group": "standard",
        "octane_ron": None,
        "unit": "kg",
    },
}

_SPC_PRODUCTS = [
    ("Petrol 98 RON", "gasoline", "premium", 98),
    ("Petrol 95 RON", "gasoline", "regular", 95),
    ("Petrol 92 RON", "gasoline", "regular", 92),
    ("Diesel", "diesel", "standard", None),
]

_CALTEX_PRODUCTS = {
    "Regular 92 with Techron": ("Petrol 92 RON", "gasoline", "regular", 92),
    "Premium 95 with Techron": ("Petrol 95 RON", "gasoline", "regular", 95),
    "Platinum 98 with Techron": ("Petrol 98 RON", "gasoline", "premium", 98),
    "Caltex Diesel with Techron": ("Diesel", "diesel", "standard", None),
}


def _month_end(d: date) -> date:
    next_m = d.replace(day=28) + timedelta(days=4)
    return next_m - timedelta(days=next_m.day)


def _parse_period_key(key: str) -> date | None:
    # Expected: "2015 Jan"
    parts = (key or "").strip().split()
    if len(parts) < 2:
        return None
    try:
        year = int(parts[0])
    except ValueError:
        return None
    mon = parts[1].strip().lower()[:3]
    if mon not in MONTH_MAP_EN:
        return None
    try:
        return date(year, MONTH_MAP_EN[mon], 1)
    except ValueError:
        return None


def _parse_spc_update_date(text: str) -> date | None:
    match = re.search(r"Last updated on\s+(\d{1,2})\s+([A-Za-z]{3})\s+(\d{4})", text)
    if not match:
        return None
    day = int(match.group(1))
    mon = match.group(2).strip().lower()
    year = int(match.group(3))
    if mon not in MONTH_MAP_EN:
        return None
    try:
        return date(year, MONTH_MAP_EN[mon], day)
    except ValueError:
        return None


def fetch_sg_singstat_avg_retail_prices(cutoff: date) -> pd.DataFrame:
    """Fetch Singapore monthly average retail fuel prices from SingStat TableBuilder."""
    print("  [sg_singstat] Fetching Singapore SingStat TableBuilder (monthly)...")
    print(f"  [sg_singstat] Cutoff: {cutoff}")

    session = get_session()

    # 1) Resolve table UUID from matrixNumber
    try:
        meta = session.get(_API_META, timeout=30).json().get("Data", {})
    except Exception as e:
        print(f"  [sg_singstat] Failed to fetch metadata: {e}")
        return pd.DataFrame()

    table_id = meta.get("id")
    if not table_id:
        print("  [sg_singstat] Missing table UUID in metadata")
        return pd.DataFrame()

    # 2) Get row descriptors (includes per-row jsonChunk URL)
    row_url = (
        "https://tablebuilder.singstat.gov.sg"
        f"/api/doswebcontent/1/StatisticTableFileUpload/StatisticTable/Row/{table_id}"
    )
    try:
        rows = session.get(row_url, timeout=45).json().get("Data", [])
    except Exception as e:
        print(f"  [sg_singstat] Failed to fetch rows: {e}")
        return pd.DataFrame()

    # 3) Identify the fuel rows and fetch their rowdata JSON
    all_rows: list[dict] = []

    for r in rows:
        row_text = str(r.get("rowText") or "").strip()
        key = row_text.lower()
        if key not in _PRODUCTS:
            continue

        json_chunk = str(r.get("jsonChunk") or "").strip()
        if not json_chunk:
            continue

        # The app fetches the rowdata via same-origin proxy: strip blob hostname.
        path = urlparse(json_chunk).path
        if not path.startswith("/"):
            path = "/" + path
        data_url = "https://tablebuilder.singstat.gov.sg" + path

        try:
            items = session.get(data_url, timeout=45).json()
        except Exception as e:
            print(f"  [sg_singstat] Rowdata fetch failed for '{row_text}': {e}")
            continue

        spec = _PRODUCTS[key]
        for item in items or []:
            obs_date = _parse_period_key(str(item.get("Key", "")))
            if obs_date is None or obs_date <= cutoff:
                continue
            raw_val = item.get("Value")
            try:
                price = float(raw_val)
            except (TypeError, ValueError):
                continue
            if not (0.2 <= price <= 10.0):
                continue

            eff_to = _month_end(obs_date)
            row_out = _TMPL_SG.copy()
            row_out.update(
                {
                    "fuel_family": spec["fuel_family"],
                    "fuel_product": spec["fuel_product"],
                    "quality_group": spec["quality_group"],
                    "octane_ron": spec["octane_ron"],
                    "unit": spec["unit"],
                    "price_local": price,
                    "effective_from": str(obs_date),
                    "effective_to": str(eff_to),
                    "observation_date": str(obs_date),
                    "source_url": _TABLE_URL,
                    "notes": row_text,
                }
            )
            row_out["observation_hash"] = make_hash(row_out)
            all_rows.append(row_out)

    print(f"  [sg_singstat] {len(all_rows)} rows fetched (cutoff {cutoff})")
    return pd.DataFrame(all_rows) if all_rows else pd.DataFrame()


def fetch_sg_spc_latest_pump_prices(cutoff: date) -> pd.DataFrame:
    """Fetch SPC latest pump prices (Levo 98/95/92 + diesel)."""
    print("  [sg_spc] Fetching SPC latest pump prices...")
    print(f"  [sg_spc] Cutoff: {cutoff}")

    session = get_session()

    try:
        resp = session.get(_SPC_URL, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        print(f"  [sg_spc] Could not fetch page: {e}")
        return pd.DataFrame()

    soup = BeautifulSoup(resp.content, "lxml")
    update_text = ""
    update_el = soup.find("div", class_=re.compile(r"latest-update-pump-price", re.I))
    if update_el:
        update_text = update_el.get_text(" ", strip=True)

    obs_date = _parse_spc_update_date(update_text) or date.today()
    if obs_date <= cutoff:
        print(f"  [sg_spc] Date {obs_date} not newer than cutoff {cutoff}, skipping")
        return pd.DataFrame()

    price_nodes = soup.select("span.pump-price[data-price]")
    prices = []
    for node in price_nodes:
        raw = node.get("data-price", "")
        try:
            val = float(str(raw).strip())
        except (TypeError, ValueError):
            continue
        if 0.5 <= val <= 10.0:
            prices.append(val)

    if len(prices) < len(_SPC_PRODUCTS):
        print("  [sg_spc] Missing pump price values on page")
        return pd.DataFrame()

    all_rows = []
    note = update_text or f"Fetched {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"
    for idx, (prod_name, family, qg, ron) in enumerate(_SPC_PRODUCTS):
        price = prices[idx]
        row = _TMPL_SG_SPC.copy()
        row.update(
            {
                "fuel_family": family,
                "fuel_product": prod_name,
                "quality_group": qg,
                "octane_ron": ron,
                "price_local": price,
                "effective_from": str(obs_date),
                "effective_to": str(obs_date),
                "observation_date": str(obs_date),
                "source_url": _SPC_URL,
                "notes": note,
            }
        )
        row["observation_hash"] = make_hash(row)
        all_rows.append(row)

    print(f"  [sg_spc] {len(all_rows)} rows fetched for {obs_date}")
    return pd.DataFrame(all_rows) if all_rows else pd.DataFrame()


def _parse_caltex_last_updated(text: str) -> date | None:
    # Example: "Last Updated 10 Mar 2026, 12:30 PM"
    match = re.search(
        r"Last Updated\s+(\d{1,2})\s+([A-Za-z]{3})\s+(\d{4})",
        text or "",
        re.IGNORECASE,
    )
    if not match:
        return None
    day = int(match.group(1))
    mon = match.group(2).strip().lower()
    year = int(match.group(3))
    if mon not in MONTH_MAP_EN:
        return None
    try:
        return date(year, MONTH_MAP_EN[mon], day)
    except ValueError:
        return None


def fetch_sg_caltex_pump_prices(cutoff: date) -> pd.DataFrame:
    """Fetch Caltex Singapore pump prices from the official fuel-prices page."""
    print("  [sg_caltex] Fetching Caltex Singapore fuel prices...")
    print(f"  [sg_caltex] Cutoff: {cutoff}")

    session = get_session()
    try:
        resp = session.get(_CALTEX_URL, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        print(f"  [sg_caltex] Could not fetch page: {e}")
        return pd.DataFrame()

    soup = BeautifulSoup(resp.content, "lxml")
    table = soup.find("table")
    if table is None:
        print("  [sg_caltex] Missing fuel prices table")
        return pd.DataFrame()

    cells = [
        " ".join(c.get_text(" ", strip=True).split())
        for c in table.find_all(["th", "td"])
    ]
    if len(cells) < 7:
        print("  [sg_caltex] Unexpected table structure")
        return pd.DataFrame()

    # Expect: headers + (product, before, after)*N + last_updated
    last_updated_text = next(
        (c for c in cells if c.lower().startswith("last updated")), ""
    )
    obs_date = _parse_caltex_last_updated(last_updated_text) or date.today()
    if obs_date <= cutoff:
        print(f"  [sg_caltex] Date {obs_date} not newer than cutoff {cutoff}, skipping")
        return pd.DataFrame()

    # Find first occurrence of the product list after the 3 headers.
    # Empirically the table is: [FUEL PRODUCTS, BEFORE..., AFTER..., product, before, after, ..., Last Updated ...]
    # Parse triples until we reach Last Updated.
    parsed = []
    i = 3
    while i + 2 < len(cells):
        if cells[i].lower().startswith("last updated"):
            break
        name = cells[i]
        before = cells[i + 1]
        after = cells[i + 2]
        parsed.append((name, before, after))
        i += 3

    if not parsed:
        print("  [sg_caltex] No product rows parsed")
        return pd.DataFrame()

    all_rows = []
    note = f"{last_updated_text}; prices are before site discount"
    for name, before, _after in parsed:
        key = re.sub(r"\s*\u00ae\s*", " ", name).strip()
        key = key.replace("\u00ae", "")
        # Normalize to mapping key prefix
        match_key = None
        for k in _CALTEX_PRODUCTS:
            if key.startswith(k):
                match_key = k
                break
        if not match_key:
            continue

        m = re.search(r"SGD\s+(\d+\.\d{3})", before)
        if not m:
            continue
        price = float(m.group(1))
        if not (0.5 <= price <= 10.0):
            continue

        prod_name, family, qg, ron = _CALTEX_PRODUCTS[match_key]
        row = _TMPL_SG_CALTEX.copy()
        row.update(
            {
                "fuel_family": family,
                "fuel_product": prod_name,
                "quality_group": qg,
                "octane_ron": ron,
                "price_local": price,
                "effective_from": str(obs_date),
                "effective_to": str(obs_date),
                "observation_date": str(obs_date),
                "source_url": _CALTEX_URL,
                "notes": note,
            }
        )
        row["observation_hash"] = make_hash(row)
        all_rows.append(row)

    if not all_rows:
        print("  [sg_caltex] No rows extracted")
        return pd.DataFrame()

    print(f"  [sg_caltex] {len(all_rows)} rows fetched for {obs_date}")
    return pd.DataFrame(all_rows)
