"""Taiwan fuel price fetchers.

Two sources:
  1. MOEA Energy Administration — monthly nationwide average (POST API).
  2. CPC Corp Taiwan — historical retail prices (JS variable in HTML page).
"""

from __future__ import annotations

# ruff: noqa: E402
SOURCE_META = [
    {
        "fetcher_fn": "fetch_tw_moea_nationwide_avg",
        "country": "Taiwan",
        "source_name": "Taiwan MOEA Energy Administration — Nationwide Average",
        "url": "https://www2.moeaea.gov.tw/oil111/EN/NationwideAvg",
        "description": (
            "Monthly nationwide average retail fuel prices from Taiwan's "
            "Ministry of Economic Affairs Energy Administration. "
            "Uses a POST API to retrieve monthly data."
        ),
        "extraction_method": ["REST API"],
        "products": [
            "Unleaded 92",
            "Unleaded 95",
            "Unleaded 98",
            "Super Diesel",
        ],
        "source_keys": ["tw_moea_nationwide_avg_monthly"],
        "publishes_on": "Monthly",
        "notes": (
            "POST to /GetRangeNationwideAvg with unit=month, start/end as YYYY/MM. "
            "Response JSON shape confirmed at runtime via _find_data_rows(). "
            "Price range: 15–60 TWD/L."
        ),
    },
    {
        "fetcher_fn": "fetch_tw_cpc_history_prices",
        "country": "Taiwan",
        "source_name": "CPC Corp Taiwan — Historical Retail Prices",
        "url": "https://www.cpc.com.tw/en/HistoryPrice.aspx?n=3058",
        "description": (
            "Historical pump prices from CPC Corp Taiwan (state-owned). "
            "Extracts the pieSeries JS variable from the page HTML. "
            "Typically covers recent years with ~7 data points."
        ),
        "extraction_method": ["Web scraping"],
        "products": [
            "Unleaded 92",
            "Unleaded 95",
            "Unleaded 98",
            "Super Diesel",
        ],
        "source_keys": ["tw_cpc_history_prices"],
        "publishes_on": "Irregular",
        "notes": (
            "Regex parses var pieSeries = [...]; from inline JS. "
            "full_refresh=True because the page only shows ~7 recent entries. "
            "Price range: 15–60 TWD/L."
        ),
    },
]

import calendar
import json
import re
from datetime import date, datetime

import pandas as pd

from ..utils import get_session, make_hash, make_template

_MOEA_POST_URL = "https://www2.moeaea.gov.tw/oil111/EN/GetRangeNationwideAvg"
_MOEA_GET_URL = "https://www2.moeaea.gov.tw/oil111/EN/NationwideAvg"
_CPC_URL = "https://www.cpc.com.tw/en/HistoryPrice.aspx?n=3058"

_TMPL_MOEA = make_template(
    country="Taiwan",
    wb_iso3="TWN",
    source_key="tw_moea_nationwide_avg_monthly",
    source_name="Taiwan MOEA Energy Administration — Nationwide Average",
    source_url=_MOEA_GET_URL,
    source_type="official",
    currency="TWD",
    unit="L",
    subnational_area="National",
    publication_frequency="monthly",
    observation_method="reported",
    tax_status="tax_inclusive",
)

_TMPL_CPC = make_template(
    country="Taiwan",
    wb_iso3="TWN",
    source_key="tw_cpc_history_prices",
    source_name="CPC Corp Taiwan — Historical Retail Prices",
    source_url=_CPC_URL,
    source_type="official",
    currency="TWD",
    unit="L",
    subnational_area="National",
    publication_frequency="irregular",
    observation_method="reported",
    tax_status="tax_inclusive",
)

# Maps MOEA API column name → (fuel_product, fuel_family, quality_group, octane_ron)
# Actual keys confirmed from API: Oil92, Oil95, Oil98, Oilchai (diesel).
# Plan-spec names kept as fallbacks in case the EN endpoint uses different keys.
_MOEA_PRODUCTS: dict[str, tuple[str, str, str, int | None]] = {
    "Oil92": ("Unleaded 92", "gasoline", "regular", 92),
    "Oil95": ("Unleaded 95", "gasoline", "premium", 95),
    "Oil98": ("Unleaded 98", "gasoline", "super_premium", 98),
    "Oilchai": ("Super Diesel", "diesel", "regular", None),
    # Fallback English-style keys in case the EN endpoint differs
    "Unleaded-92": ("Unleaded 92", "gasoline", "regular", 92),
    "Unleaded-95": ("Unleaded 95", "gasoline", "premium", 95),
    "Unleaded-98": ("Unleaded 98", "gasoline", "super_premium", 98),
    "Super Diesel": ("Super Diesel", "diesel", "regular", None),
}

_CPC_PRODUCTS: dict[str, tuple[str, str, str, int | None]] = {
    "92 Unleaded gasoline": ("Unleaded 92", "gasoline", "regular", 92),
    "95 Unleaded gasoline": ("Unleaded 95", "gasoline", "premium", 95),
    "98 Unleaded gasoline": ("Unleaded 98", "gasoline", "super_premium", 98),
    "Super/Premium diesel": ("Super Diesel", "diesel", "regular", None),
    # Fallback short names in case the page wording changes
    "92 Unleaded": ("Unleaded 92", "gasoline", "regular", 92),
    "95 Unleaded": ("Unleaded 95", "gasoline", "premium", 95),
    "98 Unleaded": ("Unleaded 98", "gasoline", "super_premium", 98),
    "Super Diesel": ("Super Diesel", "diesel", "regular", None),
}

_PRICE_MIN = 15.0
_PRICE_MAX = 60.0


def _find_data_rows(payload: object) -> list[dict]:
    """Walk known candidate keys to find the list of data rows in MOEA response.

    Confirmed API shape (2026-03):
      {"res": "01", "msg": "", "data": {"title": "...", "gasoline": [...]}}
    Each row in gasoline: {"Oil92": float, "Oil95": float, "Oil98": float,
                           "Oilchai": float, "SurDate": "YYYY/MM"}

    Also handles flat lists and other common wrappers as fallback.
    """
    if isinstance(payload, list):
        return payload

    if not isinstance(payload, dict):
        return []

    # Primary path: data.gasoline (confirmed structure)
    data_node = payload.get("data")
    if isinstance(data_node, dict):
        gasoline = data_node.get("gasoline")
        if isinstance(gasoline, list):
            return gasoline
        # Some endpoints may use different sub-keys
        for subkey in ("rows", "list", "result", "items", "prices"):
            sub = data_node.get(subkey)
            if isinstance(sub, list):
                return sub

    # Generic fallbacks
    for key in ("data", "rows", "list", "result", "items", "Data", "Rows", "List"):
        val = payload.get(key)
        if isinstance(val, list):
            return val

    # Last resort: any list-valued top-level key
    for val in payload.values():
        if isinstance(val, list) and val:
            return val

    return []


def fetch_tw_moea_nationwide_avg(cutoff: date) -> pd.DataFrame:
    """Fetch Taiwan MOEA monthly nationwide average fuel prices."""
    print("  [tw_moea] Fetching Taiwan MOEA nationwide average (monthly)...")
    print(f"  [tw_moea] Cutoff: {cutoff}")

    session = get_session()
    today = date.today()

    start_str = f"{cutoff.year}/{cutoff.month:02d}"
    end_str = f"{today.year}/{today.month:02d}"

    # Some servers require a prior GET to establish session cookies.
    try:
        session.get(_MOEA_GET_URL, timeout=20)
    except Exception as e:
        print(f"  [tw_moea] Warning: GET to establish session failed: {e}")

    try:
        resp = session.post(
            _MOEA_POST_URL,
            data={"unit": "month", "start": start_str, "end": end_str},
            timeout=30,
        )
        resp.raise_for_status()
    except Exception as e:
        print(f"  [tw_moea] POST failed: {e}")
        return pd.DataFrame()

    try:
        payload = resp.json()
    except Exception as e:
        print(f"  [tw_moea] JSON parse error: {e}")
        print(f"  [tw_moea] Response preview: {resp.text[:300]}")
        return pd.DataFrame()

    rows_raw = _find_data_rows(payload)
    if not rows_raw:
        print(
            f"  [tw_moea] Could not locate data rows in response. Keys: {list(payload.keys()) if isinstance(payload, dict) else type(payload)}"
        )
        print(f"  [tw_moea] Response preview: {str(payload)[:500]}")
        return pd.DataFrame()

    print(f"  [tw_moea] Found {len(rows_raw)} raw rows in response")

    all_rows: list[dict] = []
    unknown_keys: set[str] = set()

    for entry in rows_raw:
        if not isinstance(entry, dict):
            continue

        # Discover date and price columns — key names may vary
        # Common patterns: {"date": "2025/01", "product_name": price, ...}
        # or {"month": "2025/01", "name": "Unleaded-95", "price": 28.5}
        # We handle both flat and nested shapes.

        # Try to find a date-like value
        raw_date: str | None = None
        for dk in (
            "SurDate",
            "date",
            "Date",
            "month",
            "Month",
            "period",
            "Period",
            "yearMonth",
        ):
            v = entry.get(dk)
            if v and isinstance(v, str) and re.match(r"\d{4}[/\-]\d{1,2}", v):
                raw_date = v
                break

        if raw_date is None:
            continue

        try:
            parts = re.split(r"[/\-]", raw_date)
            year, month = int(parts[0]), int(parts[1])
            obs_date = date(year, month, 1)
        except (IndexError, ValueError):
            continue

        if obs_date <= cutoff:
            continue

        last_day = calendar.monthrange(year, month)[1]
        eff_from = obs_date
        eff_to = date(year, month, last_day)

        # Flat shape: remaining keys are product → price
        # Nested shape: entry has "name"/"product" + "price"/"value" keys
        name_key = next(
            (k for k in ("name", "Name", "product", "Product") if k in entry), None
        )
        price_key = next(
            (
                k
                for k in ("price", "Price", "value", "Value", "avg", "Avg")
                if k in entry
            ),
            None,
        )

        if name_key and price_key:
            # Nested: one product per row
            product_name = str(entry[name_key]).strip()
            spec = _MOEA_PRODUCTS.get(product_name)
            if spec is None:
                unknown_keys.add(product_name)
                continue
            try:
                price = float(entry[price_key])
            except (TypeError, ValueError):
                continue
            if not (_PRICE_MIN <= price <= _PRICE_MAX):
                continue
            fuel_product, fuel_family, quality_group, octane_ron = spec
            row = _TMPL_MOEA.copy()
            row.update(
                {
                    "fuel_family": fuel_family,
                    "fuel_product": fuel_product,
                    "quality_group": quality_group,
                    "octane_ron": octane_ron,
                    "price_local": price,
                    "effective_from": str(eff_from),
                    "effective_to": str(eff_to),
                    "observation_date": str(obs_date),
                    "source_url": _MOEA_POST_URL,
                }
            )
            row["observation_hash"] = make_hash(row)
            all_rows.append(row)
        else:
            # Flat: iterate remaining keys as product names
            skip_keys = {
                "SurDate",
                "date",
                "Date",
                "month",
                "Month",
                "period",
                "Period",
                "yearMonth",
            }
            for product_name, raw_val in entry.items():
                if product_name in skip_keys:
                    continue
                spec = _MOEA_PRODUCTS.get(product_name)
                if spec is None:
                    unknown_keys.add(product_name)
                    continue
                try:
                    price = float(raw_val)
                except (TypeError, ValueError):
                    continue
                if not (_PRICE_MIN <= price <= _PRICE_MAX):
                    continue
                fuel_product, fuel_family, quality_group, octane_ron = spec
                row = _TMPL_MOEA.copy()
                row.update(
                    {
                        "fuel_family": fuel_family,
                        "fuel_product": fuel_product,
                        "quality_group": quality_group,
                        "octane_ron": octane_ron,
                        "price_local": price,
                        "effective_from": str(eff_from),
                        "effective_to": str(eff_to),
                        "observation_date": str(obs_date),
                        "source_url": _MOEA_POST_URL,
                    }
                )
                row["observation_hash"] = make_hash(row)
                all_rows.append(row)

    if unknown_keys:
        print(
            f"  [tw_moea] Unrecognised product keys (not mapped): {sorted(unknown_keys)}"
        )

    print(f"  [tw_moea] {len(all_rows)} rows fetched (cutoff {cutoff})")
    return pd.DataFrame(all_rows) if all_rows else pd.DataFrame()


def fetch_tw_cpc_history_prices(cutoff: date) -> pd.DataFrame:
    """Fetch CPC Corp Taiwan historical retail prices from inline JS pieSeries."""
    print("  [tw_cpc] Fetching CPC Corp Taiwan history prices...")
    print(f"  [tw_cpc] Cutoff: {cutoff}")

    session = get_session()
    try:
        resp = session.get(_CPC_URL, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        print(f"  [tw_cpc] Fetch failed: {e}")
        return pd.DataFrame()

    html = resp.text
    m = re.search(r"var\s+pieSeries\s*=\s*(\[[\s\S]*?\]);", html)
    if not m:
        print("  [tw_cpc] Could not find pieSeries JS variable in page")
        return pd.DataFrame()

    try:
        pie_data = json.loads(m.group(1))
    except json.JSONDecodeError as e:
        print(f"  [tw_cpc] JSON parse error for pieSeries: {e}")
        return pd.DataFrame()

    if not isinstance(pie_data, list):
        print("  [tw_cpc] pieSeries is not a list")
        return pd.DataFrame()

    all_rows: list[dict] = []
    unknown_keys: set[str] = set()

    for entry in pie_data:
        if not isinstance(entry, dict):
            continue

        # Actual API shape: {name: "YYYY/MM/DD", data: [{name: product, y: price, GroupID: int}]}
        # Fallback flat shape: {date: "YYYY/MM/DD", name: product, y: price, GroupID: int}
        raw_date = entry.get("date") or entry.get("name")
        if not raw_date or not isinstance(raw_date, str):
            continue

        # Detect if this entry is a date-keyed container (has inner "data" list)
        inner_products = entry.get("data")
        if isinstance(inner_products, list):
            # Nested shape: outer name is the date
            try:
                obs_date = datetime.strptime(raw_date.strip(), "%Y/%m/%d").date()
            except ValueError:
                try:
                    obs_date = datetime.strptime(raw_date.strip(), "%Y-%m-%d").date()
                except ValueError:
                    continue

            if obs_date <= cutoff:
                continue

            for product_entry in inner_products:
                if not isinstance(product_entry, dict):
                    continue
                product_name = str(product_entry.get("name", "")).strip()
                spec = _CPC_PRODUCTS.get(product_name)
                if spec is None:
                    unknown_keys.add(product_name)
                    continue
                raw_y = product_entry.get("y")
                try:
                    price = float(raw_y)
                except (TypeError, ValueError):
                    continue
                if not (_PRICE_MIN <= price <= _PRICE_MAX):
                    continue
                fuel_product, fuel_family, quality_group, octane_ron = spec
                row = _TMPL_CPC.copy()
                row.update(
                    {
                        "fuel_family": fuel_family,
                        "fuel_product": fuel_product,
                        "quality_group": quality_group,
                        "octane_ron": octane_ron,
                        "price_local": price,
                        "effective_from": str(obs_date),
                        "effective_to": str(obs_date),
                        "observation_date": str(obs_date),
                        "source_url": _CPC_URL,
                        "notes": f"GroupID: {product_entry.get('GroupID')}",
                    }
                )
                row["observation_hash"] = make_hash(row)
                all_rows.append(row)
        else:
            # Flat shape: {date: "YYYY/MM/DD", name: product, y: price}
            raw_date_flat = entry.get("date")
            if not raw_date_flat:
                continue
            try:
                obs_date = datetime.strptime(
                    str(raw_date_flat).strip(), "%Y/%m/%d"
                ).date()
            except ValueError:
                try:
                    obs_date = datetime.strptime(
                        str(raw_date_flat).strip(), "%Y-%m-%d"
                    ).date()
                except ValueError:
                    continue

            if obs_date <= cutoff:
                continue

            product_name = str(entry.get("name", "")).strip()
            spec = _CPC_PRODUCTS.get(product_name)
            if spec is None:
                unknown_keys.add(product_name)
                continue
            raw_y = entry.get("y")
            try:
                price = float(raw_y)
            except (TypeError, ValueError):
                continue
            if not (_PRICE_MIN <= price <= _PRICE_MAX):
                continue
            fuel_product, fuel_family, quality_group, octane_ron = spec
            row = _TMPL_CPC.copy()
            row.update(
                {
                    "fuel_family": fuel_family,
                    "fuel_product": fuel_product,
                    "quality_group": quality_group,
                    "octane_ron": octane_ron,
                    "price_local": price,
                    "effective_from": str(obs_date),
                    "effective_to": str(obs_date),
                    "observation_date": str(obs_date),
                    "source_url": _CPC_URL,
                    "notes": f"GroupID: {entry.get('GroupID')}",
                }
            )
            row["observation_hash"] = make_hash(row)
            all_rows.append(row)

    if unknown_keys:
        print(
            f"  [tw_cpc] Unrecognised product names (not mapped): {sorted(unknown_keys)}"
        )

    print(f"  [tw_cpc] {len(all_rows)} rows fetched (cutoff {cutoff})")
    return pd.DataFrame(all_rows) if all_rows else pd.DataFrame()
