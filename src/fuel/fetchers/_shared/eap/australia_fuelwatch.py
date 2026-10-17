"""Australia: FuelWatch WA (Perth) daily RSS + historic monthly CSV.

Ported unchanged from legacy pacific-observatory
``src/cpi/fuel_prices/fetchers/australia.py`` (dev 2d60a353); split across
three modules only to stay under the 500-line cap, imports adjusted.
"""

import io
from datetime import date
from xml.etree import ElementTree as ET

import pandas as pd

from fuel.fetchers._shared.eap.legacy import get_session, make_hash, make_template




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
