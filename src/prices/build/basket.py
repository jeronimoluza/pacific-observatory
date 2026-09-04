"""Basket selection for `prices build`.

Defines the country and COICOP filters applied to enriched price rows before
they reach aggregation / publication. Country scope is global: BUILD_COUNTRIES
is None, so no country filter is applied. EAP_COUNTRIES survives as the named
region set to scope back down with, not as the live filter.
"""

from __future__ import annotations

import pandas as pd

EAP_COUNTRIES: frozenset[str] = frozenset(
    {
        # east_asia (cache + regions.yaml both forms — cache stores short slugs)
        "china",
        "hong_kong",
        "hong_kong_sar_china",
        "japan",
        "korea_dem_peoples_rep",
        "macao_sar_china",
        "macao",
        "mongolia",
        "south_korea",
        "korea",
        "taiwan",
        "taiwan_china",
        # pacific_islands
        "american_samoa",
        "australia",
        "fiji",
        "french_polynesia",
        "guam",
        "kiribati",
        "marshall_islands",
        "micronesia_fed_sts",
        "nauru",
        "new_caledonia",
        "new_zealand",
        "northern_mariana_islands",
        "palau",
        "papua_new_guinea",
        "samoa",
        "solomon_islands",
        "tonga",
        "tuvalu",
        "vanuatu",
        # southeast_asia
        "brunei",
        "brunei_darussalam",
        "cambodia",
        "indonesia",
        "lao_pdr",
        "laos",
        "malaysia",
        "myanmar",
        "philippines",
        "singapore",
        "thailand",
        "timor_leste",
        "vietnam",
    }
)

FNB_COICOP_PREFIXES: tuple[str, ...] = ("01.", "02.")

# None means every country in the corpus. Set to a frozenset (e.g. EAP_COUNTRIES)
# to scope the build back down to one region.
BUILD_COUNTRIES: frozenset[str] | None = None


def in_scope_countries(countries: pd.Series) -> pd.Series:
    """Boolean mask for the build's country scope; all-True when scope is global."""
    if BUILD_COUNTRIES is None:
        return pd.Series(True, index=countries.index)
    return countries.isin(BUILD_COUNTRIES)


def is_fnb(coicop_code) -> bool:
    if coicop_code is None or pd.isna(coicop_code):
        return False
    return str(coicop_code).startswith(FNB_COICOP_PREFIXES)


def filter_basket(df: pd.DataFrame) -> pd.DataFrame:
    """Apply country-scope × COICOP-01/02 × state==resolved filter."""
    out = df[in_scope_countries(df["country"])]
    out = out[out["coicop_code"].astype(str).str.startswith(FNB_COICOP_PREFIXES)]
    out = out[out["state"] == "resolved"]
    return out.copy()
