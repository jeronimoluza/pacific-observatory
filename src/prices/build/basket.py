"""Basket selection for the EAP F&B PoC dashboard.

Defines the country and COICOP filters applied to enriched price rows
before they reach aggregation / publication. PoC scope is hard-coded;
when the basket widens to all COICOP categories, the COICOP filter
becomes a no-op and EAP_COUNTRIES is replaced with a region-driven set.
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


def is_fnb(coicop_code) -> bool:
    if coicop_code is None or pd.isna(coicop_code):
        return False
    return str(coicop_code).startswith(FNB_COICOP_PREFIXES)


def filter_basket(df: pd.DataFrame) -> pd.DataFrame:
    """Apply EAP × COICOP-01/02 × state==resolved filter."""
    out = df[df["country"].isin(EAP_COUNTRIES)]
    out = out[out["coicop_code"].astype(str).str.startswith(FNB_COICOP_PREFIXES)]
    out = out[out["state"] == "resolved"]
    return out.copy()
