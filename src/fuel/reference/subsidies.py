"""IMF fossil fuel subsidies + WB pricing regime loaders.

Cached to ``{cache_dir}/imf/`` and ``{cache_dir}/worldbank/``.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

import pandas as pd
import requests

logger = logging.getLogger(__name__)

_IMF_XLSB_URL = (
    "https://www.imf.org/-/media/files/topics/"
    "energysubsidies/imffossilfuelsubsidiesdata.xlsb"
)

PRODUCTS = ["Gasoline", "Diesel", "Kerosene", "LPG", "Natural Gas", "Coal"]
TABLE_PRODUCTS = ["Gasoline", "Diesel", "LPG", "Kerosene"]

REGIME_COLORS = {
    "Market": "#6c757d",
    "Market Prices with Subsidies": "#2196f3",
    "Price Control": "#d62728",
    "Price Control with Subsidies": "#e6ab02",
    "Unknown": "#aec7e8",
}

_CODE_TO_BASE_REGIME = {
    0: "Market",
    1: "Market",
    2: "Price Control",
    3: "Market",
}

_SUBSIDY_TYPE_CODES = {3, 4, 5, 6, 7, 9}

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


def _split_not_in_parens(text: str) -> list[str]:
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
    if not text or str(text).lower().strip() in ("nan", "none", ""):
        return {
            p: {"regime": overall_base, "subsidy": overall_subsidy}
            for p in TABLE_PRODUCTS
        }

    per_product: dict[str, dict] = {}
    for entry in _split_not_in_parens(str(text)):
        m_qual = re.search(r"\(([^)]+)\)", entry)
        if not m_qual:
            continue
        qualifier = m_qual.group(1).lower()
        m_code = re.search(r"(\d+)", entry)
        if not m_code:
            continue
        code = int(m_code.group(1))
        base = _CODE_TO_BASE_REGIME.get(code, overall_base)
        subsidy = code in _SUBSIDY_TYPE_CODES or overall_subsidy

        matched = [
            p
            for p in TABLE_PRODUCTS
            if any(kw in qualifier for kw in _PRODUCT_QUAL_KEYWORDS.get(p, []))
        ]
        for p in matched:
            per_product[p] = {"regime": base, "subsidy": subsidy}

    if not per_product:
        return {
            p: {"regime": overall_base, "subsidy": overall_subsidy}
            for p in TABLE_PRODUCTS
        }
    return {
        p: per_product.get(p, {"regime": overall_base, "subsidy": overall_subsidy})
        for p in TABLE_PRODUCTS
    }


def _apply_hardcoded_overrides(
    out: pd.DataFrame,
    product_regimes: dict[str, dict[str, dict]],
    overrides: dict[str, dict[str, dict]],
) -> tuple[pd.DataFrame, dict[str, dict[str, dict]]]:
    for iso3, per_product in overrides.items():
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


def load_regime_data(
    regime_csv: Path,
    overrides: dict[str, dict[str, dict]] | None = None,
) -> tuple[pd.DataFrame, dict[str, dict[str, dict]]]:
    """Load WB subsidies/price controls CSV and classify pricing regimes."""
    if not regime_csv.exists():
        logger.warning("Regime CSV not found: %s", regime_csv)
        return pd.DataFrame(), {}

    df = pd.read_csv(regime_csv, header=[0, 1], low_memory=False)

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

    def classify_base(row):
        pm = row["pricing_mechanism"]
        return _CODE_TO_BASE_REGIME.get(int(pm) if pd.notna(pm) else -1, "Unknown")

    def classify_subsidy(row):
        st = row["subsidy_type"]
        return int(st) in _SUBSIDY_TYPE_CODES if pd.notna(st) else False

    out["base_regime"] = out.apply(classify_base, axis=1)
    out["subsidy_flag"] = out.apply(classify_subsidy, axis=1)
    out["regime"] = out.apply(
        lambda r: r["base_regime"] + (" + Subsidies" if r["subsidy_flag"] else ""),
        axis=1,
    )

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
        st_prods = _parse_product_qualifier(raw_stype.at[idx], base, False)
        merged: dict[str, dict] = dict(pm_prods)
        for prod, info in st_prods.items():
            if (
                info["subsidy"] != pm_prods[prod]["subsidy"]
                or info["regime"] != pm_prods[prod]["regime"]
            ):
                merged[prod] = info
        product_regimes[iso3] = merged

    if overrides:
        out, product_regimes = _apply_hardcoded_overrides(
            out, product_regimes, overrides
        )

    return out.reset_index(drop=True), product_regimes


def load_imf_subsidies(cache_dir: Path) -> pd.DataFrame:
    """Load IMF Fossil Fuel Subsidies (All_Implicit sheet).

    Auto-downloads the XLSB if not cached. Returns wide DataFrame with
    columns: country_name, wb_iso3, Gasoline, Diesel, Kerosene, LPG,
    Natural Gas, Coal (values in billion USD).
    """
    xlsb_path = cache_dir / "imf" / "fossil_fuel_subsidies.xlsb"
    if not xlsb_path.exists():
        logger.info("Downloading IMF subsidies XLSB ...")
        try:
            resp = requests.get(_IMF_XLSB_URL, timeout=120, stream=True)
            resp.raise_for_status()
            xlsb_path.parent.mkdir(parents=True, exist_ok=True)
            with open(xlsb_path, "wb") as fh:
                for chunk in resp.iter_content(chunk_size=65536):
                    fh.write(chunk)
            logger.info("Saved %s (%d bytes)", xlsb_path, xlsb_path.stat().st_size)
        except Exception as exc:
            logger.warning("Could not download IMF XLSB: %s", exc)
            return pd.DataFrame()

    try:
        df = pd.read_excel(xlsb_path, engine="pyxlsb", sheet_name="All_Implicit")
    except Exception as exc:
        logger.warning("Could not read IMF XLSB: %s", exc)
        return pd.DataFrame()

    if df.empty:
        logger.warning("IMF XLSB All_Implicit sheet is empty")
        return pd.DataFrame()

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
        logger.warning("No product label row found in IMF XLSB")
        return pd.DataFrame()

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
        logger.warning("No product columns identified in IMF XLSB")
        return pd.DataFrame()

    data = df.iloc[label_row_idx + 2 :].dropna(how="all").reset_index(drop=True)

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
        logger.warning("No country column detected in IMF XLSB")
        return pd.DataFrame()

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
        logger.warning("IMF XLSB parsed 0 records")
        return pd.DataFrame()

    df_wide = pd.DataFrame(records)
    for prod in PRODUCTS:
        if prod not in df_wide.columns:
            df_wide[prod] = None

    n_p = sum(1 for p in PRODUCTS if df_wide[p].notna().any())
    logger.info("IMF subsidies: %d countries, %d products", len(df_wide), n_p)
    return df_wide
