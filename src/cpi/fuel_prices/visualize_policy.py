"""Generate standalone HTML fuel policy overview visualization.

Two tabs:
  Tab 1 — Global Commodity Prices: Brent/WTI/Dubai/RBOB time-series +
           EAP country pricing-regime table.
  Tab 2 — Country Subsidies Comparison: scatter of subsidy per capita
           vs GDP per capita, coloured by pricing regime.
"""

import html as _html
import json
import re
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import requests

from .constants import (
    DASHBOARD_HISTORY_YEARS,
    DATA_DIR,
    IMF_SUBSIDIES_XLSB,
    PALETTE,
    WB_GDP_CSV,
    WB_POPULATION_CSV,
    WB_SUBSIDIES_CSV,
)

_IMF_XLSB_URL = "https://www.imf.org/-/media/files/topics/energysubsidies/imffossilfuelsubsidiesdata.xlsb"
_IMF_XLSB = IMF_SUBSIDIES_XLSB
_CONTROLS_CSV = WB_SUBSIDIES_CSV
_POPULATION_CSV = WB_POPULATION_CSV
_GDP_CSV = WB_GDP_CSV

# ── Per-country product lists for Tab 3 (edit to control which chips appear) ──
COUNTRY_PRODUCTS: dict[str, list[str]] = {
    "Australia": ["Unleaded", "Premium 95", "Premium 98", "E10", "Diesel", "LPG"],
    "Cambodia": ["Regular", "Diesel", "Super"],
    "China": ["Gasoline", "Diesel"],
    "Fiji": [
        "Motor Spirit",
        "Diesel",
        "Kerosene",
        "Premix",
    ],
    "Indonesia": [
        "Pertalite",
        "Pertamax",
        "Pertamax Turbo",
        "Pertamax Green 95",
        "Pertamax di Pertashop",
        "Biosolar",
        "Biosolar Non-Subsidi",
        "Dexlite",
        "Pertamina Dex",
    ],
    "Japan": [
        "Regular Gasoline",
        "High-octane Gasoline",
        "Diesel",
        "Kerosene (retail)",
    ],
    "Korea, Rep.": ["Regular Gasoline", "Diesel", "Kerosene"],
    "Lao PDR": ["Gasoline 95", "Regular Gasoline", "Diesel"],
    "Malaysia": ["RON95", "RON97", "Diesel"],
    "Mongolia": ["Petrol A-92", "Petrol A-80", "Diesel"],
    "Myanmar": ["Octane 92", "Octane 95", "Diesel", "Premium Diesel"],
    "New Zealand": [
        "Regular Petrol",
        "Premium Petrol 95R",
        "Unleaded 91",
        "Unleaded 95",
        "Unleaded 98",
        "Diesel",
    ],
    "Palau": ["Unleaded", "Super", "Diesel", "Kerosene", "LPG"],
    "Papua New Guinea": ["Petrol", "Diesel", "Kerosene"],
    "Philippines": ["RON 91", "RON 95", "RON 100", "Diesel", "Diesel Plus", "Kerosene"],
    "Samoa": ["Petrol", "Diesel", "Kerosene"],
    "Singapore": ["Petrol 92 RON", "Petrol 95 RON", "Petrol 98 RON", "Diesel", "LPG"],
    "Solomon Islands": ["Petrol (PMS)", "Diesel (ADO)", "Propane LPG"],
    "Thailand": [
        "Gasoline 95",
        "Gasohol 91",
        "Gasohol 95",
        "Gasohol E20",
        "Gasohol E85",
        "E20",
        "E85",
        "Super Power GSH95",
        "Diesel",
        "Diesel (HSD)",
        "Diesel (LSD)",
        "Premium Diesel",
        "Hi Diesel S",
        "Hi Premium Diesel S",
        "Hi Premium 97",
        "Kerosene",
        "NGV retail price",
    ],
    "Taiwan": ["Unleaded 92", "Unleaded 95", "Unleaded 98", "Super Diesel"],
    "Timor-Leste": ["Petrol", "Diesel"],
    "Tonga": ["Petrol", "Diesel", "Kerosene"],
    "Vanuatu": ["Unleaded Petrol 95RON", "Low Sulphur Diesel 10PPM"],
    "Vietnam": [
        "E5 RON 92-II",
        "E10 RON 95-III",
        "RON 95-III",
        "RON 95-V",
        "Diesel 0.05S-II",
        "Diesel 0.001S-V",
        "Kerosene 2-K",
        "Mazut 180cst-0.5S",
        "Mazut N02B (3.5S)",
    ],
}

# 5-category composite regime labels (base + subsidy flag)
_REGIME_COLORS = {
    "Market": "#6c757d",
    "Market Prices with Subsidies": "#2196f3",
    "Price Control": "#d62728",
    "Price Control with Subsidies": "#e6ab02",
    "Unknown": "#aec7e8",
}

_PRODUCTS = ["Gasoline", "Diesel", "Kerosene", "LPG", "Natural Gas", "Coal"]
_TABLE_PRODUCTS = ["Gasoline", "Diesel", "LPG", "Kerosene"]

# Unit conversion helpers for commodity chart normalization
_GAL_PER_BBL = 42.0

# Base regime only (Market vs Price Control) — subsidy is tracked separately
_CODE_TO_BASE_REGIME = {
    0: "Market",
    1: "Market",  # deregulated
    2: "Price Control",
    3: "Market",  # pseudo-regulated still market-priced
}

# subsidy_type codes that indicate a subsidy is in place
_SUBSIDY_TYPE_CODES = {3, 4, 5, 6, 7, 9}

# ISO3 codes excluded from subsidy chips in Tab 1 (no data yet)
_SUBSIDY_CHIP_EXCLUDE: set[str] = set()

# Hardcoded product regimes for countries missing from, or intentionally
# overriding, the WB pricing-regime CSV.
_HARDCODED_PRODUCT_REGIMES: dict[str, dict[str, dict]] = {
    "MNG": {
        "Gasoline": {"regime": "Price Control", "subsidy": False},
        "Diesel": {"regime": "Price Control", "subsidy": False},
        "LPG": {"regime": "Price Control", "subsidy": False},
        "Kerosene": {"regime": "Price Control", "subsidy": False},
    },
    "HKG": {
        "Gasoline": {"regime": "Market", "subsidy": False},
        "Diesel": {"regime": "Market", "subsidy": False},
        "LPG": {"regime": "Market", "subsidy": False},
        "Kerosene": {"regime": "Market", "subsidy": False},
    },
    "TWN": {
        "Gasoline": {"regime": "Price Control", "subsidy": False},
        "Diesel": {"regime": "Price Control", "subsidy": False},
        "LPG": {"regime": "Price Control", "subsidy": False},
        "Kerosene": {"regime": "Price Control", "subsidy": False},
    },
}


def _apply_hardcoded_regime_overrides(
    out: pd.DataFrame, product_regimes: dict[str, dict[str, dict]]
) -> tuple[pd.DataFrame, dict[str, dict[str, dict]]]:
    """Apply hardcoded per-product overrides and sync row-level base regime when uniform."""
    for iso3, per_product in _HARDCODED_PRODUCT_REGIMES.items():
        product_regimes[iso3] = per_product

        regime_values = [
            str(info.get("regime"))
            for info in per_product.values()
            if isinstance(info, dict) and info.get("regime")
        ]
        subsidy_values = [
            bool(info.get("subsidy"))
            for info in per_product.values()
            if isinstance(info, dict)
        ]
        if len(set(regime_values)) != 1 or len(set(subsidy_values)) != 1 or out.empty:
            continue

        mask = out["wb_iso3"] == iso3
        if not mask.any():
            continue

        base_regime = regime_values[0]
        subsidy_flag = subsidy_values[0]
        out.loc[mask, "base_regime"] = base_regime
        out.loc[mask, "subsidy_flag"] = subsidy_flag
        out.loc[mask, "regime"] = base_regime + (" + Subsidies" if subsidy_flag else "")

    return out, product_regimes


# Country name normalization for GDP/pop CSV merges
_COUNTRY_NAME_MAP: dict[str, str] = {
    "Viet Nam": "Vietnam",
    "Micronesia, Fed. Sts.": "Micronesia (Federated States of)",
    "Micronesia (Fed. Sts.)": "Micronesia (Federated States of)",
    "Korea, Rep.": "Korea, Rep.",
    "Lao PDR": "Lao PDR",
    "Timor-Leste": "Timor-Leste",
}

_PRODUCT_QUAL_KEYWORDS: dict[str, list[str]] = {
    "Gasoline": [
        "gasoline",
        "petrol",
        "ron",
        "high grade",
        "premium",
        "unleaded",
        "pertalite",
        "pertamax",
        "subsidized fuel",
    ],
    "Diesel": ["diesel", "gas oil"],
    "LPG": ["lpg", "liquefied petroleum"],
    "Kerosene": ["kerosene", "paraffin"],
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _split_not_in_parens(text: str) -> list[str]:
    """Split *text* on commas that are NOT inside parentheses."""
    result: list[str] = []
    depth = 0
    current: list[str] = []
    for ch in text:
        if ch == "(":
            depth += 1
            current.append(ch)
        elif ch == ")":
            depth = max(0, depth - 1)
            current.append(ch)
        elif ch == "," and depth == 0:
            seg = "".join(current).strip()
            if seg:
                result.append(seg)
            current = []
        else:
            current.append(ch)
    seg = "".join(current).strip()
    if seg:
        result.append(seg)
    return result


def _parse_product_qualifier(
    text: str,
    overall_base: str = "Unknown",
    overall_subsidy: bool = False,
) -> dict[str, dict]:
    """Return per-product {regime, subsidy} dicts.

    Only entries with an explicit parenthesised product qualifier are processed;
    plain codes (no qualifier) are ignored.  When no product-qualified entries
    exist, all products return overall_base / overall_subsidy.
    """
    if not text or str(text).lower().strip() in ("nan", "none", ""):
        return {
            p: {"regime": overall_base, "subsidy": overall_subsidy}
            for p in _TABLE_PRODUCTS
        }

    per_product: dict[str, dict] = {}

    for entry in _split_not_in_parens(str(text)):
        m_qual = re.search(r"\(([^)]+)\)", entry)
        if not m_qual:
            continue  # skip entries with no product qualifier
        qualifier = m_qual.group(1).lower()

        m_code = re.search(r"(\d+)", entry)
        if not m_code:
            continue
        code = int(m_code.group(1))
        base = _CODE_TO_BASE_REGIME.get(code, overall_base)
        subsidy = code in _SUBSIDY_TYPE_CODES or overall_subsidy

        matched = [
            p
            for p in _TABLE_PRODUCTS
            if any(kw in qualifier for kw in _PRODUCT_QUAL_KEYWORDS.get(p, []))
        ]
        for p in matched:
            per_product[p] = {"regime": base, "subsidy": subsidy}

    if not per_product:
        # No product-specific qualifiers found — all products mirror the overall
        return {
            p: {"regime": overall_base, "subsidy": overall_subsidy}
            for p in _TABLE_PRODUCTS
        }

    # Products NOT mentioned in any qualifier default to the overall regime
    return {
        p: per_product.get(p, {"regime": overall_base, "subsidy": overall_subsidy})
        for p in _TABLE_PRODUCTS
    }


# ---------------------------------------------------------------------------
# Data loading helpers
# ---------------------------------------------------------------------------


def _load_commodity_data() -> pd.DataFrame:
    """Load commodity data from per-source observations (Global + EAP)."""
    paths = [
        DATA_DIR / "global" / "global_investing_daily" / "observations.csv",
        DATA_DIR / "eap" / "global_investing_daily" / "observations.csv",
    ]
    frames = []
    for p in paths:
        if p.exists():
            frames.append(pd.read_csv(p, low_memory=False))
        else:
            print(f"  [policy] WARNING: {p} not found")
    if not frames:
        return pd.DataFrame()
    df = pd.concat(frames, ignore_index=True)
    df["observation_date"] = pd.to_datetime(df["observation_date"], errors="coerce")
    df = df.dropna(subset=["observation_date", "price_local"])
    df["price_local"] = pd.to_numeric(df["price_local"], errors="coerce")
    df = df.dropna(subset=["price_local"])
    df = df[df["price_local"] > 0]
    return df


def _load_regime_data() -> tuple[pd.DataFrame, dict[str, dict[str, dict]]]:
    """Load subsidies_price_controls_2024.csv and classify pricing regimes.

    Returns
    -------
    df : pd.DataFrame
        Columns: country_name, wb_iso3, region, pricing_mechanism,
                 subsidy_type, base_regime, subsidy_flag, tooltip
    product_regimes : dict[iso3, dict[product, {"regime": str, "subsidy": bool}]]
        Per-product regime+subsidy for each country in *_TABLE_PRODUCTS*.
    """
    if not _CONTROLS_CSV.exists():
        print(f"  [policy] WARNING: {_CONTROLS_CSV} not found")
        return pd.DataFrame(), {}

    df = pd.read_csv(_CONTROLS_CSV, header=[0, 1], low_memory=False)

    economy_col = df.columns[0]
    iso_col = df.columns[1]
    region_col = df.columns[2]
    mech_col = df.columns[3]
    tooltip_col = df.columns[7] if len(df.columns) > 7 else None
    stype_col = df.columns[12] if len(df.columns) > 12 else None

    out = pd.DataFrame()
    out["country_name"] = df[economy_col].astype(str).str.strip()
    out["wb_iso3"] = df[iso_col].astype(str).str.strip()
    out["region"] = df[region_col].astype(str).str.strip()

    # Fix: extract first digit from text like "2 (diesel & LPG)"
    out["pricing_mechanism"] = (
        df[mech_col].astype(str).str.extract(r"(\d)", expand=False).astype(float)
    )
    out["subsidy_type"] = (
        df[stype_col]
        .astype(str)
        .str.extract(r"(\d)", expand=False)
        .astype(float)
        .fillna(0)
        if stype_col is not None
        else pd.Series(0.0, index=out.index)
    )
    out["tooltip"] = (
        df[tooltip_col].astype(str).str.strip()
        if tooltip_col is not None
        else pd.Series("", index=out.index)
    )

    out = out[out["country_name"].notna() & (out["country_name"] != "nan")].copy()

    def classify_base(row: pd.Series) -> str:
        pm = row["pricing_mechanism"]
        return _CODE_TO_BASE_REGIME.get(int(pm) if pd.notna(pm) else -1, "Unknown")

    def classify_subsidy(row: pd.Series) -> bool:
        st = row["subsidy_type"]
        return int(st) in _SUBSIDY_TYPE_CODES if pd.notna(st) else False

    out["base_regime"] = out.apply(classify_base, axis=1)
    out["subsidy_flag"] = out.apply(classify_subsidy, axis=1)
    # Keep a combined "regime" column for backward compat in scatter assembly
    out["regime"] = out.apply(
        lambda r: r["base_regime"] + (" + Subsidies" if r["subsidy_flag"] else ""),
        axis=1,
    )

    # Build per-product {regime, subsidy} dict from raw col-3 and col-12 text
    raw_mech = df[mech_col].astype(str)
    raw_stype = (
        df[stype_col].astype(str)
        if stype_col is not None
        else pd.Series("", index=df.index)
    )

    product_regimes: dict[str, dict[str, dict]] = {}
    for idx in out.index:
        iso3 = out.at[idx, "wb_iso3"]
        base = out.at[idx, "base_regime"]
        sub = bool(out.at[idx, "subsidy_flag"])

        pm_prods = _parse_product_qualifier(raw_mech.at[idx], base, sub)
        # Pass overall_subsidy=False so only explicitly product-qualified codes
        # in col-12 trigger the subsidy flag; unmentioned products fall back to
        # the pm result rather than inheriting the row-level subsidy flag.
        st_prods = _parse_product_qualifier(raw_stype.at[idx], base, False)

        # Merge: subsidy-type overrides pm only when it has an explicit qualifier
        merged: dict[str, dict] = dict(pm_prods)
        for prod, info in st_prods.items():
            if (
                info["subsidy"] != pm_prods[prod]["subsidy"]
                or info["regime"] != pm_prods[prod]["regime"]
            ):
                merged[prod] = info

        product_regimes[iso3] = merged

    out, product_regimes = _apply_hardcoded_regime_overrides(out, product_regimes)
    return out.reset_index(drop=True), product_regimes


def _load_eap_countries() -> pd.DataFrame:
    """Return unique country/wb_iso3 pairs from source_registry.csv.

    Supplements with EAP countries from the regime CSV that have no fuel
    price data (e.g. KIR, MHL, FSM, NRU, PLW, TON, TUV).
    """
    registry_csv = DATA_DIR / "source_registry.csv"
    if registry_csv.exists():
        combined = pd.read_csv(registry_csv, low_memory=False)
        if "country" in combined.columns and "wb_iso3" in combined.columns:
            combined = combined[["country", "wb_iso3"]].drop_duplicates(
                subset=["wb_iso3"]
            )
        else:
            combined = pd.DataFrame(columns=["country", "wb_iso3"])
    else:
        # Fallback: scan per-source observations to build country list
        from .process import load_stored_observations

        all_obs = load_stored_observations(DATA_DIR)
        if (
            not all_obs.empty
            and "country" in all_obs.columns
            and "wb_iso3" in all_obs.columns
        ):
            combined = all_obs[["country", "wb_iso3"]].drop_duplicates(
                subset=["wb_iso3"]
            )
        else:
            combined = pd.DataFrame(columns=["country", "wb_iso3"])

    combined["country"] = combined["country"].replace({"Viet Nam": "Vietnam"})
    combined = combined.drop_duplicates(subset=["wb_iso3"]).reset_index(drop=True)

    # Supplement with EAP rows from regime CSV that are missing from fuel CSVs
    if _CONTROLS_CSV.exists():
        try:
            df_reg = pd.read_csv(_CONTROLS_CSV, header=[0, 1], low_memory=False)
            eco_col = df_reg.columns[1]  # wb_iso3
            name_col = df_reg.columns[0]  # economy name
            reg_col = df_reg.columns[2]  # region
            df_reg_clean = pd.DataFrame(
                {
                    "country": df_reg[name_col].astype(str).str.strip(),
                    "wb_iso3": df_reg[eco_col].astype(str).str.strip(),
                    "region": df_reg[reg_col].astype(str).str.strip(),
                }
            )
            eap_extra = df_reg_clean[
                (df_reg_clean["region"] == "EAP")
                & (~df_reg_clean["wb_iso3"].isin(combined["wb_iso3"]))
            ][["country", "wb_iso3"]].drop_duplicates(subset=["wb_iso3"])
            combined = pd.concat([combined, eap_extra], ignore_index=True)
        except Exception:
            pass

    return combined.reset_index(drop=True)


def _load_imf_subsidies() -> pd.DataFrame:
    """Load IMF Fossil Fuel Subsidies data (``All_Implicit`` sheet).

    Auto-downloads the XLSB if not present.  Returns a wide DataFrame::

        country_name | wb_iso3 | Gasoline | Diesel | Kerosene | LPG |
        Natural Gas  | Coal

    Values are in **billion USD**.  Returns an empty DataFrame on failure.
    """
    if not _IMF_XLSB.exists():
        print("  [policy] Downloading IMF subsidies XLSB ...")
        try:
            resp = requests.get(_IMF_XLSB_URL, timeout=120, stream=True)
            resp.raise_for_status()
            _IMF_XLSB.parent.mkdir(parents=True, exist_ok=True)
            with open(_IMF_XLSB, "wb") as fh:
                for chunk in resp.iter_content(chunk_size=65536):
                    fh.write(chunk)
            print(f"  [policy] Saved {_IMF_XLSB} ({_IMF_XLSB.stat().st_size:,} bytes)")
        except Exception as exc:
            print(f"  [policy] WARNING: Could not download IMF XLSB: {exc}")
            return pd.DataFrame()

    try:
        df = pd.read_excel(_IMF_XLSB, engine="pyxlsb", sheet_name="All_Implicit")
    except Exception as exc:
        print(f"  [policy] WARNING: Could not read IMF XLSB: {exc}")
        return pd.DataFrame()

    if df.empty:
        print("  [policy] WARNING: IMF XLSB All_Implicit sheet is empty")
        return pd.DataFrame()

    # Step 1 — find the label row that contains "Gasoline", "Diesel", etc.
    # (The default header row 0 contains variable codes, not human labels.)
    _DETECT_KWDS = [
        "gasoline",
        "diesel",
        "lpg",
        "kerosene",
        "natural gas",
        "coal",
        "petroleum",
    ]
    label_row_idx: int | None = None
    for i in df.index[:15]:
        vals = [str(v).strip().lower() for v in df.loc[i] if pd.notna(v)]
        if sum(any(kw in v for kw in _DETECT_KWDS) for v in vals) >= 2:
            label_row_idx = i
            break

    if label_row_idx is None:
        print("  [policy] WARNING: No product label row found in IMF XLSB")
        return pd.DataFrame()

    # Step 2 — map code-named columns → canonical product names using the label row
    _PROD_SEARCH: dict[str, list[str]] = {
        "Gasoline": ["gasoline", "petrol"],
        "Diesel": ["diesel"],
        "Kerosene": ["kerosene"],
        "LPG": ["lpg"],
        "Natural Gas": ["natural gas"],
        "Coal": ["coal"],
    }
    col_to_product: dict[str, str] = {}
    for col_name, cell in df.loc[label_row_idx].items():
        cell_lower = str(cell).strip().lower()
        for prod, kws in _PROD_SEARCH.items():
            if any(kw in cell_lower for kw in kws):
                col_to_product[str(col_name)] = prod
                break

    if not col_to_product:
        print("  [policy] WARNING: No product columns identified in IMF XLSB")
        return pd.DataFrame()

    # Step 3 — isolate data rows (skip label row + unit/note rows below it)
    data = df.iloc[label_row_idx + 2 :].dropna(how="all").reset_index(drop=True)

    # Step 4 — detect ISO3 and country columns by data-value patterns
    iso_col = country_col = None
    sample = data.head(50)
    for col in df.columns:
        if str(col) in col_to_product:
            continue
        vals = sample[col].dropna().astype(str).str.strip()
        vals = vals[~vals.str.lower().isin(["nan", "none", "missing", ""])]
        if len(vals) < 3:
            continue
        if iso_col is None and vals.str.match(r"^[a-z]{2,3}$").mean() > 0.6:
            iso_col = col
        elif (
            country_col is None
            and (vals.str.len() > 4).mean() > 0.6
            and vals.str.match(r"^[A-Za-z\s\-,'\.\(\)&]+$").mean() > 0.6
        ):
            country_col = col

    if country_col is None:
        print(
            f"  [policy] WARNING: No country column detected in IMF XLSB. "
            f"Cols: {list(df.columns[:8])}"
        )
        return pd.DataFrame()

    # Step 5 — extract records
    _VALID_COUNTRY_RE = re.compile(r"^[A-Za-z\s\-,'\.\(\)&]{2,60}$")
    records = []
    for _, row in data.iterrows():
        cname = str(row[country_col]).strip() if pd.notna(row[country_col]) else ""
        if not _VALID_COUNTRY_RE.match(cname):
            continue
        iso3 = (
            str(row[iso_col]).strip().upper()
            if iso_col and pd.notna(row.get(iso_col))
            else ""
        )
        rec: dict = {"country_name": cname, "wb_iso3": iso3}
        for col_name, prod in col_to_product.items():
            try:
                rec[prod] = (
                    float(row[col_name]) if pd.notna(row.get(col_name)) else None
                )
            except (ValueError, TypeError):
                rec[prod] = None
        records.append(rec)

    if not records:
        print("  [policy] WARNING: IMF XLSB parsed 0 records")
        return pd.DataFrame()

    df_wide = pd.DataFrame(records)
    for prod in _PRODUCTS:
        if prod not in df_wide.columns:
            df_wide[prod] = None

    n_p = sum(1 for p in _PRODUCTS if df_wide[p].notna().any())
    print(f"  [policy] IMF subsidies: {len(df_wide)} countries, {n_p} products (2024)")
    return df_wide


def _load_population() -> pd.DataFrame:
    if not _POPULATION_CSV.exists():
        print(f"  [policy] WARNING: {_POPULATION_CSV} not found")
        return pd.DataFrame()
    df = pd.read_csv(_POPULATION_CSV, low_memory=False)
    if "country_name" in df.columns:
        df["country_name"] = df["country_name"].replace(_COUNTRY_NAME_MAP)
    return df


def _load_gdp() -> pd.DataFrame:
    if not _GDP_CSV.exists():
        print(
            f"  [policy] WARNING: {_GDP_CSV} not found — run fetchers/imf_weo_gdp.py first"
        )
        return pd.DataFrame()
    df = pd.read_csv(_GDP_CSV, low_memory=False)
    if "country_name" in df.columns:
        df["country_name"] = df["country_name"].replace(_COUNTRY_NAME_MAP)
    return df


# ---------------------------------------------------------------------------
# Main data assembly
# ---------------------------------------------------------------------------


def load_policy_data() -> dict:
    """Load and merge all data sources into a dict ready for the HTML."""
    print("  [policy] Loading commodity data ...")
    df_comm = _load_commodity_data()

    print("  [policy] Loading regime data ...")
    df_regime, product_regimes = _load_regime_data()

    print("  [policy] Loading EAP countries ...")
    df_eap = _load_eap_countries()

    print("  [policy] Loading IMF subsidies ...")
    df_imf = _load_imf_subsidies()

    print("  [policy] Loading population ...")
    df_pop = _load_population()

    print("  [policy] Loading GDP per capita ...")
    df_gdp = _load_gdp()

    # --- Coverage audit (Task 1) ---
    eap_isos = set(df_eap["wb_iso3"].dropna()) if not df_eap.empty else set()
    regime_isos = set(df_regime["wb_iso3"].dropna()) if not df_regime.empty else set()
    imf_isos = set(df_imf["wb_iso3"].dropna()) if not df_imf.empty else set()
    pop_isos = set(df_pop["wb_iso3"].dropna()) if not df_pop.empty else set()
    gdp_isos = set(df_gdp["wb_iso3"].dropna()) if not df_gdp.empty else set()
    print(
        f"  [policy] Coverage — EAP countries: {len(eap_isos)} | "
        f"Regime CSV: {len(regime_isos)} | IMF subsidies: {len(imf_isos)} | "
        f"Population: {len(pop_isos)} | GDP/cap: {len(gdp_isos)}"
    )
    missing_regime = eap_isos - regime_isos
    missing_pop = eap_isos - pop_isos
    missing_gdp = eap_isos - gdp_isos
    if missing_regime:
        print(f"  [policy] EAP missing from regime CSV: {sorted(missing_regime)}")
    if missing_pop:
        print(f"  [policy] EAP missing from population CSV: {sorted(missing_pop)}")
    if missing_gdp:
        print(f"  [policy] EAP missing from GDP CSV: {sorted(missing_gdp)}")
    # Note: Tab 1 subsidy chips are driven by the IMF Fossil Fuel Subsidies
    # workbook (All_Implicit) per-product values: imf_value > 0 => Subsidised.
    # Countries missing from the IMF sheet will simply show no subsidy chips.

    # --- Commodity series for Tab 1 ---
    comm_series: dict = {}
    if not df_comm.empty:
        for prod in df_comm["fuel_product"].dropna().unique():
            rows = df_comm[df_comm["fuel_product"] == prod].sort_values(
                "observation_date"
            )
            unit = rows["unit"].iloc[0] if "unit" in rows.columns else ""
            currency = rows["currency"].iloc[0] if "currency" in rows.columns else ""
            unit_norm = unit
            unit_factor = 1.0
            if unit == "gal":
                unit_norm = "bbl"
                unit_factor = _GAL_PER_BBL
            pts = [
                {
                    "x": r["observation_date"].strftime("%Y-%m-%d"),
                    "y": round(float(r["price_local"]) * unit_factor, 4),
                }
                for _, r in rows.iterrows()
                if pd.notna(r["price_local"])
            ]
            if pts:
                comm_series[prod] = {
                    "points": pts,
                    "unit": unit_norm,
                    "currency": currency,
                }

    # --- EAP country list with regimes (for Tab 1 table) ---
    eap_countries: list[dict] = []
    if not df_eap.empty and not df_regime.empty:
        regime_cols = [
            "wb_iso3",
            "base_regime",
            "subsidy_flag",
            "regime",
            "pricing_mechanism",
            "subsidy_type",
            "tooltip",
        ]
        merged = df_eap.merge(
            df_regime[[c for c in regime_cols if c in df_regime.columns]],
            on="wb_iso3",
            how="left",
        )
        merged["regime"] = merged["regime"].fillna("Unknown")
        merged["base_regime"] = (
            merged["base_regime"].fillna("Unknown")
            if "base_regime" in merged.columns
            else "Unknown"
        )
        merged["subsidy_flag"] = (
            merged["subsidy_flag"]
            .where(merged["subsidy_flag"].notna(), False)
            .astype(bool)
            if "subsidy_flag" in merged.columns
            else False
        )
        merged = merged.drop_duplicates(subset=["country", "wb_iso3"])
        eap_countries = merged.to_dict(orient="records")
    elif not df_eap.empty:
        df_eap_copy = df_eap.copy()
        df_eap_copy["regime"] = "Unknown"
        df_eap_copy["base_regime"] = "Unknown"
        df_eap_copy["subsidy_flag"] = False
        df_eap_copy["tooltip"] = ""
        eap_countries = df_eap_copy.to_dict(orient="records")

    # --- Per-capita subsidies (USD/person) from IMF billion-USD data ---
    # imf_pc_by_iso3: {iso3: {product: float|None}}
    imf_pc_by_iso3: dict[str, dict[str, float | None]] = {}
    # Also store raw IMF values (billion USD) for subsidy flag in JS
    imf_raw_by_iso3: dict[str, dict[str, float | None]] = {}
    if not df_imf.empty:
        df_imf_pop = (
            df_imf.merge(df_pop[["wb_iso3", "population"]], on="wb_iso3", how="left")
            if not df_pop.empty
            else df_imf.assign(population=None)
        )
        for _, row in df_imf_pop.iterrows():
            iso3 = str(row.get("wb_iso3", "")).strip()
            pop = row.get("population")
            pop_ok = pd.notna(pop) and float(pop) > 0
            prods: dict[str, float | None] = {}
            raw_prods: dict[str, float | None] = {}
            for prod in _PRODUCTS:
                val = row.get(prod)
                raw_prods[prod] = float(val) if pd.notna(val) else None
                if pd.notna(val) and pop_ok:
                    prods[prod] = float(val) * 1e9 / float(pop)
                else:
                    prods[prod] = None
            imf_pc_by_iso3[iso3] = prods
            imf_raw_by_iso3[iso3] = raw_prods

    # --- Scatter data for Tab 2 ---
    # Use all countries that have GDP/pop data (not just EAP), per scope notes.
    scatter_points: list[dict] = []
    if not df_gdp.empty:
        # Build a base from all countries with GDP data
        scatter_base = df_gdp[["wb_iso3", "gdp_per_capita"]].copy()
        # Add country name from GDP CSV (country_name col) or fall back to iso3
        if "country_name" in df_gdp.columns:
            scatter_base["country_name"] = df_gdp["country_name"]
        else:
            scatter_base["country_name"] = scatter_base["wb_iso3"]

        if not df_pop.empty:
            scatter_base = scatter_base.merge(
                df_pop[["wb_iso3", "population"]], on="wb_iso3", how="left"
            )
        else:
            scatter_base["population"] = None

        if not df_regime.empty:
            scatter_base = scatter_base.merge(
                df_regime[["wb_iso3", "base_regime", "subsidy_flag", "regime"]],
                on="wb_iso3",
                how="left",
            )
            scatter_base["regime"] = scatter_base["regime"].fillna("Unknown")
            scatter_base["base_regime"] = scatter_base["base_regime"].fillna("Unknown")
            scatter_base["subsidy_flag"] = (
                scatter_base["subsidy_flag"]
                .where(scatter_base["subsidy_flag"].notna(), False)
                .astype(bool)
            )
        else:
            scatter_base["regime"] = "Unknown"
            scatter_base["base_regime"] = "Unknown"
            scatter_base["subsidy_flag"] = False

        for _, row in scatter_base.iterrows():
            iso3 = str(row.get("wb_iso3", ""))
            imf_pc = imf_pc_by_iso3.get(iso3, {p: None for p in _PRODUCTS})
            imf_raw = imf_raw_by_iso3.get(iso3, {p: None for p in _PRODUCTS})
            scatter_points.append(
                {
                    "country": str(row.get("country_name", "")),
                    "wb_iso3": iso3,
                    "base_regime": str(row.get("base_regime", "Unknown")),
                    "regime": str(row.get("regime", "Unknown")),
                    "gdp_per_capita": float(row["gdp_per_capita"])
                    if pd.notna(row.get("gdp_per_capita"))
                    else None,
                    "population": int(row["population"])
                    if pd.notna(row.get("population"))
                    else None,
                    "subsidies": {
                        p: (round(float(v), 4) if v is not None else None)
                        for p, v in imf_pc.items()
                    },
                    # imf_value > 0 per product — used by JS to determine subsidy badge
                    "imf_has_subsidy": {
                        p: (v is not None and v > 0) for p, v in imf_raw.items()
                    },
                }
            )

    # Retain hardcoded per-product overrides even if regime loading changes upstream.
    product_regimes.update(_HARDCODED_PRODUCT_REGIMES)

    return {
        "comm_series": comm_series,
        "eap_countries": eap_countries,
        "scatter": scatter_points,
        "regime_colors": _REGIME_COLORS,
        "product_regimes": product_regimes,
        "products": _PRODUCTS,
        "table_products": _TABLE_PRODUCTS,
        "imf_raw_by_iso3": imf_raw_by_iso3,
    }


# ---------------------------------------------------------------------------
# HTML generation
# ---------------------------------------------------------------------------

_CSS = """
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        padding: 12px 20px;
        background: #fff;
        max-width: 1100px;
    }
    h1 { font-size: 1.15em; font-weight: 700; color: #222; margin-bottom: 12px; }
    .tab-bar {
        display: flex; gap: 0; margin-bottom: 16px;
        border-bottom: 2px solid #e0e0e0;
    }
    .tab-btn {
        padding: 8px 22px; border: none; background: none; cursor: pointer;
        font-size: 0.92em; font-weight: 600; color: #888;
        border-bottom: 3px solid transparent; margin-bottom: -2px;
        transition: all 0.15s;
    }
    .tab-btn.active { color: #667eea; border-bottom-color: #667eea; }
    .tab-btn:hover:not(.active) { color: #444; }
    .tab-pane { display: none; }
    .tab-pane.active { display: block; }
    .ctrl-row {
        display: flex; align-items: center; gap: 8px;
        flex-wrap: wrap; margin-bottom: 8px;
    }
    .row-label {
        font-weight: 600; color: #333; font-size: 0.9em;
        white-space: nowrap; min-width: 80px;
    }
    .chip-container {
        display: flex; flex-wrap: wrap; gap: 5px;
        margin-bottom: 8px; max-height: 100px; overflow-y: auto; padding: 2px 0;
    }
    .chip {
        display: inline-flex; align-items: center; gap: 4px;
        padding: 3px 10px; border: 1px solid #ddd; border-radius: 16px;
        font-size: 0.8em; font-weight: 400; cursor: pointer;
        user-select: none; transition: all 0.15s; white-space: nowrap;
    }
    .chip:hover { border-color: #667eea; background: #f0f4ff; }
    .chip input[type="checkbox"] { display: none; }
    .chip:has(input:checked) { background: #667eea; color: #fff; border-color: #667eea; }
    .section-label {
        font-weight: 600; color: #333; font-size: 0.9em; margin-bottom: 4px; margin-top: 6px;
    }
    .chart-wrapper { position: relative; height: 420px; margin-top: 8px; }
    .slider-row {
        display: flex; align-items: center; gap: 10px; margin-bottom: 10px; overflow: visible;
    }
    .slider-row label { font-weight: 600; color: #333; font-size: 0.95em; white-space: nowrap; }
    #range-label { font-size: 0.85em; color: #555; min-width: 200px; text-align: center; white-space: nowrap; }
    #date-slider { flex: 1; min-width: 200px; }
    .noUi-connect { background: #667eea !important; }
    .noUi-handle { border-color: #667eea !important; box-shadow: none !important; }
    .noUi-tooltip {
        font-size: 0.75em; padding: 2px 6px; background: #667eea;
        color: #fff; border: none; border-radius: 4px;
    }
    /* Regime table */
    .regime-table-wrap { overflow-x: auto; margin-top: 14px; }
    .regime-table {
        border-collapse: collapse; font-size: 0.82em; min-width: 500px; width: 100%;
    }
    .regime-table th, .regime-table td {
        padding: 5px 14px; text-align: left; border-bottom: 1px solid #eee;
    }
    .regime-table th { font-weight: 600; background: #f7f7f7; }
    .regime-table tr:hover td { background: #f8f8ff; }
    .regime-badge {
        display: inline-block; padding: 2px 9px; border-radius: 12px;
        font-size: 0.78em; font-weight: 600; color: #fff; white-space: nowrap;
        cursor: default;
    }
    /* KPI cards */
    .kpi-row { display: flex; gap: 14px; flex-wrap: wrap; margin-bottom: 16px; }
    .kpi-card {
        flex: 1; min-width: 180px; padding: 14px 18px;
        border: 1px solid #e8e8e8; border-radius: 8px; background: #fafafa;
    }
    .kpi-value { font-size: 1.6em; font-weight: 700; color: #222; line-height: 1.1; }
    .kpi-label { font-size: 0.78em; color: #666; margin-top: 3px; }
    /* Scatter */
    .scatter-wrapper { position: relative; height: 480px; margin-top: 8px; }
    .toggle-group {
        display: inline-flex; flex-wrap: wrap;
    }
    .toggle-group label {
        padding: 4px 12px; border: 1px solid #ddd; font-size: 0.82em;
        cursor: pointer; user-select: none; transition: all 0.15s;
        margin-left: -1px; white-space: nowrap;
    }
    .toggle-group label:first-child { margin-left: 0; border-radius: 16px 0 0 16px; }
    .toggle-group label:last-child  { border-radius: 0 16px 16px 0; }
    .toggle-group input[type="radio"] { display: none; }
    .toggle-group label:has(input:checked) {
        background: #667eea; color: #fff; border-color: #667eea; z-index:1; position:relative;
    }
    .toggle-group label:hover:not(:has(input:checked)) { border-color: #667eea; background: #f0f4ff; }
    .legend-row { display: flex; gap: 14px; flex-wrap: wrap; margin: 8px 0; }
    .legend-item { display: flex; align-items: center; gap: 5px; font-size: 0.82em; }
    .legend-dot { width: 12px; height: 12px; border-radius: 50%; flex-shrink: 0; }
    /* Tab 3 — Country Fuel Prices */
    #fuel-country-select {
        padding: 6px 10px; border: 1px solid #ddd; border-radius: 4px;
        font-size: 0.9em; cursor: pointer; background: #fff;
    }
    #fuel-country-select:hover, #fuel-country-select:focus { border-color: #667eea; outline: 0; }
    #fuel-range-label { font-size: 0.85em; color: #555; min-width: 200px; text-align: center; white-space: nowrap; }
    #fuel-date-slider { flex: 0 1 55%; min-width: 140px; max-width: 55%; }
    #fuel-regime-section {
        margin: 8px 0 4px 0;
        padding: 8px 10px;
    }
    #fuel-regime-section .section-label { margin-top: 0; }
    .fuel-regime-grid {
        display: grid;
        grid-template-columns: 140px 1fr 1fr;
        gap: 0;
        align-items: start;
        border: 1px solid #e1e1e1;
        border-radius: 4px;
        overflow: hidden;
    }
    .fuel-regime-grid > div {
        padding: 4px 6px;
        border-top: 1px solid #e1e1e1;
        border-left: 1px solid #e1e1e1;
    }
    .fuel-regime-grid > div:nth-child(-n+3) { border-top: none; }
    .fuel-regime-grid > div:nth-child(3n+1) { border-left: none; }
    .fuel-regime-grid .grid-header {
        font-size: 0.82em;
        font-weight: 700;
        color: #555;
        text-align: left;
    }
    .fuel-regime-grid .row-label {
        font-size: 0.84em;
        font-weight: 600;
        color: #555;
    }
    .fuel-regime-cell {
        min-height: 22px;
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
        align-items: center;
    }
    .fuel-regime-cell .regime-badge {
        font-size: 0.78em;
        padding: 3px 10px;
        font-weight: 600;
    }
    #fuel-meta-panel { font-size: 0.82em; color: #555; margin: 4px 0; line-height: 1.7; }
    /* fuel location table removed (no per-location rendering) */
"""


def gen_policy_html(data: dict, fuel_data: dict, out: Path) -> None:
    """Write the three-tab standalone HTML file."""
    comm_series = data["comm_series"]
    eap_countries = data["eap_countries"]
    scatter = data["scatter"]
    regime_colors = data["regime_colors"]
    product_regimes = data.get("product_regimes", {})
    table_products = data.get("table_products", _TABLE_PRODUCTS)
    products = data.get("products", _PRODUCTS)

    eap_isos = sorted({c.get("wb_iso3", "") for c in eap_countries if c.get("wb_iso3")})
    eap_isos_json = json.dumps(eap_isos)

    imf_raw_by_iso3 = data.get("imf_raw_by_iso3", {})

    _FUEL_KEEP = {
        "observation_date",
        "price_local",
        "location",
        "source_key",
        "fuel_product",
        "series_key",
        "fuel_family",
        "currency",
        "unit",
    }

    def _avg_stations(records: list[dict]) -> list[dict]:
        """Collapse per-station rows into one averaged row per (date, product, source)."""
        from collections import defaultdict

        groups: dict = defaultdict(list)
        first: dict = {}
        for r in records:
            key = (
                r.get("observation_date"),
                r.get("fuel_product"),
                r.get("source_key"),
            )
            groups[key].append(r.get("price_local"))
            if key not in first:
                first[key] = r
        out = []
        for key, prices in groups.items():
            valid = [p for p in prices if p is not None]
            if not valid:
                continue
            rec = dict(first[key])
            rec["price_local"] = round(sum(valid) / len(valid), 4)
            rec["subnational_area"] = ""
            rec["location"] = ""
            out.append(rec)
        return sorted(
            out,
            key=lambda r: (r.get("observation_date", ""), r.get("fuel_product", "")),
        )

    def _collapse_country_records(records: list[dict]) -> list[dict]:
        """Pre-aggregate chart records to keep the standalone HTML lightweight.

        Tab 3 no longer renders per-location tables, so we only need one averaged
        row per (date, product, source) for charting. This avoids embedding a
        huge station-level payload in the HTML.
        """
        from collections import defaultdict

        grouped_prices: dict[tuple, list[float]] = defaultdict(list)
        first_row: dict[tuple, dict] = {}

        for r in records:
            obs_date = str(r.get("observation_date", ""))[:10]
            price = r.get("price_local")
            if not obs_date or price is None:
                continue
            try:
                price_f = float(price)
            except (TypeError, ValueError):
                continue

            key = (
                obs_date,
                r.get("fuel_product"),
                r.get("series_key"),
                r.get("source_key"),
                r.get("fuel_family"),
                r.get("currency"),
                r.get("unit"),
            )
            grouped_prices[key].append(price_f)
            first_row.setdefault(key, r)

        collapsed: list[dict] = []
        for key, prices in grouped_prices.items():
            rec = dict(first_row[key])
            rec["observation_date"] = key[0]
            rec["fuel_product"] = key[1]
            rec["series_key"] = key[2]
            rec["source_key"] = key[3]
            rec["fuel_family"] = key[4]
            rec["currency"] = key[5]
            rec["unit"] = key[6]
            rec["price_local"] = round(sum(prices) / len(prices), 4)
            rec["location"] = "National"
            collapsed.append(rec)

        return sorted(
            collapsed,
            key=lambda r: (
                str(r.get("observation_date", "")),
                str(r.get("fuel_product", "")),
                str(r.get("source_key", "")),
            ),
        )

    # Pre-process per-country before slimming.
    # HK: exclude sparse GPP rows (they introduce a duplicate "Gasoline" chip), then
    #     average the per-station Consumer Council data to one price per day.
    _HK_STABLE_STATIONS = {"PetroChina"}
    _hk_records = _avg_stations(
        [
            r
            for r in fuel_data.get("Hong Kong", [])
            if not r.get("source_key", "").startswith("gpp_")
            and r.get("subnational_area") in _HK_STABLE_STATIONS
        ]
    )
    # Mongolia: mn_data_mn_fuel_ulaanbaatar is stale (max 2025-12-31); switch to the
    #           NSO aimag weekly source which is current and has real price variation.
    _mn_records = [
        r
        for r in fuel_data.get("Mongolia", [])
        if r.get("source_key") == "mn_nso_aimag_weekly_fuel"
    ]
    # Vietnam: keep only vn_petrolimex_retail National rows to avoid zone-mixing spikes.
    #          GPP rows (sparse, different product name) are also excluded.
    _vn_records = [
        r
        for r in fuel_data.get("Vietnam", [])
        if r.get("source_key") == "vn_petrolimex_retail"
        and r.get("location") == "National"
    ]
    # China: NDRC source stores prices in CNY/ton; convert to CNY/L using standard
    # petroleum densities (No.92 gasoline ~0.7254 kg/L, No.0 diesel ~0.835 kg/L).
    _CN_L_PER_TON = {"Gasoline": 1379.0, "Diesel": 1197.6}
    _cn_records = []
    for r in fuel_data.get("China", []):
        if r.get("unit") == "ton" and r.get("fuel_product") in _CN_L_PER_TON:
            rec = dict(r)
            rec["price_local"] = round(
                r["price_local"] / _CN_L_PER_TON[r["fuel_product"]], 4
            )
            rec["unit"] = "L"
            _cn_records.append(rec)
        else:
            _cn_records.append(r)

    # Thailand: exclude NGV source (unit=kg); rename a few Bangchak brand names
    _TH_PRODUCT_MAP = {
        "E20": "Gasohol E20",
        "E85": "Gasohol E85",
        "Hi Diesel S": "Diesel",
    }
    _th_records = []
    for r in fuel_data.get("Thailand", []):
        if r.get("source_key") == "th_eppo_ngv_bangkok_2025":
            continue
        fp = r.get("fuel_product")
        if fp in _TH_PRODUCT_MAP:
            rec = dict(r)
            rec["fuel_product"] = _TH_PRODUCT_MAP[fp]
            _th_records.append(rec)
        else:
            _th_records.append(r)

    _preprocessed = {
        **fuel_data,
        "Hong Kong": _hk_records,
        "Mongolia": _mn_records,
        "Vietnam": _vn_records,
        "China": _cn_records,
        "Thailand": _th_records,
    }

    fuel_data_slim = {
        country: _collapse_country_records(
            [{k: r[k] for k in _FUEL_KEEP if k in r} for r in records]
        )
        for country, records in _preprocessed.items()
    }

    # Normalize Taiwan CPC product names ("92 Unleaded") to MOEA convention ("Unleaded 92")
    _TW_RENAME = {
        "92 Unleaded": "Unleaded 92",
        "95 Unleaded": "Unleaded 95",
        "98 Unleaded": "Unleaded 98",
    }
    for r in fuel_data_slim.get("Taiwan", []):
        fp = r.get("fuel_product")
        if fp in _TW_RENAME:
            r["fuel_product"] = _TW_RENAME[fp]

    # Trim both time-series to the last DASHBOARD_HISTORY_YEARS years.
    # observation_date and comm point x values are already "%Y-%m-%d" strings,
    # so lexicographic comparison works correctly.
    _cutoff = (date.today() - timedelta(days=365 * DASHBOARD_HISTORY_YEARS)).strftime(
        "%Y-%m-%d"
    )
    fuel_data_slim = {
        country: [
            r for r in records if str(r.get("observation_date", ""))[:10] >= _cutoff
        ]
        for country, records in fuel_data_slim.items()
    }
    comm_series = {
        prod: {**series, "points": [p for p in series["points"] if p["x"] >= _cutoff]}
        for prod, series in comm_series.items()
    }

    comm_json = json.dumps(json.dumps(comm_series))
    scatter_json = json.dumps(json.dumps(scatter))
    colors_json = json.dumps(regime_colors)
    palette_json = json.dumps(PALETTE)
    fuel_data_json = json.dumps(json.dumps(fuel_data_slim))
    country_products_json = json.dumps(COUNTRY_PRODUCTS)
    product_regimes_json = json.dumps(product_regimes)
    _HIDDEN_COUNTRIES = {"Palau"}
    fuel_countries = sorted(c for c in fuel_data.keys() if c not in _HIDDEN_COUNTRIES)
    fuel_country_opts = "\n".join(
        f'<option value="{c}">{c}</option>' for c in fuel_countries
    )
    products_json = json.dumps(products)

    # --- Regime table rows ---
    prod_headers = "".join(f"<th>{p}</th>" for p in table_products)
    # Colors for the two base regime chips
    _BASE_COLORS = {
        "Market": regime_colors.get("Market", "#6c757d"),
        "Price Control": regime_colors.get("Price Control", "#d62728"),
        "Unknown": regime_colors.get("Unknown", "#aec7e8"),
    }
    _SUBSIDY_COLOR = "#2196f3"

    regime_rows_html = ""
    for c in sorted(
        eap_countries, key=lambda x: x.get("country", x.get("country_name", ""))
    ):
        name = c.get("country", c.get("country_name", ""))
        iso3 = c.get("wb_iso3", "")
        tip = _html.escape(str(c.get("tooltip", "")), quote=True)
        tooltip_attr = f' title="{tip}"' if tip and tip.lower() != "nan" else ""

        per_prod = product_regimes.get(iso3, {})
        imf_raw_country = imf_raw_by_iso3.get(iso3, {})
        prod_cells = ""
        can_show_subsidy = iso3 not in _SUBSIDY_CHIP_EXCLUDE
        for prod in table_products:
            info = per_prod.get(prod)
            if info is None:
                prod_cells += "<td></td>"
                continue
            base = (
                info.get("regime", "Unknown") if isinstance(info, dict) else str(info)
            )
            if base == "Unknown":
                prod_cells += "<td></td>"
                continue
            # Use IMF raw value as the authoritative subsidy signal
            imf_val = imf_raw_country.get(prod)
            subsidy = (
                (imf_val is not None and imf_val > 0) if can_show_subsidy else False
            )
            bc = _BASE_COLORS.get(base, "#aec7e8")
            base_label = "Price Controlled" if base == "Price Control" else base
            cell_html = f'<span class="regime-badge" style="background:{bc}"{tooltip_attr}>{base_label}</span>'
            if subsidy:
                cell_html += f' <span class="regime-badge" style="background:{_SUBSIDY_COLOR}">Subsidised</span>'
            prod_cells += f"<td>{cell_html}</td>"

        regime_rows_html += f"<tr><td>{name}</td>{prod_cells}</tr>\n"

    # --- Product radio buttons for Tab 2 ---
    product_radios_html = ""
    for i, prod in enumerate(products):
        checked = "checked" if i == 0 else ""
        product_radios_html += (
            f'<label><input type="radio" name="product-toggle" value="{prod}" '
            f'{checked} onchange="renderScatter()">{prod}</label>\n'
        )

    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Fuel Policy Overview — EAP</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns@3.0.0/dist/chartjs-adapter-date-fns.bundle.min.js"></script>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/nouislider@15.7.1/dist/nouislider.min.css">
    <script src="https://cdn.jsdelivr.net/npm/nouislider@15.7.1/dist/nouislider.min.js"></script>
    <style>{_CSS}</style>
</head>
<body>
<h1>Fuel Policy Overview &mdash; East Asia &amp; Pacific</h1>

<div class="tab-bar">
    <button class="tab-btn active" onclick="switchTab('tab1',this)">Commodity Prices</button>
    <button class="tab-btn"       onclick="switchTab('tab2',this)">Country Subsidies</button>
    <button class="tab-btn"       onclick="switchTab('tab3',this)">Country Fuel Prices</button>
</div>

<!-- ===== TAB 1 ===== -->
<div id="tab1" class="tab-pane active">

    <div class="ctrl-row">
        <span class="row-label">Products:</span>
    </div>
    <div class="chip-container" id="comm-chips"></div>

    <div class="slider-row">
        <label>Date Range:</label>
        <span id="range-label">&mdash;</span>
        <div id="date-slider"></div>
    </div>

    <div class="chart-wrapper"><canvas id="comm-chart"></canvas></div>

    <div class="section-label" style="margin-top:18px">EAP Country Pricing Regimes (2024) &mdash; Subsidised = IMF implicit subsidy &gt; 0</div>
    <div class="regime-table-wrap">
        <table class="regime-table">
            <thead>
                <tr>
                    <th>Country</th>
                    {prod_headers}
                </tr>
            </thead>
            <tbody>{regime_rows_html}</tbody>
        </table>
    </div>
</div>

<!-- ===== TAB 2 ===== -->
<div id="tab2" class="tab-pane">

    <div class="kpi-row" id="kpi-row"></div>

    <div class="ctrl-row">
        <span class="row-label">Product:</span>
        <div class="toggle-group">
            {product_radios_html}
        </div>
    </div>

    <p style="font-size:0.85em;color:#555;margin:6px 0 10px 0">
        Subsidies are decomposed into explicit and implicit subsidies. Explicit subsidies occur when the retail price is below a fuel&#39;s supply cost. Implicit subsidies occur when the retail price fails to include external costs, inclusive of the standard consumption tax.
    </p>

    <div class="scatter-wrapper"><canvas id="scatter-chart"></canvas></div>

    <p style="font-size:0.78em;color:#888;margin-top:8px">
        X axis: GDP per capita (USD, log scale, <a href="https://www.imf.org/en/Publications/WEO" target="_blank" style="color:#667eea">IMF WEO 2025</a>) &nbsp;|&nbsp;
        Y axis: subsidy per capita (USD/person, <a href="https://www.imf.org/en/Topics/climate-change/energy-subsidies" target="_blank" style="color:#667eea">IMF Fossil Fuel Subsidies</a>) &nbsp;|&nbsp;
        Hollow markers = no IMF subsidy data available
    </p>
</div>

<!-- ===== TAB 3 ===== -->
<div id="tab3" class="tab-pane">
    <div class="ctrl-row">
        <span class="row-label">Country:</span>
        <select id="fuel-country-select">{fuel_country_opts}</select>
    </div>
    <div class="slider-row">
        <label>Date Range:</label>
        <span id="fuel-range-label">&mdash;</span>
        <div id="fuel-date-slider"></div>
    </div>
    <div id="fuel-regime-section" style="display:none">
        <div class="section-label">Price Regimes:</div>
        <div class="fuel-regime-grid">
            <div></div>
            <div class="grid-header">Subsidised</div>
            <div class="grid-header">Not Subsidised</div>
            <div class="row-label">Market Prices</div>
            <div id="fuel-regime-market-sub" class="fuel-regime-cell"></div>
            <div id="fuel-regime-market-nosub" class="fuel-regime-cell"></div>
            <div class="row-label">Price Controlled</div>
            <div id="fuel-regime-control-sub" class="fuel-regime-cell"></div>
            <div id="fuel-regime-control-nosub" class="fuel-regime-cell"></div>
        </div>
    </div>
    <div class="section-label">Fuel Family:</div>
    <div class="chip-container" id="fuel-axis-chips"></div>
    <div id="fuel-meta-panel"></div>
    <div class="chart-wrapper"><canvas id="fuel-chart"></canvas></div>
    <!-- location price table removed -->
</div>

<script>
// ─── Data ────────────────────────────────────────────────────────────────────
const COMM_SERIES   = JSON.parse({comm_json});
const SCATTER_DATA  = JSON.parse({scatter_json});
const REGIME_COLORS = {colors_json};
const PALETTE       = {palette_json};
const PRODUCT_REGIMES = {product_regimes_json};
const ALL_PRODUCTS  = {products_json};
const EAP_ISOS      = new Set({eap_isos_json});

// ─── Tab switching ────────────────────────────────────────────────────────────
let fuelTabInitialized    = false;
let commTabInitialized    = false;
let scatterTabInitialized = false;
function switchTab(id, btn) {{
    document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.getElementById(id).classList.add('active');
    btn.classList.add('active');
    if (id === 'tab1' && !commTabInitialized) {{
        commTabInitialized = true;
        buildCommChips();
        initCommSlider();
        renderComm();
    }}
    if (id === 'tab2' && !scatterTabInitialized) {{
        scatterTabInitialized = true;
        renderScatter();
    }}
    if (id === 'tab3' && !fuelTabInitialized) {{
        fuelTabInitialized = true;
        rebuildFuelChips();
        initFuelSlider();
        rerenderFuel();
    }}
}}

// ─── Composite regime helper ─────────────────────────────────────────────────
function compositeRegime(d, product) {{
    const base = d.base_regime || 'Unknown';
    const hasSub = d.imf_has_subsidy && d.imf_has_subsidy[product];
    if (base === 'Unknown') return 'Unknown';
    if (!hasSub) return base;
    if (base === 'Market') return 'Market Prices with Subsidies';
    if (base === 'Price Control') return 'Price Control with Subsidies';
    return base + ' + Subsidies';
}}

// ─── KPI cards ───────────────────────────────────────────────────────────────
function buildKPI(product, selectedCountry) {{
    const row = document.getElementById('kpi-row');
    row.innerHTML = '';

    // Filter to EAP countries only for KPI stats
    const eapData = SCATTER_DATA.filter(d => EAP_ISOS.has(d.wb_iso3));
    const withData = eapData.filter(d =>
        d.subsidies && d.subsidies[product] != null && d.subsidies[product] > 0
    );

    let topCountry = 'N/A', topVal = 0;
    if (withData.length > 0) {{
        const top = withData.reduce((a, b) => b.subsidies[product] > a.subsidies[product] ? b : a);
        topCountry = top.country;
        topVal = top.subsidies[product];
    }}

    const count = withData.length;
    const avg   = count > 0
        ? withData.reduce((s, d) => s + d.subsidies[product], 0) / count
        : 0;

    // Regime badge for selected/first EAP country
    let badgeCountry = selectedCountry || (eapData.length ? eapData[0].country : null);
    let badgeRegime = 'Unknown';
    if (badgeCountry) {{
        const found = SCATTER_DATA.find(d => d.country === badgeCountry);
        if (found) badgeRegime = compositeRegime(found, product);
    }}
    const badgeColor = REGIME_COLORS[badgeRegime] || '#aec7e8';

    const cards = [
        {{
            value: topCountry !== 'N/A' ? topCountry + ' \u2014 $' + topVal.toFixed(1) : 'N/A',
            label: 'Highest ' + product + ' subsidy per capita in EAP (USD/person)'
        }},
        {{
            value: count,
            label: 'EAP countries with ' + product + ' subsidy'
        }},
        {{
            value: avg > 0 ? '$' + avg.toFixed(1) : 'N/A',
            label: 'Average ' + product + ' subsidy per capita in EAP (USD/person)'
        }},
    ];
    cards.forEach(c => {{
        const div = document.createElement('div');
        div.className = 'kpi-card';
        div.innerHTML = '<div class="kpi-value">' + c.value + '</div>'
                      + '<div class="kpi-label">' + c.label + '</div>';
        row.appendChild(div);
    }});

}}

// ─── Commodity chart helpers ──────────────────────────────────────────────────
let sliderDates = [];
let commSlider  = null;
let commChart   = null;

function formatDate(d) {{
    const dt = new Date(d);
    return dt.getFullYear() + '-' + String(dt.getMonth()+1).padStart(2,'0') + '-' + String(dt.getDate()).padStart(2,'0');
}}

function buildCommChips() {{
    const c = document.getElementById('comm-chips');
    c.innerHTML = '';
    Object.keys(COMM_SERIES).sort().forEach((key) => {{
        const lel = document.createElement('label');
        lel.className = 'chip';
        const cb = document.createElement('input');
        cb.type = 'checkbox'; cb.value = key; cb.checked = true;
        cb.addEventListener('change', renderComm);
        lel.appendChild(cb);
        lel.appendChild(document.createTextNode(key));
        c.appendChild(lel);
    }});
}}

function initCommSlider() {{
    const allDates = new Set();
    Object.values(COMM_SERIES).forEach(s => s.points.forEach(p => allDates.add(p.x)));
    sliderDates = Array.from(allDates).sort();
    if (!sliderDates.length) return;

    const maxIdx = sliderDates.length - 1;
    const lastDate = new Date(sliderDates[maxIdx]);
    const oneYearBeforeLast = new Date(lastDate);
    oneYearBeforeLast.setFullYear(oneYearBeforeLast.getFullYear() - 1);
    const defaultStart = sliderDates.findIndex(d => new Date(d) >= oneYearBeforeLast);
    const startIdx = defaultStart >= 0 ? defaultStart : 0;

    const el = document.getElementById('date-slider');
    if (commSlider) commSlider.destroy();
    commSlider = noUiSlider.create(el, {{
        start: [startIdx, maxIdx],
        connect: true,
        step: 1,
        range: {{ min: 0, max: maxIdx || 1 }},
        tooltips: [
            {{ to: v => formatDate(sliderDates[Math.round(v)]) }},
            {{ to: v => formatDate(sliderDates[Math.round(v)]) }}
        ]
    }});
    const rangeLabel = document.getElementById('range-label');
    function updateLabel() {{
        const [a, b] = commSlider.get().map(v => Math.round(v));
        rangeLabel.textContent = formatDate(sliderDates[a]) + '  \u2192  ' + formatDate(sliderDates[b]);
    }}
    updateLabel();
    commSlider.on('update', updateLabel);
    commSlider.on('change', renderComm);
}}

function getSliderRange() {{
    if (!commSlider || !sliderDates.length) return {{ from: '', to: '' }};
    const [a, b] = commSlider.get().map(v => Math.round(v));
    return {{ from: sliderDates[a], to: sliderDates[b] }};
}}

function getChecked(containerId) {{
    return Array.from(document.querySelectorAll('#' + containerId + ' input:checked')).map(e => e.value);
}}

function renderComm() {{
    const selected = getChecked('comm-chips');
    const range    = getSliderRange();
    const ctx = document.getElementById('comm-chart').getContext('2d');

    const datasets = [];
    let colorIdx = 0;

    selected.forEach(key => {{
        const series = COMM_SERIES[key];
        if (!series) return;
        let pts = series.points;
        if (range.from) pts = pts.filter(p => p.x >= range.from);
        if (range.to)   pts = pts.filter(p => p.x <= range.to);
        datasets.push({{
            label: key,
            data: pts,
            borderColor: PALETTE[colorIdx % PALETTE.length],
            backgroundColor: PALETTE[colorIdx % PALETTE.length],
            borderWidth: 1.8,
            fill: false,
            tension: 0.1,
            pointRadius: 0,
            pointHoverRadius: 4,
            spanGaps: false,
        }});
        colorIdx++;
    }});

    const firstSeries = selected.length ? COMM_SERIES[selected[0]] : null;
    const yLabel = firstSeries ? (firstSeries.currency + '/' + firstSeries.unit) : '';

    if (!commChart) {{
        commChart = new Chart(ctx, {{
            type: 'line',
            data: {{ datasets }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{ position: 'top', labels: {{ usePointStyle: true, padding: 14, font: {{ size: 11 }} }} }},
                    tooltip: {{
                        mode: 'index', intersect: false,
                        backgroundColor: 'rgba(0,0,0,0.82)', padding: 12,
                        callbacks: {{
                            title: items => items.length ? items[0].raw.x : '',
                            label: item => {{
                                const v = item.raw ? item.raw.y : null;
                                return v == null ? null : item.dataset.label + ': ' + v.toFixed(2);
                            }}
                        }}
                    }}
                }},
                scales: {{
                    x: {{ type: 'time', time: {{ unit: 'month' }}, display: true, title: {{ display: true, text: 'Date' }} }},
                    y: {{ display: true, title: {{ display: true, text: yLabel }} }}
                }}
            }}
        }});
    }} else {{
        commChart.data.datasets = datasets;
        commChart.options.scales.y.title.text = yLabel;
        commChart.update('none');
    }}
}}

// ─── Scatter chart ────────────────────────────────────────────────────────────
let scatterChart = null;
let _scatterProduct = '';

function renderScatter() {{
    const productEl = document.querySelector('input[name="product-toggle"]:checked');
    const product   = productEl ? productEl.value : ALL_PRODUCTS[0];

    buildKPI(product);

    const regimes = Object.keys(REGIME_COLORS);
    const datasets = [];

    const eapScatter = SCATTER_DATA.filter(d => EAP_ISOS.has(d.wb_iso3));

    // Subsidised regimes: solid dots at actual subsidy y value
    regimes.forEach(regime => {{
        const rPts = eapScatter.filter(d =>
            compositeRegime(d, product) === regime &&
            d.gdp_per_capita != null &&
            d.subsidies && d.subsidies[product] != null && d.subsidies[product] > 0
        );
        if (!rPts.length) return;
        datasets.push({{
            label: regime,
            data: rPts.map(d => ({{
                x: d.gdp_per_capita,
                y: d.subsidies[product],
                _meta: d,
            }})),
            backgroundColor: REGIME_COLORS[regime] + 'cc',
            borderColor:     REGIME_COLORS[regime],
            borderWidth: 1.5,
            pointRadius: 10,
            pointHoverRadius: 13,
        }});
    }});

    // Unknown regime / no subsidy data
    const noDataPts = eapScatter.filter(d =>
        d.gdp_per_capita != null &&
        compositeRegime(d, product) === 'Unknown'
    );
    if (noDataPts.length) {{
        datasets.push({{
            label: 'No subsidy data',
            data: noDataPts.map(d => ({{ x: d.gdp_per_capita, y: 1, _meta: d }})),
            backgroundColor: 'transparent',
            borderColor: '#999',
            borderWidth: 1.5,
            pointRadius: 10,
            pointHoverRadius: 13,
            pointStyle: 'circle',
        }});
    }}

    // Compute y-axis bounds with padding in log space
    const allY = datasets.flatMap(ds => ds.data.map(p => p.y)).filter(v => v != null && v > 0);
    const yLogPad = 0.4; // log10 decades of padding
    const yMin = allY.length ? Math.pow(10, Math.log10(Math.min(...allY)) - yLogPad) : 0.5;
    const yMax = allY.length ? Math.pow(10, Math.log10(Math.max(...allY)) + yLogPad) : 1e5;

    _scatterProduct = product;
    const ctx = document.getElementById('scatter-chart').getContext('2d');
    if (!scatterChart) {{
        scatterChart = new Chart(ctx, {{
            type: 'scatter',
            data: {{ datasets }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{ position: 'top', labels: {{ usePointStyle: true, padding: 12, font: {{ size: 11 }} }} }},
                    tooltip: {{
                        callbacks: {{
                            label: item => {{
                                const m = item.raw._meta;
                                const regime = compositeRegime(m, _scatterProduct);
                                const hasSubsidy = m.subsidies && m.subsidies[_scatterProduct] != null && m.subsidies[_scatterProduct] > 0;
                                let sub;
                                if (hasSubsidy) {{
                                    sub = '$' + m.subsidies[_scatterProduct].toFixed(2);
                                }} else if (regime === 'Market' || regime === 'Price Control') {{
                                    sub = 'no subsidies';
                                }} else {{
                                    sub = 'no data';
                                }}
                                const gdp = m.gdp_per_capita != null
                                    ? '$' + Math.round(m.gdp_per_capita).toLocaleString()
                                    : 'N/A';
                                return [
                                    m.country + ' (' + m.wb_iso3 + ')',
                                    _scatterProduct + ' subsidy per capita: ' + sub,
                                    'GDP per capita: ' + gdp,
                                ];
                            }}
                        }}
                    }},
                }},
                scales: {{
                    x: {{
                        type: 'logarithmic',
                        display: true,
                        title: {{ display: true, text: 'GDP per capita (USD, log scale)' }},
                        ticks: {{
                            callback: function(value) {{
                                const log = Math.log10(value);
                                if (Math.abs(log - Math.round(log)) < 0.01) {{
                                    const exp = Math.round(log);
                                    const sups = '\u2070\u00b9\u00b2\u00b3\u2074\u2075\u2076\u2077\u2078\u2079';
                                    const supStr = String(exp).split('').map(c => sups[+c]).join('');
                                    return '10' + supStr;
                                }}
                                return null;
                            }}
                        }}
                    }},
                    y: {{
                        type: 'logarithmic',
                        display: true,
                        min: yMin,
                        max: yMax,
                        title: {{ display: true, text: _scatterProduct + ' subsidy per capita (USD/person, log scale)' }},
                        ticks: {{
                            callback: function(value) {{
                                const log = Math.log10(value);
                                if (Math.abs(log - Math.round(log)) < 0.01) {{
                                    const exp = Math.round(log);
                                    const sups = '\u2070\u00b9\u00b2\u00b3\u2074\u2075\u2076\u2077\u2078\u2079';
                                    const supStr = String(exp).split('').map(c => sups[+c]).join('');
                                    return '10' + supStr;
                                }}
                                return null;
                            }}
                        }}
                    }}
                }}
            }},
            plugins: [{{
                id: 'iso3labels',
                afterDatasetsDraw(chart) {{
                    const ctx = chart.ctx;
                    chart.data.datasets.forEach((ds, di) => {{
                        const meta = chart.getDatasetMeta(di);
                        meta.data.forEach((pt, pi) => {{
                            const m = ds.data[pi]._meta;
                            if (!m || !EAP_ISOS.has(m.wb_iso3)) return;
                            ctx.save();
                            ctx.font = 'bold 11px sans-serif';
                            ctx.fillStyle = '#333';
                            ctx.textAlign = 'center';
                            ctx.fillText(m.wb_iso3, pt.x, pt.y - 14);
                            ctx.restore();
                        }});
                    }});
                }}
            }}]
        }});
    }} else {{
        scatterChart.data.datasets = datasets;
        scatterChart.options.scales.y.min = yMin;
        scatterChart.options.scales.y.max = yMax;
        scatterChart.options.scales.y.title.text = _scatterProduct + ' subsidy per capita (USD/person, log scale)';
        scatterChart.update('none');
    }}
}}

// ─── Tab 3: Country Fuel Prices ───────────────────────────────────────────────
const FUEL_DATA = JSON.parse({fuel_data_json});
const COUNTRY_PRODUCTS = {country_products_json};

const LABELS = {{
    diesel: "Diesel", gasoline: "Gasoline", lpg: "LPG",
    kerosene: "Kerosene", fuel_oil: "Fuel Oil",
    natural_gas: "Natural Gas", town_gas: "Town Gas",
    premium: "Premium", regular: "Regular",
    premix: "Premix", super_premium: "Super Premium",
    octane_95: "Premium",
}};

function lbl(v) {{ return (v && LABELS[v]) ? LABELS[v] : (v || "\u2014"); }}

function chipKey(r){{
    return r.fuel_product || r.series_key || "unknown";
}}

function chipLabel(key) {{
    return key || "\u2014";
}}

function getCheckedValues(containerId) {{
    return Array.from(
        document.querySelectorAll("#" + containerId + " input:checked")
    ).map(function(cb) {{ return cb.value; }});
}}

function buildNationalAvg(locSeries) {{
    var byDate = {{}};
    Object.keys(locSeries).forEach(function(loc) {{
        locSeries[loc].forEach(function(pt) {{
            if (pt.y == null) return;
            if (!byDate[pt.x]) byDate[pt.x] = {{ sum: 0, count: 0 }};
            byDate[pt.x].sum   += pt.y;
            byDate[pt.x].count += 1;
        }});
    }});
    return Object.keys(byDate).sort().map(function(d) {{
        return {{ x: d, y: byDate[d].sum / byDate[d].count }};
    }});
}}

function formatYM(d) {{
    const dt = new Date(d);
    return dt.getFullYear() + '-' + String(dt.getMonth() + 1).padStart(2, '0') + '-' + String(dt.getDate()).padStart(2, '0');
}}

let fuelSliderDates = [];
let fuelSlider = null;

function getFuelSliderRange() {{
    if (!fuelSlider || !fuelSliderDates.length) return {{ from: '', to: '' }};
    const vals = fuelSlider.get().map(v => Math.round(v));
    return {{ from: fuelSliderDates[vals[0]], to: fuelSliderDates[vals[1]] }};
}}

function initFuelSlider() {{
    var rows = getFuelCountryRows();
    if (!rows || !rows.length) return;
    var dateSet = {{}};
    rows.forEach(function(r) {{ dateSet[r.observation_date] = true; }});
    fuelSliderDates = Object.keys(dateSet).sort();
    const maxIdx = fuelSliderDates.length - 1;
    if (maxIdx < 0) return;

    const lastFuelDate = new Date(fuelSliderDates[maxIdx]);
    const oneYearBeforeFuel = new Date(lastFuelDate);
    oneYearBeforeFuel.setFullYear(oneYearBeforeFuel.getFullYear() - 1);
    const defaultFuelStart = fuelSliderDates.findIndex(d => new Date(d) >= oneYearBeforeFuel);
    const startIdx = defaultFuelStart >= 0 ? defaultFuelStart : 0;

    const el = document.getElementById('fuel-date-slider');
    if (fuelSlider) {{ fuelSlider.destroy(); }}
    fuelSlider = noUiSlider.create(el, {{
        start: [startIdx, maxIdx],
        connect: true,
        step: 1,
        range: {{ min: 0, max: maxIdx || 1 }},
        tooltips: [
            {{ to: v => formatYM(fuelSliderDates[Math.round(v)]) }},
            {{ to: v => formatYM(fuelSliderDates[Math.round(v)]) }}
        ]
    }});
    const rangeLabel = document.getElementById('fuel-range-label');
    function updateFuelLabel() {{
        const vals = fuelSlider.get().map(v => Math.round(v));
        rangeLabel.textContent = formatYM(fuelSliderDates[vals[0]]) + '  \u2192  ' + formatYM(fuelSliderDates[vals[1]]);
    }}
    updateFuelLabel();
    fuelSlider.on('update', function() {{ updateFuelLabel(); }});
    fuelSlider.on('change', function() {{ rerenderFuel(); }});
}}

function buildFuelChips(containerId, keys, rows) {{
    var c = document.getElementById(containerId);
    c.innerHTML = "";
    keys.forEach(function(key) {{
        var lel = document.createElement("label");
        lel.className = "chip";
        var cb = document.createElement("input");
        cb.type = "checkbox"; cb.value = key; cb.checked = true;
        cb.addEventListener("change", rerenderFuel);
        lel.appendChild(cb);
        lel.appendChild(document.createTextNode(chipLabel(key)));
        c.appendChild(lel);
    }});
}}

var fuelLocDataStore = {{}};

function buildFuelLocTable(key) {{
    var wrap = document.getElementById("fuel-loc-table-wrap");
    if (!key || !fuelLocDataStore[key]) {{ wrap.innerHTML = ""; return; }}
    var locMap  = fuelLocDataStore[key];
    var locs    = Object.keys(locMap);
    var entries = locs.map(function(loc) {{
        var pts  = locMap[loc];
        var last = pts.length ? pts[pts.length - 1] : null;
        return {{ loc: loc, val: last ? last.y : null }};
    }});
    var avgPts  = buildNationalAvg(locMap);
    var lastAvg = avgPts.length ? avgPts[avgPts.length - 1] : null;
    entries.push({{ loc: "National Average", val: lastAvg ? lastAvg.y : null, isAvg: true }});
    entries.sort(function(a, b) {{
        if (a.val == null && b.val == null) return 0;
        if (a.val == null) return 1;
        if (b.val == null) return -1;
        return b.val - a.val;
    }});
    var allRows = window._fuelCountryRows || [];
    var keyRows = allRows.filter(function(r) {{ return chipKey(r) === key; }});
    var cu  = keyRows.length ? ((keyRows[0].currency || "") + "/" + (keyRows[0].unit || "")) : "";
    var tbl = "<table id='fuel-loc-table'><thead><tr>"
            + "<th>Location</th><th>Price (" + cu + ")</th>"
            + "</tr></thead><tbody>";
    entries.forEach(function(e) {{
        var cls = e.isAvg ? " class='nat-avg-row'" : "";
        var val = e.val != null ? e.val.toFixed(2) : "\u2014";
        tbl += "<tr" + cls + "><td>" + e.loc + "</td><td>" + val + "</td></tr>";
    }});
    tbl += "</tbody></table>";
    wrap.innerHTML = tbl;
}}

function rebuildFuelLocToggles(multiKeys) {{
    var sec  = document.getElementById("fuel-loc-table-section");
    var togs = document.getElementById("fuel-loc-table-toggles");
    togs.innerHTML = "";
    if (!multiKeys.length) {{ sec.style.display = "none"; return; }}
    sec.style.display = "";
    var allRows  = window._fuelCountryRows || [];
    var visRows  = allRows.filter(function(r) {{ return multiKeys.includes(chipKey(r)); }});
    var lastDate = visRows.reduce(function(m, r) {{ return r.observation_date > m ? r.observation_date : m; }}, "");
    var secLabel = sec.querySelector(".section-label");
    if (secLabel) secLabel.textContent = lastDate ? "Location Prices for " + lastDate : "Location Prices:";
    multiKeys.forEach(function(key, idx) {{
        var lel = document.createElement("label");
        var rb  = document.createElement("input");
        rb.type = "radio"; rb.name = "fuel-loc-tab"; rb.value = key;
        if (idx === 0) rb.checked = true;
        rb.addEventListener("change", function() {{ buildFuelLocTable(rb.value); }});
        lel.appendChild(rb);
        lel.appendChild(document.createTextNode(chipLabel(key)));
        togs.appendChild(lel);
    }});
    buildFuelLocTable(multiKeys[0]);
}}

function makeFuelDataset(label, points, color, isGray) {{
    var pts = points;
    return {{
        label:            label,
        data:             pts,
        borderColor:      isGray ? "#e8e8e8" : color,
        backgroundColor:  isGray ? "#e8e8e8" : color,
        borderWidth:      isGray ? 1 : 1.8,
        fill:             false,
        tension:          0.1,
        pointRadius:      0,
        pointHoverRadius: isGray ? 3 : 5,
        spanGaps:         false,
        order:            isGray ? 2 : 1,
        _isGray:          isGray,
    }};
}}

function updateFuelMeta(rows) {{
    var panel = document.getElementById("fuel-meta-panel");
    if (!rows || !rows.length) {{ panel.innerHTML = ""; return; }}
    var dates = rows.map(function(r) {{ return r.observation_date; }}).sort();
    panel.innerHTML = "<strong>Date Range:</strong> " + dates[0] + " \u2013 " + dates[dates.length - 1];
}}

function computeFuelYScale(datasets, yLabel) {{
    var allY = [];
    datasets.forEach(function(ds) {{
        (ds.data || []).forEach(function(pt) {{
            if (pt && pt.y != null && !ds._isGray) allY.push(pt.y);
        }});
    }});
    if (!allY.length) return {{ display: true, title: {{ display: true, text: yLabel }} }};
    var yMin = Math.min.apply(null, allY);
    var yMax = Math.max.apply(null, allY);
    var pad = (yMax - yMin) * 0.05 || yMax * 0.05 || 1;
    return {{
        display: true,
        title: {{ display: true, text: yLabel }},
        min: Math.max(0, yMin - pad),
        max: yMax + pad
    }};
}}

function drawFuelChart(datasets, yLabel) {{
    var ctx = document.getElementById("fuel-chart").getContext("2d");
    if (!datasets.length) {{
        if (window.fuelChart) {{ window.fuelChart.destroy(); window.fuelChart = null; }}
        return;
    }}
    var yScale = computeFuelYScale(datasets, yLabel);
    if (!window.fuelChart) {{
        window.fuelChart = new Chart(ctx, {{
            type: "line",
            data: {{ datasets: datasets }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{
                        position: "top",
                        labels: {{
                            usePointStyle: true, padding: 14, font: {{ size: 11 }},
                            filter: function(item, data) {{ return !data.datasets[item.datasetIndex]._isGray; }}
                        }}
                    }},
                    tooltip: {{
                        mode: "index", intersect: false,
                        backgroundColor: "rgba(0,0,0,0.82)", padding: 12,
                        filter: function(item) {{ return !item.dataset._isGray; }},
                        callbacks: {{
                            title: function(items) {{ return items.length ? items[0].raw.x : ""; }},
                            label: function(item) {{
                                var val = item.raw ? item.raw.y : null;
                                if (val == null) return null;
                                return item.dataset.label + ": " + val.toFixed(2);
                            }}
                        }}
                    }}
                }},
                scales: {{
                    x: {{ type: "time", time: {{ unit: "month", tooltipFormat: "yyyy-MM-dd" }},
                          display: true, title: {{ display: true, text: "Date" }} }},
                    y: yScale
                }}
            }}
        }});
    }} else {{
        window.fuelChart.data.datasets = datasets;
        window.fuelChart.options.scales.y = yScale;
        window.fuelChart.update('none');
    }}
}}

function getFuelCountryRows() {{
    var country = document.getElementById("fuel-country-select").value;
    var rows = FUEL_DATA[country] || [];
    var allowed = COUNTRY_PRODUCTS[country];
    if (allowed) {{
        rows = rows.filter(function(r) {{ return allowed.includes(r.fuel_product); }});
    }}
    return rows;
}}

function rebuildFuelChips() {{
    var rows = getFuelCountryRows();
    var keys = [...new Set(rows.map(chipKey))].sort();
    buildFuelChips("fuel-axis-chips", keys, rows);
}}

function rerenderFuel() {{
    var rows         = getFuelCountryRows();
    window._fuelCountryRows = rows;
    var selectedKeys = getCheckedValues("fuel-axis-chips");
    var visibleRows  = rows.filter(function(r) {{ return selectedKeys.includes(chipKey(r)); }});
    var range = getFuelSliderRange();
    if (range.from) visibleRows = visibleRows.filter(function(r) {{ return r.observation_date >= range.from; }});
    if (range.to)   visibleRows = visibleRows.filter(function(r) {{ return r.observation_date <= range.to; }});
    updateFuelMeta(visibleRows);
    if (!visibleRows.length) {{
        drawFuelChart([], "");
        var locSection = document.getElementById('fuel-loc-table-section');
        if (locSection) locSection.style.display = 'none';
        var section = document.getElementById('fuel-regime-section');
        if (section) section.style.display = 'none';
        return;
    }}
    var firstRow  = visibleRows[0];
    var yLabel    = (firstRow.currency || "") + " / " + (firstRow.unit || "");
    var datasets  = [];
    var colorIdx  = 0;
    var keyColors = {{}};
    selectedKeys.forEach(function(key) {{
        var keyRows = visibleRows.filter(function(r) {{ return chipKey(r) === key; }});
        if (!keyRows.length) return;
        var color  = PALETTE[colorIdx % PALETTE.length];
        var serLbl = chipLabel(key);
        colorIdx++;
        keyColors[key] = color;
        // Per-date source-weighted location resolution
        var byDate = {{}};
        keyRows.forEach(function(r) {{
            var d = r.observation_date;
            if (!d || r.price_local == null) return;
            var loc = (r.location || "").toLowerCase();
            var isNat = loc === "national" || loc === "national average";
            var sk = r.source_key || "_unknown";
            if (!byDate[d]) byDate[d] = {{}};
            if (!byDate[d][sk]) byDate[d][sk] = {{ nat: [], sub: [] }};
            if (isNat) byDate[d][sk].nat.push(r.price_local);
            else byDate[d][sk].sub.push(r.price_local);
        }});
        var avgPts = Object.keys(byDate).sort().map(function(d) {{
            var sources = byDate[d];
            var sourceAvgs = [];
            Object.keys(sources).forEach(function(sk) {{
                var s = sources[sk];
                var prices = s.sub.length ? s.sub : s.nat;
                if (!prices.length) return;
                var sum = prices.reduce(function(a, v) {{ return a + v; }}, 0);
                sourceAvgs.push(sum / prices.length);
            }});
            if (!sourceAvgs.length) return {{ x: d, y: null }};
            var total = sourceAvgs.reduce(function(a, v) {{ return a + v; }}, 0);
            return {{ x: d, y: total / sourceAvgs.length }};
        }});
        datasets.push(makeFuelDataset(serLbl, avgPts, color, false));
    }});
    drawFuelChart(datasets, yLabel);
    var locSection = document.getElementById('fuel-loc-table-section');
    if (locSection) locSection.style.display = 'none';
    updateFuelRegimeSection(document.getElementById("fuel-country-select").value, selectedKeys, keyColors);
}}

// ─── Tab 3 price regime section ─────────────────────────────────────────────────
function fuelBaseProduct(row) {{
    const family = row && row.fuel_family;
    const f = String(family || '').toLowerCase();
    if (f === 'gasoline') return 'Gasoline';
    if (f === 'diesel') return 'Diesel';
    if (f === 'lpg') return 'LPG';
    if (f === 'kerosene') return 'Kerosene';

    const product = String((row && row.fuel_product) || '').toLowerCase();
    if (!product) return null;
    if (product.includes('diesel') || product.includes('gas oil')) return 'Diesel';
    if (product.includes('kerosene') || product.includes('paraffin')) return 'Kerosene';
    if (product.includes('lpg') || product.includes('liquefied petroleum')) return 'LPG';
    if (
        product.includes('gasoline')
        || product.includes('petrol')
        || product.includes('ron')
        || product.includes('unleaded')
        || product.includes('pertalite')
        || product.includes('pertamax')
        || product.includes('motor spirit')
    ) return 'Gasoline';
    return null;
}}

function updateFuelRegimeSection(countryName, selectedKeys, keyColors) {{
    const section = document.getElementById('fuel-regime-section');
    const marketSub = document.getElementById('fuel-regime-market-sub');
    const marketNoSub = document.getElementById('fuel-regime-market-nosub');
    const controlSub = document.getElementById('fuel-regime-control-sub');
    const controlNoSub = document.getElementById('fuel-regime-control-nosub');
    if (!section || !marketSub || !marketNoSub || !controlSub || !controlNoSub) return;

    const d = SCATTER_DATA.find(x => x.country === countryName);
    if (!d) {{ section.style.display = 'none'; return; }}
    const iso3 = d.wb_iso3 || '';
    const perProd = PRODUCT_REGIMES[iso3] || {{}};
    const subsidyMap = d.imf_has_subsidy || {{}};

    const rows = window._fuelCountryRows || [];
    const buckets = {{
        marketSub: [],
        marketNoSub: [],
        controlSub: [],
        controlNoSub: [],
    }};
    selectedKeys.forEach(function(key) {{
        const row = rows.find(r => chipKey(r) === key);
        if (!row) return;
        const baseProd = fuelBaseProduct(row);
        if (!baseProd) return;
        const info = perProd[baseProd];
        if (!info || !info.regime || info.regime === 'Unknown') return;
        const entry = {{
            key: key,
            label: chipLabel(key),
            color: keyColors[key] || '#666',
        }};
        const isSub = !!subsidyMap[baseProd];
        if (info.regime === 'Market') {{
            (isSub ? buckets.marketSub : buckets.marketNoSub).push(entry);
        }} else if (info.regime === 'Price Control') {{
            (isSub ? buckets.controlSub : buckets.controlNoSub).push(entry);
        }}
    }});

    function renderCell(entries, el) {{
        if (!entries.length) {{
            el.innerHTML = '';
            return;
        }}
        let html = '';
        entries.forEach(function(e) {{
            html += '<span class="regime-badge" style="background:' + e.color + '">' + e.label + '</span>';
        }});
        el.innerHTML = html;
    }}

    renderCell(buckets.marketSub, marketSub);
    renderCell(buckets.marketNoSub, marketNoSub);
    renderCell(buckets.controlSub, controlSub);
    renderCell(buckets.controlNoSub, controlNoSub);

    const total = buckets.marketSub.length + buckets.marketNoSub.length + buckets.controlSub.length + buckets.controlNoSub.length;
    section.style.display = total ? '' : 'none';
}}

document.getElementById("fuel-country-select").addEventListener("change", function() {{
    rebuildFuelChips();
    initFuelSlider();
    rerenderFuel();
}});
// ─── Init ───────────────────────────────────────────────────────────────────────────
requestAnimationFrame(() => {{
    commTabInitialized = true;
    buildKPI(ALL_PRODUCTS[0]);
    buildCommChips();
    initCommSlider();
    renderComm();
}});
</script>
</body>
</html>"""

    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  [policy] Created {out}")
