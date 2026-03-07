"""Global and EAP commodity oil/gasoline price fetchers.

Four sources:
  1. investing.com internal API (daily, best-effort — Cloudflare may block)
  2. EIA Open Data API v2  (daily, requires EIA_API_KEY env var)
  3. World Bank CMO Pink Sheet (monthly, no auth)
  4. IMF commodity prices via FRED API (monthly, requires FRED_API_KEY env var)
"""

import json
import os
from datetime import date, timedelta
from typing import Optional

import pandas as pd

from ..utils import get_session, make_hash, make_template

# ---------------------------------------------------------------------------
# Shared commodity definitions
# ---------------------------------------------------------------------------

_GLOBAL = dict(country="Global", wb_iso3="WLD", subnational_area="Global")
_EAP = dict(country="EAP", wb_iso3="EAP", subnational_area="East Asia & Pacific")

_INVESTING_SLUGS: list[dict] = [
    dict(
        slug="crude-oil",
        fuel_product="WTI Crude Oil",
        fuel_family="crude_oil",
        quality_group="wti",
        unit="bbl",
        currency="USD",
        **_GLOBAL,
    ),
    dict(
        slug="brent-oil",
        fuel_product="Brent Crude Oil",
        fuel_family="crude_oil",
        quality_group="brent",
        unit="bbl",
        currency="USD",
        **_GLOBAL,
    ),
    dict(
        slug="gasoline-rbob",
        fuel_product="Gasoline RBOB",
        fuel_family="gasoline",
        quality_group="regular",
        unit="gal",
        currency="USD",
        **_GLOBAL,
    ),
    dict(
        slug="dubai-crude-oil-platts-futures",
        fuel_product="Dubai Crude Oil (Platts)",
        fuel_family="crude_oil",
        quality_group="dubai",
        unit="bbl",
        currency="USD",
        **_EAP,
    ),
    dict(
        slug="nymex-singapore-gasoil-platts-c1-futures",
        fuel_product="Singapore Gasoil (Platts)",
        fuel_family="gasoil",
        quality_group="regular",
        unit="bbl",
        currency="USD",
        **_EAP,
    ),
]

_EIA_SERIES: list[dict] = [
    dict(
        series="RBRTE",
        fuel_product="Brent Crude Oil Spot",
        fuel_family="crude_oil",
        quality_group="brent",
        unit="bbl",
        currency="USD",
        **_GLOBAL,
    ),
    dict(
        series="RWTC",
        fuel_product="WTI Crude Oil Spot",
        fuel_family="crude_oil",
        quality_group="wti",
        unit="bbl",
        currency="USD",
        **_GLOBAL,
    ),
    dict(
        series="RGASNYUSG",
        fuel_product="NY Harbor Gasoline Spot",
        fuel_family="gasoline",
        quality_group="regular",
        unit="gal",
        currency="USD",
        **_GLOBAL,
    ),
]

_WB_PINK_COLS: list[dict] = [
    dict(
        col_pattern="crude oil, average",
        fuel_product="Crude Oil Average (Brent+Dubai+WTI)",
        fuel_family="crude_oil",
        quality_group="average",
        unit="bbl",
        currency="USD",
        **_GLOBAL,
    ),
    dict(
        col_pattern="crude oil, brent",
        fuel_product="Brent Crude Oil",
        fuel_family="crude_oil",
        quality_group="brent",
        unit="bbl",
        currency="USD",
        **_GLOBAL,
    ),
    dict(
        col_pattern="crude oil, wti",
        fuel_product="WTI Crude Oil",
        fuel_family="crude_oil",
        quality_group="wti",
        unit="bbl",
        currency="USD",
        **_GLOBAL,
    ),
    dict(
        col_pattern="crude oil, dubai",
        fuel_product="Dubai Crude Oil",
        fuel_family="crude_oil",
        quality_group="dubai",
        unit="bbl",
        currency="USD",
        **_EAP,
    ),
]

_FRED_SERIES: list[dict] = [
    dict(
        series="POILWTIUSDM",
        fuel_product="WTI Crude Oil (IMF)",
        fuel_family="crude_oil",
        quality_group="wti",
        unit="bbl",
        currency="USD",
        **_GLOBAL,
    ),
    dict(
        series="POILBREUSDM",
        fuel_product="Brent Crude Oil (IMF)",
        fuel_family="crude_oil",
        quality_group="brent",
        unit="bbl",
        currency="USD",
        **_GLOBAL,
    ),
    dict(
        series="POILDUBUSDM",
        fuel_product="Dubai Crude Oil (IMF)",
        fuel_family="crude_oil",
        quality_group="dubai",
        unit="bbl",
        currency="USD",
        **_EAP,
    ),
]

_WB_XLSX_URL = (
    "https://thedocs.worldbank.org/en/doc/"
    "18675f1d1639c7a34d463f59263ba0a2-0050012025/related/CMO-Historical-Data-Monthly.xlsx"
)

# ---------------------------------------------------------------------------
# Source 1: investing.com internal API (daily, best-effort)
# ---------------------------------------------------------------------------

_INVESTING_BASE = "https://www.investing.com/commodities/"
_INVESTING_API = (
    "https://api.investing.com/api/financialdata/historical/{instrument_id}"
)
_INVESTING_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.investing.com/",
    "Origin": "https://www.investing.com",
    "domain-id": "www",
}


def _get_instrument_id(slug: str, session) -> Optional[int]:
    """Fetch commodity page and extract instrument_id from __NEXT_DATA__ JSON."""
    url = f"{_INVESTING_BASE}{slug}"
    try:
        resp = session.get(url, timeout=20)
        if resp.status_code != 200:
            print(f"  [investing] HTTP {resp.status_code} for {slug}")
            return None
    except Exception as e:
        print(f"  [investing] Fetch error for {slug}: {e}")
        return None

    html = resp.text
    start = html.find('<script id="__NEXT_DATA__"')
    if start == -1:
        print(f"  [investing] __NEXT_DATA__ not found for {slug}")
        return None
    start = html.find(">", start) + 1
    end = html.find("</script>", start)
    if end == -1:
        return None

    try:
        data = json.loads(html[start:end])
    except Exception as e:
        print(f"  [investing] JSON parse error for {slug}: {e}")
        return None

    def _find_instrument_id(obj, depth=0):
        if depth > 20:
            return None
        if isinstance(obj, dict):
            if "instrument_id" in obj:
                try:
                    return int(obj["instrument_id"])
                except (ValueError, TypeError):
                    pass
            if "instrumentId" in obj:
                try:
                    return int(obj["instrumentId"])
                except (ValueError, TypeError):
                    pass
            for v in obj.values():
                result = _find_instrument_id(v, depth + 1)
                if result is not None:
                    return result
        elif isinstance(obj, list):
            for item in obj:
                result = _find_instrument_id(item, depth + 1)
                if result is not None:
                    return result
        return None

    instrument_id = _find_instrument_id(data)
    if instrument_id is None:
        print(f"  [investing] instrument_id not found in __NEXT_DATA__ for {slug}")
    return instrument_id


def _fetch_investing_series(
    instrument_id: int, slug: str, cutoff: date, session
) -> list[dict]:
    """Fetch daily history from investing.com internal API for one instrument."""
    start_str = cutoff.strftime("%Y-%m-%d")
    end_str = date.today().strftime("%Y-%m-%d")
    url = _INVESTING_API.format(instrument_id=instrument_id)
    params = {
        "start-date": start_str,
        "end-date": end_str,
        "time-frame": "Daily",
        "add-missing-rows": "false",
    }
    try:
        resp = session.get(url, params=params, headers=_INVESTING_HEADERS, timeout=30)
        if resp.status_code == 403:
            print(f"  [investing] 403 Forbidden for {slug} — Cloudflare blocking")
            return []
        if resp.status_code != 200:
            print(f"  [investing] HTTP {resp.status_code} for {slug} API")
            return []
        payload = resp.json()
    except Exception as e:
        print(f"  [investing] API error for {slug}: {e}")
        return []

    rows_data = payload.get("data", [])
    if not rows_data:
        rows_data = payload.get("Data", [])

    results = []
    for entry in rows_data:
        try:
            obs_date = pd.to_datetime(
                entry.get("rowDate") or entry.get("date") or entry.get("Date")
            ).date()
        except Exception:
            continue
        if obs_date <= cutoff:
            continue
        price_raw = (
            entry.get("last_close")
            or entry.get("price")
            or entry.get("Price")
            or entry.get("last")
        )
        try:
            price = float(price_raw)
        except (TypeError, ValueError):
            continue
        if price <= 0:
            continue
        results.append({"obs_date": obs_date, "price": price})

    return results


def fetch_investing_commodities(cutoff: date) -> pd.DataFrame:
    """Fetch daily global/EAP commodity prices from investing.com (best-effort)."""
    print("  [investing] Fetching investing.com commodity data...")
    print(f"  [investing] Cutoff: {cutoff}")

    session = get_session()
    session.headers.update(_INVESTING_HEADERS)

    all_rows = []
    for spec in _INVESTING_SLUGS:
        slug = spec["slug"]
        print(f"  [investing] → {slug}")
        instrument_id = _get_instrument_id(slug, session)
        if instrument_id is None:
            continue

        raw_rows = _fetch_investing_series(instrument_id, slug, cutoff, session)
        if not raw_rows:
            print(f"  [investing]   0 rows for {slug}")
            continue

        tmpl = make_template(
            country=spec["country"],
            wb_iso3=spec["wb_iso3"],
            subnational_area=spec["subnational_area"],
            fuel_family=spec["fuel_family"],
            fuel_product=spec["fuel_product"],
            quality_group=spec["quality_group"],
            currency=spec["currency"],
            unit=spec["unit"],
            source_key="global_investing_daily",
            source_name="Investing.com Commodity Futures",
            source_url=f"{_INVESTING_BASE}{slug}-historical-data",
            source_type="market",
            publication_frequency="daily",
            observation_method="market",
            tax_status="pre_tax",
        )

        for entry in raw_rows:
            obs_date = entry["obs_date"]
            r = tmpl.copy()
            r.update(
                {
                    "price_local": round(entry["price"], 4),
                    "effective_from": str(obs_date),
                    "effective_to": str(obs_date),
                    "observation_date": str(obs_date),
                    "source_url": f"{_INVESTING_BASE}{slug}-historical-data",
                }
            )
            r["observation_hash"] = make_hash(r)
            all_rows.append(r)

        print(f"  [investing]   {len(raw_rows)} rows for {slug}")

    print(f"  [investing] Total: {len(all_rows)} rows")
    return pd.DataFrame(all_rows) if all_rows else pd.DataFrame()


# ---------------------------------------------------------------------------
# Source 2: EIA Open Data API v2 (daily)
# ---------------------------------------------------------------------------

_EIA_API_BASE = "https://api.eia.gov/v2/petroleum/pri/spt/data/"


def fetch_eia_spot_prices(cutoff: date) -> pd.DataFrame:
    """Fetch daily WTI, Brent, and NY Harbor gasoline spot prices from EIA API v2."""
    print("  [eia] Fetching EIA spot price data...")
    print(f"  [eia] Cutoff: {cutoff}")

    api_key = os.environ.get("EIA_API_KEY", "").strip()
    if not api_key:
        print(
            "  [eia] EIA_API_KEY environment variable not set.\n"
            "  [eia] Register at https://www.eia.gov/opendata/ to get a free key.\n"
            "  [eia] Then: export EIA_API_KEY=your_key_here"
        )
        return pd.DataFrame()

    session = get_session()
    all_rows = []

    series_ids = [s["series"] for s in _EIA_SERIES]
    params = {
        "api_key": api_key,
        "frequency": "daily",
        "data[]": "value",
        "facets[series][]": series_ids,
        "start": cutoff.strftime("%Y-%m-%d"),
        "end": date.today().strftime("%Y-%m-%d"),
        "sort[0][column]": "period",
        "sort[0][direction]": "asc",
        "offset": 0,
        "length": 5000,
    }

    try:
        resp = session.get(_EIA_API_BASE, params=params, timeout=60)
        if resp.status_code == 403:
            print("  [eia] 403 — Invalid or missing API key")
            return pd.DataFrame()
        resp.raise_for_status()
        payload = resp.json()
    except Exception as e:
        print(f"  [eia] Request error: {e}")
        return pd.DataFrame()

    data = payload.get("response", {}).get("data", [])
    if not data:
        print("  [eia] No data returned")
        return pd.DataFrame()

    series_lookup = {s["series"]: s for s in _EIA_SERIES}

    for entry in data:
        series_id = entry.get("series", "")
        spec = series_lookup.get(series_id)
        if spec is None:
            continue
        try:
            obs_date = pd.to_datetime(entry["period"]).date()
        except Exception:
            continue
        if obs_date <= cutoff:
            continue
        try:
            price = float(entry["value"])
        except (TypeError, ValueError):
            continue
        if price <= 0:
            continue

        tmpl = make_template(
            country=spec["country"],
            wb_iso3=spec["wb_iso3"],
            subnational_area=spec["subnational_area"],
            fuel_family=spec["fuel_family"],
            fuel_product=spec["fuel_product"],
            quality_group=spec["quality_group"],
            currency=spec["currency"],
            unit=spec["unit"],
            source_key="global_eia_spot_daily",
            source_name="EIA Weekly Petroleum Supply Indicators — Spot Prices",
            source_url=_EIA_API_BASE,
            source_type="official",
            publication_frequency="daily",
            observation_method="market",
            tax_status="pre_tax",
        )
        tmpl.update(
            {
                "price_local": round(price, 4),
                "effective_from": str(obs_date),
                "effective_to": str(obs_date),
                "observation_date": str(obs_date),
                "notes": f"EIA series: {series_id}",
            }
        )
        tmpl["observation_hash"] = make_hash(tmpl)
        all_rows.append(tmpl)

    print(f"  [eia] {len(all_rows)} rows fetched")
    return pd.DataFrame(all_rows) if all_rows else pd.DataFrame()


# ---------------------------------------------------------------------------
# Source 3: World Bank CMO Pink Sheet (monthly, no auth)
# ---------------------------------------------------------------------------


def fetch_wb_pink_sheet(cutoff: date) -> pd.DataFrame:
    """Fetch monthly commodity prices from World Bank CMO Pink Sheet Excel."""
    print("  [wb_pink] Fetching World Bank CMO Pink Sheet data...")
    print(f"  [wb_pink] Cutoff: {cutoff}")
    print(f"  [wb_pink] URL: {_WB_XLSX_URL}")

    session = get_session()
    try:
        resp = session.get(_WB_XLSX_URL, timeout=120)
        resp.raise_for_status()
    except Exception as e:
        print(f"  [wb_pink] Download error: {e}")
        return pd.DataFrame()

    try:
        xf = pd.ExcelFile(resp.content)
    except Exception as e:
        print(f"  [wb_pink] Excel open error: {e}")
        return pd.DataFrame()

    monthly_sheet = None
    for name in xf.sheet_names:
        if "monthly" in name.lower() or name.strip().lower() == "monthly prices":
            monthly_sheet = name
            break
    if monthly_sheet is None:
        monthly_sheet = xf.sheet_names[0]
        print(
            f"  [wb_pink] 'Monthly prices' sheet not found; using first: '{monthly_sheet}'"
        )

    try:
        raw = pd.read_excel(resp.content, sheet_name=monthly_sheet, header=None)
    except Exception as e:
        print(f"  [wb_pink] Sheet read error: {e}")
        return pd.DataFrame()

    header_row_idx = None
    for i, row in raw.iterrows():
        row_str = " ".join(str(v).lower() for v in row.values if pd.notna(v))
        if "crude oil" in row_str or "petroleum" in row_str:
            header_row_idx = i
            break

    if header_row_idx is None:
        print("  [wb_pink] Could not locate header row with commodity names")
        return pd.DataFrame()

    header_row = raw.iloc[header_row_idx]
    data_rows = raw.iloc[header_row_idx + 1 :].copy()
    data_rows.columns = range(len(data_rows.columns))

    date_col = 0
    col_map: dict[int, dict] = {}
    for col_idx, col_name in header_row.items():
        if pd.isna(col_name) or col_idx == date_col:
            continue
        col_lower = str(col_name).strip().lower()
        for spec in _WB_PINK_COLS:
            if spec["col_pattern"] in col_lower:
                col_map[col_idx] = spec
                break

    if not col_map:
        print("  [wb_pink] No matching commodity columns found")
        return pd.DataFrame()

    all_rows = []
    for _, row in data_rows.iterrows():
        raw_date = row[date_col]
        if pd.isna(raw_date):
            continue
        try:
            obs_date = pd.to_datetime(raw_date).date()
            obs_date = obs_date.replace(day=1)
        except Exception:
            continue
        if obs_date <= cutoff:
            continue
        if obs_date > date.today():
            continue

        for col_idx, spec in col_map.items():
            try:
                price = float(row[col_idx])
            except (TypeError, ValueError):
                continue
            if pd.isna(price) or price <= 0:
                continue

            month_end = obs_date.replace(day=28) + timedelta(days=4)
            month_end = month_end - timedelta(days=month_end.day)

            tmpl = make_template(
                country=spec["country"],
                wb_iso3=spec["wb_iso3"],
                subnational_area=spec["subnational_area"],
                fuel_family=spec["fuel_family"],
                fuel_product=spec["fuel_product"],
                quality_group=spec["quality_group"],
                currency=spec["currency"],
                unit=spec["unit"],
                source_key="global_wb_pinksheet",
                source_name="World Bank Commodity Markets (Pink Sheet)",
                source_url=_WB_XLSX_URL,
                source_type="official",
                publication_frequency="monthly",
                observation_method="reported",
                tax_status="pre_tax",
            )
            tmpl.update(
                {
                    "price_local": round(price, 4),
                    "effective_from": str(obs_date),
                    "effective_to": str(month_end),
                    "observation_date": str(obs_date),
                }
            )
            tmpl["observation_hash"] = make_hash(tmpl)
            all_rows.append(tmpl)

    print(f"  [wb_pink] {len(all_rows)} rows fetched")
    return pd.DataFrame(all_rows) if all_rows else pd.DataFrame()


# ---------------------------------------------------------------------------
# Source 4: IMF commodity prices via FRED API (monthly)
# ---------------------------------------------------------------------------

_FRED_OBS_URL = "https://api.stlouisfed.org/fred/series/observations"


def fetch_imf_fred_prices(cutoff: date) -> pd.DataFrame:
    """Fetch monthly IMF commodity prices (WTI, Brent, Dubai) from FRED API."""
    print("  [imf_fred] Fetching IMF commodity prices via FRED API...")
    print(f"  [imf_fred] Cutoff: {cutoff}")

    api_key = os.environ.get("FRED_API_KEY", "").strip()
    if not api_key:
        print(
            "  [imf_fred] FRED_API_KEY environment variable not set.\n"
            "  [imf_fred] Register at https://fredaccount.stlouisfed.org/ to get a free key.\n"
            "  [imf_fred] Then: export FRED_API_KEY=your_key_here"
        )
        return pd.DataFrame()

    session = get_session()
    all_rows = []

    for spec in _FRED_SERIES:
        series_id = spec["series"]
        params = {
            "series_id": series_id,
            "api_key": api_key,
            "file_type": "json",
            "observation_start": cutoff.strftime("%Y-%m-%d"),
            "observation_end": date.today().strftime("%Y-%m-%d"),
            "sort_order": "asc",
        }
        try:
            resp = session.get(_FRED_OBS_URL, params=params, timeout=30)
            if resp.status_code == 400:
                print(
                    f"  [imf_fred] 400 — Bad request for series {series_id}; check API key"
                )
                continue
            resp.raise_for_status()
            payload = resp.json()
        except Exception as e:
            print(f"  [imf_fred] Error fetching {series_id}: {e}")
            continue

        observations = payload.get("observations", [])
        count = 0
        for obs in observations:
            val_str = obs.get("value", ".")
            if val_str == ".":
                continue
            try:
                obs_date = pd.to_datetime(obs["date"]).date()
                obs_date = obs_date.replace(day=1)
            except Exception:
                continue
            if obs_date <= cutoff:
                continue
            try:
                price = float(val_str)
            except (TypeError, ValueError):
                continue
            if price <= 0:
                continue

            month_end = obs_date.replace(day=28) + timedelta(days=4)
            month_end = month_end - timedelta(days=month_end.day)

            tmpl = make_template(
                country=spec["country"],
                wb_iso3=spec["wb_iso3"],
                subnational_area=spec["subnational_area"],
                fuel_family=spec["fuel_family"],
                fuel_product=spec["fuel_product"],
                quality_group=spec["quality_group"],
                currency=spec["currency"],
                unit=spec["unit"],
                source_key="global_imf_fred_monthly",
                source_name="IMF Primary Commodity Prices (via FRED)",
                source_url=f"https://fred.stlouisfed.org/series/{series_id}",
                source_type="official",
                publication_frequency="monthly",
                observation_method="reported",
                tax_status="pre_tax",
            )
            tmpl.update(
                {
                    "price_local": round(price, 4),
                    "effective_from": str(obs_date),
                    "effective_to": str(month_end),
                    "observation_date": str(obs_date),
                    "notes": f"FRED series: {series_id}",
                }
            )
            tmpl["observation_hash"] = make_hash(tmpl)
            all_rows.append(tmpl)
            count += 1

        print(f"  [imf_fred]   {series_id}: {count} rows")

    print(f"  [imf_fred] Total: {len(all_rows)} rows")
    return pd.DataFrame(all_rows) if all_rows else pd.DataFrame()
