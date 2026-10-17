"""EAP Excel export from the legacy pacific-observatory enriched CSV.

EAP fuel still runs on the legacy pipeline, so its Excel cannot come from
``export_region_xlsx``. This module reads the legacy
``retail_series_enriched.csv`` and writes ``eap_fuel_prices.xlsx`` with the
same sheets as the other regions: ``data``, ``sources`` and ``freshness``.

Rules ported from the refresh-fuel-dashboards skill's ``gen_eap_excel.py``:
source exclusions, per-litre normalisation (LPG kg x 0.54 kg/L) and URL
backfill from the legacy ``fuel_source_inventory.xlsx``.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from .publish import _OUTPUTS_DIR, _PROJECT_ROOT
from .publish_xlsx import _DATA_COLS_STATIC

logger = logging.getLogger(__name__)


def _legacy_root() -> Path:
    """The sibling pacific-observatory checkout, also found from a worktree."""
    for p in [_PROJECT_ROOT, *_PROJECT_ROOT.parents]:
        if (p.parent / "pacific-observatory").is_dir():
            return p.parent / "pacific-observatory"
    return _PROJECT_ROOT.parent / "pacific-observatory"


_LEGACY_DATA = _legacy_root() / "data" / "cpi"
DEFAULT_LEGACY_CSV = (
    _LEGACY_DATA / "fuel_prices_staged" / "enrich" / "retail_series_enriched.csv"
)
DEFAULT_SOURCE_INVENTORY = _LEGACY_DATA / "fuel_prices" / "fuel_source_inventory.xlsx"
DEFAULT_OUT_DIR = _OUTPUTS_DIR / "excels"

# Excluded from the EAP Excel (decided 2026-05-29); all gpp_* are excluded too.
EXCLUDED_SOURCES = {
    "au_accc_5largestcities_quarterly",
    "au_fuelwatch_perth_daily",
    "fiji_fccc_monthly_prices",
    "kh_moc_fuel_notices",
    "kr_opinet_weekly_national_sampled_2025",
    "lao_kpl_fuel_notices",
    "mn_data_mn_a92_aimags",
    "mn_data_mn_diesel_aimags",
    "mn_data_mn_fuel_ulaanbaatar",
    "my_mof_weekly_petroleum",
    "ph_doe_visayas_weekly",
    "pw_ops_fuel_prices_quarterly",
    "vn_moit_fuel",
}

# China NDRC Gasoline/Diesel are CNY/ton: litres per ton by product.
CN_TON_TO_L = {"Gasoline": 1379.0, "Diesel": 1197.6}
LPG_KG_PER_L = 0.54
GAL_TO_L = 3.78541

URL_OVERRIDES = {
    "mm_starfish_market_price": "https://starfishmyanmar.com/market-price?",
    "th_eppo_retail_daily": "https://www.eppo.go.th/wp-json/oil-api/v1/oil-prices",
}
GPP_URL = "https://www.globalpetrolprices.com/"

COUNTRY_TO_ISO3 = {
    "Australia": "AUS",
    "Cambodia": "KHM",
    "China": "CHN",
    "Fiji": "FJI",
    "Hong Kong": "HKG",
    "Indonesia": "IDN",
    "Japan": "JPN",
    "Korea, Rep.": "KOR",
    "Lao PDR": "LAO",
    "Malaysia": "MYS",
    "Mongolia": "MNG",
    "Myanmar": "MMR",
    "New Zealand": "NZL",
    "Palau": "PLW",
    "Papua New Guinea": "PNG",
    "Philippines": "PHL",
    "Samoa": "WSM",
    "Singapore": "SGP",
    "Solomon Islands": "SLB",
    "Taiwan": "TWN",
    "Thailand": "THA",
    "Timor-Leste": "TLS",
    "Tonga": "TON",
    "Vanuatu": "VUT",
    "Vietnam": "VNM",
}

_KEY = [*_DATA_COLS_STATIC, "observation_date"]


def _to_litres(chunk: pd.DataFrame) -> pd.DataFrame:
    """Express every price per litre; drop rows with no known conversion."""
    unit = chunk["unit"].astype(str)
    gal = chunk[unit == "gal"].assign(price_local=lambda d: d["price_local"] / GAL_TO_L)
    ton = chunk[unit == "ton"]
    ton = ton.assign(
        price_local=ton["price_local"] / ton["fuel_product"].map(CN_TON_TO_L)
    )
    ton = ton.dropna(subset=["price_local"])
    # price per kg x kg per litre = price per litre.
    lpg = chunk[(unit == "kg") & (chunk["fuel_family"] == "lpg")]
    lpg = lpg.assign(price_local=lpg["price_local"] * LPG_KG_PER_L)
    out = pd.concat([chunk[unit == "L"], gal, ton, lpg], ignore_index=True)
    return out.assign(unit="L")


def _aggregate(legacy_csv: Path) -> tuple[pd.DataFrame, set[tuple[str, str]]]:
    """Stream the legacy CSV into per-day mean prices and the sources used."""
    cols = [
        "observation_date",
        "country",
        "fuel_product",
        "fuel_family",
        "price_local",
        "currency",
        "unit",
        "source_key",
    ]
    parts: list[pd.DataFrame] = []
    sources: set[tuple[str, str]] = set()
    for chunk in pd.read_csv(legacy_csv, usecols=cols, chunksize=500_000):
        sk = chunk["source_key"].astype(str)
        chunk = chunk[
            chunk["country"].isin(COUNTRY_TO_ISO3)
            & ~sk.str.startswith("gpp_")
            & ~sk.isin(EXCLUDED_SOURCES)
        ].dropna(subset=["price_local"])
        if chunk.empty:
            continue
        chunk = _to_litres(chunk)
        if chunk.empty:
            continue
        chunk["iso3"] = chunk["country"].map(COUNTRY_TO_ISO3)
        chunk["units"] = chunk["currency"].astype(str) + "/L"
        chunk["price_note"] = ""  # legacy EAP feeds are all retail
        sources.update(zip(chunk["iso3"], chunk["source_key"].astype(str)))
        parts.append(
            chunk.groupby(_KEY, sort=False)["price_local"].agg(["sum", "count"])
        )
    agg = pd.concat(parts).groupby(level=list(range(len(_KEY)))).sum()
    agg = agg[agg["count"] > 0]
    long = (agg["sum"] / agg["count"]).rename("price_local").reset_index()
    return long, sources


def _data_sheet(long: pd.DataFrame) -> pd.DataFrame:
    wide = long.pivot_table(
        index=_DATA_COLS_STATIC, columns="observation_date", values="price_local"
    ).reset_index()
    wide.columns.name = None
    dates = sorted(c for c in wide.columns if c not in _DATA_COLS_STATIC)
    wide = wide[[*_DATA_COLS_STATIC, *dates]]
    return wide.sort_values(_DATA_COLS_STATIC).reset_index(drop=True)


def _sources_sheet(sources: set[tuple[str, str]], inventory: Path) -> pd.DataFrame:
    inv = pd.read_excel(inventory, sheet_name="sources")
    url_map = dict(zip(inv["source_key"], inv["source_url"]))

    def url(sk: str) -> str:
        found = URL_OVERRIDES.get(sk) or url_map.get(sk, "")
        if isinstance(found, str) and found:
            return found
        return GPP_URL if sk.startswith(("gpp_", "global_")) else ""

    df = pd.DataFrame(sorted(sources), columns=["iso3", "source"])
    # Legacy EAP sources are all pump-price feeds; gpp_* never reach here.
    df = df.assign(url=df["source"].map(url), price_basis="retail")
    return df.sort_values(["iso3", "source"]).reset_index(drop=True)


def _freshness_sheet(long: pd.DataFrame) -> pd.DataFrame:
    """Legacy rows are observations only (no carry-forward): shown == observed."""
    last = long.groupby(["iso3", "fuel_product"], as_index=False)[
        "observation_date"
    ].max()
    last = last.rename(columns={"observation_date": "last_observed"})
    return last.assign(
        last_shown=last["last_observed"], price_basis="retail"
    ).sort_values(["iso3", "fuel_product"])


def export_eap_xlsx(
    legacy_csv: Path = DEFAULT_LEGACY_CSV,
    source_inventory: Path = DEFAULT_SOURCE_INVENTORY,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> Path:
    """Write ``eap_fuel_prices.xlsx`` from the legacy CSV and return its path."""
    long, sources = _aggregate(legacy_csv)
    data = _data_sheet(long)
    sources_df = _sources_sheet(sources, source_inventory)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "eap_fuel_prices.xlsx"
    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        data.to_excel(writer, sheet_name="data", index=False)
        sources_df.to_excel(writer, sheet_name="sources", index=False)
        _freshness_sheet(long).to_excel(writer, sheet_name="freshness", index=False)
    logger.info(
        "Wrote %s (data: %d rows x %d dates, sources: %d rows, %d without url)",
        out_path,
        len(data),
        data.shape[1] - len(_DATA_COLS_STATIC),
        len(sources_df),
        (sources_df["url"] == "").sum(),
    )
    return out_path
