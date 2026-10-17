"""Australia: NSW FuelCheck price history (Data.NSW CKAN).

Ported unchanged from legacy pacific-observatory
``src/cpi/fuel_prices/fetchers/australia.py`` (dev 2d60a353); split across
three modules only to stay under the 500-line cap, imports adjusted.
"""

import io
import re
import time
from datetime import date

import pandas as pd

from fuel.fetchers._shared.eap.legacy import get_session, make_hash, make_template


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
