"""World Bank Real-Time Energy Prices (RTEP) — shared loader for SSA countries.

The Microdata Library's table API at
``microdata.worldbank.org/index.php/api/tables/data/FCV/WLD_2023_RTEP_v01_M``
returns CSV content encoded as UTF-16-LE without a BOM (the HTTP
``Content-Type`` header misreports it as ``charset=utf-8``). The API
silently caps any ``limit`` above 10000 to 100 rows, so the full table
(~86k rows × 55 columns) must be paged via ``offset`` with
``limit=10000``. The API ignores ``filter[ISO3]=...`` so per-country
slicing happens client-side after the full table is downloaded.

Caching: the first per-country fetcher to run each month downloads the
full table once, partitions it by ISO3, and writes each country's slice
to its canonical observations directory as
``data/fuel/ssa/<sub>/<country>/wb_rtep/upstream_<YYYY-MM>.csv``.
Subsequent country fetchers within the same month read their own slice.
"""

from __future__ import annotations

import io
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zipfile import ZipFile

import pandas as pd

from core.http import make_session

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[5]
_DATA_DIR = _PROJECT_ROOT / "data" / "fuel" / "ssa"
_SOURCE_DIR = "wb_rtep"

_API_URL = (
    "https://microdata.worldbank.org/index.php/api/tables/data/FCV/"
    "WLD_2023_RTEP_v01_M"
)
_CATALOG_URL = "https://microdata.worldbank.org/index.php/catalog/6134"
_PAGE_SIZE = 10000
_RECENT_MONTHS = 6

_PRODUCTS: dict[str, tuple[str, str]] = {
    "c_fuel_diesel": ("Fuel diesel", "L"),
    "c_fuel_gas": ("Fuel gas", "kg"),
    "c_fuel_kerosene": ("Fuel kerosene", "L"),
    "c_fuel_petrol_gasoline": ("Fuel petrol gasoline", "L"),
    "c_fuel_petrol_gasoline_95_octane": ("Fuel petrol gasoline 95 octane", "L"),
    "c_fuel_super_petrol": ("Fuel super petrol", "L"),
}

_COUNTRIES: dict[str, dict] = {
    "gm": {
        "name": "Gambia, The",
        "iso3": "GMB",
        "default_currency": "GMD",
        "source_key": "wb_rtep_gm_monthly",
        "aliases": {"gambia"},
        "subregion": "west_africa",
        "country_slug": "gambia",
    },
    "gw": {
        "name": "Guinea-Bissau",
        "iso3": "GNB",
        "default_currency": "XOF",
        "source_key": "wb_rtep_gw_monthly",
        "aliases": set(),
        "subregion": "west_africa",
        "country_slug": "guinea_bissau",
    },
    "lr": {
        "name": "Liberia",
        "iso3": "LBR",
        "default_currency": "LRD",
        "source_key": "wb_rtep_lr_monthly",
        "aliases": set(),
        "subregion": "west_africa",
        "country_slug": "liberia",
    },
    "ng": {
        "name": "Nigeria",
        "iso3": "NGA",
        "default_currency": "NGN",
        "source_key": "wb_rtep_ng_monthly",
        "aliases": set(),
        "subregion": "west_africa",
        "country_slug": "nigeria",
    },
    "so": {
        "name": "Somalia",
        "iso3": "SOM",
        "default_currency": "SOS",
        "source_key": "wb_rtep_so_monthly",
        "aliases": set(),
        "subregion": "east_africa",
        "country_slug": "somalia",
    },
    "ss": {
        "name": "South Sudan",
        "iso3": "SSD",
        "default_currency": "SSP",
        "source_key": "wb_rtep_ss_monthly",
        "aliases": set(),
        "subregion": "east_africa",
        "country_slug": "south_sudan",
    },
}


def _country_cache_path(cc: str, stamp: str | None = None) -> Path:
    if stamp is None:
        stamp = datetime.utcnow().strftime("%Y-%m")
    meta = _COUNTRIES[cc]
    return (
        _DATA_DIR
        / meta["subregion"]
        / meta["country_slug"]
        / _SOURCE_DIR
        / f"upstream_{stamp}.csv"
    )


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(col).strip().lower() for col in df.columns]
    return df


def _first_existing(df: pd.DataFrame, names: tuple[str, ...]) -> str | None:
    for name in names:
        if name in df.columns:
            return name
    return None


def _rows_from_payload(payload: Any) -> tuple[list[dict], int | None]:
    rows: list[dict] = []
    total: int | None = None

    def walk(obj: Any) -> None:
        nonlocal rows, total
        if isinstance(obj, dict):
            for key in ("total", "found", "recordsTotal", "rows_count"):
                value = obj.get(key)
                if total is None and isinstance(value, int):
                    total = value
            for value in obj.values():
                walk(value)
        elif isinstance(obj, list) and obj:
            if all(isinstance(item, dict) for item in obj):
                keys = {str(key).lower() for row in obj for key in row.keys()}
                if {"iso3", "country", "dates", "mkt_name"} & keys and any(
                    key.startswith("c_fuel_") for key in keys
                ):
                    rows = obj

    walk(payload)
    return rows, total


def _read_response_as_csv(content: bytes) -> pd.DataFrame | None:
    head = content[:500].lstrip().lower()
    if head.startswith(b"<") or head.startswith(b"{") or head.startswith(b"["):
        return None
    if content[:2] == b"PK":
        with ZipFile(io.BytesIO(content)) as zf:
            csv_names = [n for n in zf.namelist() if n.lower().endswith(".csv")]
            if not csv_names:
                return None
            with zf.open(csv_names[0]) as fh:
                return pd.read_csv(fh)
    # The WB tables API serves UTF-16-LE without BOM.
    for enc in ("utf-16-le", "utf-16", "utf-8"):
        try:
            return pd.read_csv(io.BytesIO(content), encoding=enc)
        except (UnicodeError, UnicodeDecodeError):
            continue
        except Exception:
            return None
    return None


def _download_full_table() -> pd.DataFrame:
    session = make_session(Accept="text/csv,application/json,*/*")
    parts: list[pd.DataFrame] = []
    offset = 0
    while True:
        resp = session.get(
            _API_URL,
            params={"format": "csv", "limit": _PAGE_SIZE, "offset": offset},
            timeout=180,
        )
        resp.raise_for_status()
        page_df = _read_response_as_csv(resp.content)
        if page_df is None or page_df.empty:
            break
        parts.append(page_df)
        if len(page_df) < _PAGE_SIZE:
            break
        offset += len(page_df)

    if parts:
        return pd.concat(parts, ignore_index=True)

    rows: list[dict] = []
    offset = 0
    total: int | None = None
    while True:
        resp = session.get(
            _API_URL,
            params={"limit": 1000, "offset": offset},
            timeout=120,
        )
        resp.raise_for_status()
        page_rows, page_total = _rows_from_payload(resp.json())
        if total is None:
            total = page_total
        if not page_rows:
            break
        rows.extend(page_rows)
        offset += len(page_rows)
        if total is not None and offset >= total:
            break
        if len(page_rows) < 1000:
            break

    if not rows:
        raise RuntimeError(f"World Bank RTEP table returned no rows: {_CATALOG_URL}")

    return pd.DataFrame(rows)


def _partition_and_cache(full: pd.DataFrame, stamp: str) -> None:
    """Slice the global table by ISO3 and write one upstream cache per country."""
    iso_col = None
    for candidate in ("ISO3", "iso3", "country_code", "countrycode"):
        if candidate in full.columns:
            iso_col = candidate
            break
    if iso_col is None:
        return
    for cc, meta in _COUNTRIES.items():
        slice_df = full[full[iso_col].astype(str).str.upper() == meta["iso3"]]
        if slice_df.empty:
            continue
        path = _country_cache_path(cc, stamp)
        path.parent.mkdir(parents=True, exist_ok=True)
        slice_df.to_csv(path, index=False)


def _load_country_slice(cc: str) -> pd.DataFrame:
    """Return this country's upstream slice, downloading + partitioning if needed."""
    stamp = datetime.utcnow().strftime("%Y-%m")
    cache = _country_cache_path(cc, stamp)
    if cache.exists() and cache.stat().st_size > 0:
        return pd.read_csv(cache)
    full = _download_full_table()
    _partition_and_cache(full, stamp)
    if cache.exists() and cache.stat().st_size > 0:
        return pd.read_csv(cache)
    # Fallback if partitioning failed (no ISO3 column): return the in-memory full table.
    return full


def _parse_date(value: object) -> pd.Timestamp | None:
    if value is None or pd.isna(value):
        return None
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return None
    return parsed.to_period("M").to_timestamp()


def _parse_price(value: object) -> float | None:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip().replace(",", "")
    if not text or text in {"-", "NA", "N/A", "nan"}:
        return None
    try:
        price = float(text)
    except ValueError:
        return None
    return price if price > 0 else None


def _is_national_market(value: object) -> bool:
    text = str(value or "").strip().lower()
    return text in {"average", "national average", "national_avg"} or (
        "national" in text and "average" in text
    )


def _market_fields(
    row: pd.Series,
    market_col: str | None,
    adm1_col: str | None,
    adm2_col: str | None,
) -> tuple[str, str]:
    market = str(row.get(market_col, "") if market_col else "").strip()
    adm1 = str(row.get(adm1_col, "") if adm1_col else "").strip()
    adm2 = str(row.get(adm2_col, "") if adm2_col else "").strip()
    if (
        _is_national_market(market)
        or _is_national_market(adm1)
        or _is_national_market(adm2)
    ):
        return "", "national_avg"
    subnational = adm2 or adm1
    return market, subnational


def _scrape_country(cc: str, meta: dict, cutoff: date) -> pd.DataFrame | None:
    raw = _normalize_columns(_load_country_slice(cc))
    iso_col = _first_existing(raw, ("iso3", "country_code", "countrycode"))
    country_col = _first_existing(raw, ("country", "country_name"))
    date_col = _first_existing(raw, ("dates", "observation_date", "date", "month"))
    market_col = _first_existing(raw, ("mkt_name", "market", "market_name"))
    adm1_col = _first_existing(raw, ("adm1_name", "admin1", "region", "state"))
    adm2_col = _first_existing(raw, ("adm2_name", "admin2", "subnational_area"))
    currency_col = _first_existing(raw, ("cur_name", "currency"))

    if date_col is None:
        raise RuntimeError("World Bank RTEP table has no date column")
    if iso_col:
        src = raw[raw[iso_col].astype(str).str.upper() == meta["iso3"]].copy()
    elif country_col:
        names = {meta["name"].lower(), *meta.get("aliases", set())}
        src = raw[raw[country_col].astype(str).str.lower().isin(names)].copy()
    else:
        raise RuntimeError("World Bank RTEP table has no country column")
    if src.empty:
        return None

    src["_obs_date"] = src[date_col].map(_parse_date)
    src = src[src["_obs_date"].notna()].copy()
    if src.empty:
        return None
    latest = src["_obs_date"].max()
    recent_floor = latest - pd.DateOffset(months=_RECENT_MONTHS)
    src = src[
        (src["_obs_date"].dt.date > cutoff) | (src["_obs_date"] >= recent_floor)
    ].copy()
    if src.empty:
        return None

    rows: list[dict] = []
    for _, row in src.iterrows():
        obs_date = row["_obs_date"].date().isoformat()
        city, subnational = _market_fields(row, market_col, adm1_col, adm2_col)
        currency = (
            str(row.get(currency_col, "") if currency_col else "").strip()
            or meta["default_currency"]
        )
        for column, (product, unit) in _PRODUCTS.items():
            if column not in src.columns:
                continue
            price = _parse_price(row.get(column))
            if price is None:
                continue
            rows.append(
                {
                    "observation_date": obs_date,
                    "country": meta["name"],
                    "fuel_product": product,
                    "price_local": price,
                    "currency": currency,
                    "source_key": meta["source_key"],
                    "unit": unit,
                    "city": city,
                    "subnational_area": subnational,
                }
            )

    if not rows:
        return None
    return (
        pd.DataFrame(rows)
        .drop_duplicates(
            subset=["observation_date", "fuel_product", "city", "subnational_area"]
        )
        .sort_values(["observation_date", "fuel_product", "subnational_area", "city"])
        .reset_index(drop=True)
    )


def _make_fetcher(cc: str):
    meta = _COUNTRIES[cc]

    def _fetch(cutoff: date) -> pd.DataFrame | None:
        return _scrape_country(cc, meta, cutoff)

    _fetch.__name__ = f"fetch_wb_rtep_{cc}"
    _fetch.__doc__ = f"Fetch World Bank RTEP monthly fuel prices for {meta['name']}."
    return _fetch


fetch_wb_rtep_gm = _make_fetcher("gm")
fetch_wb_rtep_gw = _make_fetcher("gw")
fetch_wb_rtep_lr = _make_fetcher("lr")
fetch_wb_rtep_ng = _make_fetcher("ng")
fetch_wb_rtep_so = _make_fetcher("so")
fetch_wb_rtep_ss = _make_fetcher("ss")
