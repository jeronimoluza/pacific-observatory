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
from pathlib import Path

import pandas as pd
import requests

from .constants import DATA_DIR, COMMODITY_CSV, PALETTE

_SUBSIDIES_XLSX = DATA_DIR / "Subsidies 2010-2024.xlsx"  # legacy, not loaded
_IMF_XLSB_URL = "https://www.imf.org/-/media/files/topics/energysubsidies/imffossilfuelsubsidiesdata.xlsb"
_IMF_XLSB = DATA_DIR / "imffossilfuelsubsidiesdata.xlsb"
_CONTROLS_CSV = DATA_DIR / "subsidies_price_controls_2024.csv"
_PRIMARY_CSV = DATA_DIR / "eap_fuel_prices.csv"
_SECONDARY_CSV = DATA_DIR / "eap_fuel_prices_secondary.csv"
_POPULATION_CSV = DATA_DIR / "population.csv"
_GDP_CSV = DATA_DIR / "gdp_per_capita.csv"

_REGIME_COLORS = {
    "Market": "#6c757d",
    "Price Control": "#d62728",
    "Hybrid/Subsidised": "#e6ab02",
    "Unknown": "#aec7e8",
}

_PRODUCTS = ["Gasoline", "Diesel", "Kerosene", "LPG", "Natural Gas", "Coal"]
_TABLE_PRODUCTS = ["Gasoline", "Diesel", "LPG", "Kerosene"]

_CODE_TO_REGIME = {
    0: "Market",
    1: "Price Control",
    2: "Price Control",
    3: "Hybrid/Subsidised",
    6: "Hybrid/Subsidised",
    7: "Hybrid/Subsidised",
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
    text: str, overall_regime: str = "Unknown"
) -> dict[str, str]:
    """Return per-product regimes.  Only entries with an explicit parenthesised
    product qualifier are processed; plain codes (no qualifier) are ignored.
    When no product-qualified entries exist, all products return overall_regime.
    """
    if not text or str(text).lower().strip() in ("nan", "none", ""):
        return {p: overall_regime for p in _TABLE_PRODUCTS}

    per_product: dict[str, str] = {}

    for entry in _split_not_in_parens(str(text)):
        m_qual = re.search(r"\(([^)]+)\)", entry)
        if not m_qual:
            continue  # skip entries with no product qualifier
        qualifier = m_qual.group(1).lower()

        m_code = re.search(r"(\d+)", entry)
        if not m_code:
            continue
        regime = _CODE_TO_REGIME.get(int(m_code.group(1)))
        if regime is None:
            continue

        matched = [
            p
            for p in _TABLE_PRODUCTS
            if any(kw in qualifier for kw in _PRODUCT_QUAL_KEYWORDS.get(p, []))
        ]
        for p in matched:
            per_product[p] = regime

    if not per_product:
        # No product-specific qualifiers found — all products mirror the overall regime
        return {p: overall_regime for p in _TABLE_PRODUCTS}

    # Products NOT mentioned in any qualifier default to "Market"
    return {p: per_product.get(p, "Market") for p in _TABLE_PRODUCTS}


# ---------------------------------------------------------------------------
# Data loading helpers
# ---------------------------------------------------------------------------


def _load_commodity_data() -> pd.DataFrame:
    """Load commodity_prices.csv and return relevant global benchmarks."""
    if not COMMODITY_CSV.exists():
        print(f"  [policy] WARNING: {COMMODITY_CSV} not found")
        return pd.DataFrame()
    df = pd.read_csv(COMMODITY_CSV, low_memory=False)
    df["observation_date"] = pd.to_datetime(df["observation_date"], errors="coerce")
    df = df.dropna(subset=["observation_date", "price_local"])
    df["price_local"] = pd.to_numeric(df["price_local"], errors="coerce")
    df = df.dropna(subset=["price_local"])
    df = df[df["price_local"] > 0]
    return df


def _load_regime_data() -> tuple[pd.DataFrame, dict[str, dict[str, str]]]:
    """Load subsidies_price_controls_2024.csv and classify pricing regimes.

    Returns
    -------
    df : pd.DataFrame
        Columns: country_name, wb_iso3, region, pricing_mechanism,
                 subsidy_type, regime, tooltip
    product_regimes : dict[iso3, dict[product, regime_str]]
        Per-product regime strings for each country in *_TABLE_PRODUCTS*.
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

    def classify(row: pd.Series) -> str:
        pm, st = row["pricing_mechanism"], row["subsidy_type"]
        if pm == 2 or st == 1:
            return "Price Control"
        if pm == 3 or st in (2, 6):
            return "Hybrid/Subsidised"
        if pm == 1:
            return "Market"
        return "Unknown"

    out["regime"] = out.apply(classify, axis=1)

    # Build per-product regime dict from raw col-3 and col-12 text
    raw_mech = df[mech_col].astype(str)
    raw_stype = (
        df[stype_col].astype(str)
        if stype_col is not None
        else pd.Series("", index=df.index)
    )

    product_regimes: dict[str, dict[str, str]] = {}
    for idx in out.index:
        iso3 = out.at[idx, "wb_iso3"]
        regime = out.at[idx, "regime"]

        pm_prods = _parse_product_qualifier(raw_mech.at[idx], regime)
        st_prods = _parse_product_qualifier(raw_stype.at[idx], regime)

        # Base: pricing-mechanism column; subsidy-type overrides if more specific
        merged = dict(pm_prods)
        for prod, r in st_prods.items():
            if r != regime:
                merged[prod] = r

        product_regimes[iso3] = merged

    return out.reset_index(drop=True), product_regimes


def _load_eap_countries() -> pd.DataFrame:
    """Return unique country/wb_iso3 pairs from primary + secondary CSVs."""
    frames = []
    for path in (_PRIMARY_CSV, _SECONDARY_CSV):
        if path.exists():
            df = pd.read_csv(path, usecols=["country", "wb_iso3"], low_memory=False)
            frames.append(df)
    if not frames:
        return pd.DataFrame(columns=["country", "wb_iso3"])
    combined = pd.concat(frames, ignore_index=True)
    # Normalise name variants, then deduplicate by iso3 (primary CSV wins)
    combined["country"] = combined["country"].replace({"Viet Nam": "Vietnam"})
    return combined.drop_duplicates(subset=["wb_iso3"]).reset_index(drop=True)


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
    return pd.read_csv(_POPULATION_CSV, low_memory=False)


def _load_gdp() -> pd.DataFrame:
    if not _GDP_CSV.exists():
        print(
            f"  [policy] WARNING: {_GDP_CSV} not found — run fetchers/imf_weo_gdp.py first"
        )
        return pd.DataFrame()
    return pd.read_csv(_GDP_CSV, low_memory=False)


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

    # --- Commodity series for Tab 1 ---
    comm_series: dict = {}
    if not df_comm.empty:
        for prod in df_comm["fuel_product"].dropna().unique():
            rows = df_comm[df_comm["fuel_product"] == prod].sort_values(
                "observation_date"
            )
            pts = [
                {
                    "x": r["observation_date"].strftime("%Y-%m-%d"),
                    "y": round(float(r["price_local"]), 4),
                }
                for _, r in rows.iterrows()
                if pd.notna(r["price_local"])
            ]
            if pts:
                unit = rows["unit"].iloc[0] if "unit" in rows.columns else ""
                currency = (
                    rows["currency"].iloc[0] if "currency" in rows.columns else ""
                )
                comm_series[prod] = {"points": pts, "unit": unit, "currency": currency}

    # --- EAP country list with regimes (for Tab 1 table) ---
    eap_countries: list[dict] = []
    if not df_eap.empty and not df_regime.empty:
        regime_cols = [
            "wb_iso3",
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
        merged = merged.drop_duplicates(subset=["country", "wb_iso3"])
        eap_countries = merged.to_dict(orient="records")
    elif not df_eap.empty:
        df_eap_copy = df_eap.copy()
        df_eap_copy["regime"] = "Unknown"
        df_eap_copy["tooltip"] = ""
        eap_countries = df_eap_copy.to_dict(orient="records")

    # --- Per-capita subsidies (USD/person) from IMF billion-USD data ---
    # imf_pc_by_iso3: {iso3: {product: float|None}}
    imf_pc_by_iso3: dict[str, dict[str, float | None]] = {}
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
            for prod in _PRODUCTS:
                val = row.get(prod)
                if pd.notna(val) and pop_ok:
                    prods[prod] = float(val) * 1e9 / float(pop)
                else:
                    prods[prod] = None
            imf_pc_by_iso3[iso3] = prods

    # --- Scatter data for Tab 2 ---
    scatter_points: list[dict] = []
    if not df_eap.empty:
        base = df_eap.copy().rename(columns={"country": "country_name"})

        if not df_regime.empty:
            base = base.merge(
                df_regime[["wb_iso3", "regime"]], on="wb_iso3", how="left"
            )
            base["regime"] = base["regime"].fillna("Unknown")
        else:
            base["regime"] = "Unknown"

        if not df_pop.empty:
            base = base.merge(
                df_pop[["wb_iso3", "population"]], on="wb_iso3", how="left"
            )
        else:
            base["population"] = None

        if not df_gdp.empty:
            base = base.merge(
                df_gdp[["wb_iso3", "gdp_per_capita"]], on="wb_iso3", how="left"
            )
        else:
            base["gdp_per_capita"] = None

        for _, row in base.iterrows():
            iso3 = str(row.get("wb_iso3", ""))
            subsidies = imf_pc_by_iso3.get(iso3, {p: None for p in _PRODUCTS})
            scatter_points.append(
                {
                    "country": str(row.get("country_name", "")),
                    "wb_iso3": iso3,
                    "regime": str(row.get("regime", "Unknown")),
                    "gdp_per_capita": float(row["gdp_per_capita"])
                    if pd.notna(row.get("gdp_per_capita"))
                    else None,
                    "population": int(row["population"])
                    if pd.notna(row.get("population"))
                    else None,
                    "subsidies": {
                        p: (round(float(v), 4) if v is not None else None)
                        for p, v in subsidies.items()
                    },
                }
            )

    return {
        "comm_series": comm_series,
        "eap_countries": eap_countries,
        "scatter": scatter_points,
        "regime_colors": _REGIME_COLORS,
        "product_regimes": product_regimes,
        "products": _PRODUCTS,
        "table_products": _TABLE_PRODUCTS,
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
"""


def gen_policy_html(data: dict, out: Path) -> None:
    """Write the two-tab standalone HTML file."""
    comm_series = data["comm_series"]
    eap_countries = data["eap_countries"]
    scatter = data["scatter"]
    regime_colors = data["regime_colors"]
    product_regimes = data.get("product_regimes", {})
    table_products = data.get("table_products", _TABLE_PRODUCTS)
    products = data.get("products", _PRODUCTS)

    comm_json = json.dumps(comm_series)
    scatter_json = json.dumps(scatter)
    colors_json = json.dumps(regime_colors)
    palette_json = json.dumps(PALETTE)
    products_json = json.dumps(products)

    # --- Regime table rows ---
    prod_headers = "".join(f"<th>{p}</th>" for p in table_products)
    regime_rows_html = ""
    for c in sorted(
        eap_countries, key=lambda x: x.get("country", x.get("country_name", ""))
    ):
        name = c.get("country", c.get("country_name", ""))
        iso3 = c.get("wb_iso3", "")
        regime = c.get("regime", "Unknown")
        color = regime_colors.get(regime, "#aec7e8")
        tip = _html.escape(str(c.get("tooltip", "")), quote=True)
        tooltip_attr = f' title="{tip}"' if tip and tip.lower() != "nan" else ""

        per_prod = product_regimes.get(iso3, {})
        prod_cells = ""
        for prod in table_products:
            pr = per_prod.get(prod, "")
            if pr and pr != "Unknown":
                pc = regime_colors.get(pr, "#aec7e8")
                prod_cells += (
                    f'<td><span class="regime-badge" style="background:{pc}">'
                    f"{pr}</span></td>"
                )
            else:
                prod_cells += "<td></td>"

        regime_rows_html += (
            f"<tr>"
            f"<td>{name}</td>"
            f'<td><span class="regime-badge" style="background:{color}"{tooltip_attr}>'
            f"{regime}</span></td>"
            f"{prod_cells}"
            f"</tr>\n"
        )

    # --- Product radio buttons for Tab 2 ---
    product_radios_html = ""
    for i, prod in enumerate(products):
        checked = "checked" if i == 0 else ""
        product_radios_html += (
            f'<label><input type="radio" name="product-toggle" value="{prod}" '
            f'{checked} onchange="renderScatter()">{prod}</label>\n'
        )

    # --- Legend for scatter ---
    legend_html = "".join(
        f'<div class="legend-item">'
        f'<div class="legend-dot" style="background:{c}"></div>{r}</div>'
        for r, c in regime_colors.items()
    )
    legend_html += (
        '<div class="legend-item">'
        '<div class="legend-dot" style="background:transparent;border:2px dashed #999"></div>'
        "No subsidy data</div>"
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

    <div class="section-label" style="margin-top:18px">EAP Country Pricing Regimes (2024)</div>
    <div class="regime-table-wrap">
        <table class="regime-table">
            <thead>
                <tr>
                    <th>Country</th>
                    <th>Pricing Regime</th>
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

    <div class="legend-row">{legend_html}</div>
    <div class="scatter-wrapper"><canvas id="scatter-chart"></canvas></div>

    <p style="font-size:0.78em;color:#888;margin-top:8px">
        X axis: GDP per capita (USD, log scale, IMF WEO 2025) &nbsp;|&nbsp;
        Y axis: subsidy per capita (USD/person, IMF Fossil Fuel Subsidies) &nbsp;|&nbsp;
        Hollow markers = no IMF subsidy data available
    </p>
</div>

<script>
// ─── Data ────────────────────────────────────────────────────────────────────
const COMM_SERIES   = {comm_json};
const SCATTER_DATA  = {scatter_json};
const REGIME_COLORS = {colors_json};
const PALETTE       = {palette_json};
const ALL_PRODUCTS  = {products_json};
const EAP_ISOS      = new Set(SCATTER_DATA.map(d => d.wb_iso3));

// ─── Tab switching ────────────────────────────────────────────────────────────
function switchTab(id, btn) {{
    document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.getElementById(id).classList.add('active');
    btn.classList.add('active');
    if (id === 'tab2') renderScatter();
}}

// ─── KPI cards ───────────────────────────────────────────────────────────────
function buildKPI(product) {{
    const row = document.getElementById('kpi-row');
    row.innerHTML = '';

    const withData = SCATTER_DATA.filter(d =>
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
    const threeYearsAgo = new Date();
    threeYearsAgo.setFullYear(threeYearsAgo.getFullYear() - 3);
    const defaultStart = sliderDates.findIndex(d => new Date(d) >= threeYearsAgo);
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
    if (commChart) commChart.destroy();

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
                            return v == null ? null : datasets[item.datasetIndex].label + ': ' + v.toFixed(2);
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
}}

// ─── Scatter chart ────────────────────────────────────────────────────────────
let scatterChart = null;

function renderScatter() {{
    const productEl = document.querySelector('input[name="product-toggle"]:checked');
    const product   = productEl ? productEl.value : ALL_PRODUCTS[0];

    buildKPI(product);

    const regimes = Object.keys(REGIME_COLORS);
    const datasets = [];

    regimes.forEach(regime => {{
        const rPts = SCATTER_DATA.filter(d =>
            d.regime === regime &&
            d.gdp_per_capita != null &&
            d.subsidies && d.subsidies[product] != null
        );
        if (!rPts.length) return;
        datasets.push({{
            label: regime,
            data: rPts.map(d => ({{
                x: d.gdp_per_capita,
                y: d.subsidies[product] || 0,
                _meta: d,
            }})),
            backgroundColor: REGIME_COLORS[regime] + 'cc',
            borderColor:     REGIME_COLORS[regime],
            borderWidth: 1.5,
            pointRadius: 7,
            pointHoverRadius: 9,
        }});
    }});

    const noDataPts = SCATTER_DATA.filter(d =>
        d.gdp_per_capita != null &&
        (!d.subsidies || d.subsidies[product] == null)
    );
    if (noDataPts.length) {{
        datasets.push({{
            label: 'No subsidy data',
            data: noDataPts.map(d => ({{ x: d.gdp_per_capita, y: 0, _meta: d }})),
            backgroundColor: 'transparent',
            borderColor: '#999',
            borderWidth: 1.5,
            pointRadius: 7,
            pointHoverRadius: 9,
            pointStyle: 'circle',
        }});
    }}

    const ctx = document.getElementById('scatter-chart').getContext('2d');
    if (scatterChart) scatterChart.destroy();
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
                            const sub = m.subsidies && m.subsidies[product] != null
                                ? '$' + m.subsidies[product].toFixed(1) + '/person'
                                : 'no data';
                            const gdp = m.gdp_per_capita != null
                                ? '$' + Math.round(m.gdp_per_capita).toLocaleString()
                                : 'N/A';
                            return m.country + ' (' + m.wb_iso3 + ') \u2014 '
                                 + product + ': ' + sub + ', GDP/cap: ' + gdp;
                        }}
                    }}
                }},
            }},
            scales: {{
                x: {{
                    type: 'logarithmic',
                    display: true,
                    title: {{ display: true, text: 'GDP per capita (USD, log scale)' }},
                }},
                y: {{
                    display: true,
                    title: {{ display: true, text: product + ' subsidy per capita (USD/person)' }},
                    beginAtZero: true,
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
                        if (!m) return;
                        ctx.save();
                        ctx.font = '9px sans-serif';
                        ctx.fillStyle = '#333';
                        ctx.textAlign = 'center';
                        ctx.fillText(m.wb_iso3, pt.x, pt.y - 10);
                        ctx.restore();
                    }});
                }});
            }}
        }}]
    }});
}}

// ─── Init ─────────────────────────────────────────────────────────────────────
buildKPI(ALL_PRODUCTS[0]);
buildCommChips();
initCommSlider();
renderComm();
</script>
</body>
</html>"""

    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  [policy] Created {out}")
