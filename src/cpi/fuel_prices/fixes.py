"""One-time data fix functions applied via `python -m src.cpi.fuel_prices migrate`."""

import logging

import pandas as pd

logger = logging.getLogger(__name__)


def fix_australia_units(df: pd.DataFrame) -> pd.DataFrame:
    """Convert AUDc (cents) -> AUD (dollars) by dividing price by 100.

    Idempotency guard: only applies when price_local > 10 (already-fixed values
    are ~1.4 AUD/L, so dividing again would not pass this threshold).
    """
    mask = (df["currency"] == "AUDc") & (df["price_local"] > 10)
    df.loc[mask, "price_local"] = df.loc[mask, "price_local"] / 100
    df.loc[mask, "currency"] = "AUD"
    if mask.sum():
        logger.info(
            "[fix_au] %d Australia AUDc rows -> AUD (÷100). Price range: %.2f–%.2f",
            mask.sum(),
            df.loc[mask, "price_local"].min(),
            df.loc[mask, "price_local"].max(),
        )
    return df


def fix_quality_group(df: pd.DataFrame) -> pd.DataFrame:
    """Fill missing quality_group for diesel/kerosene rows."""
    specs = [
        ("jp_anre_weekly_petroleum_2025", r"^Diesel$", "regular"),
        ("jp_anre_weekly_petroleum_2025", r"^Kerosene", "regular"),
        ("my_mof_weekly_petroleum", r"^Diesel", "regular"),
        ("ph_doe_retail_pump_prices", r"(?i)^diesel", "regular"),
        ("fiji_fccc_monthly_prices", r"^Diesel$", "regular"),
        ("fiji_fccc_monthly_prices", r"^Kerosene$", "regular"),
        (
            "fiji_fccc_monthly_prices",
            r"(?i)^(Autogas|Bulk LPG|\d+\.?\d* Kg Cylinder)$",
            "regular",
        ),
        ("kh_moc_fuel_notices", r"^Diesel$", "regular"),
        ("kr_opinet_weekly_national_sampled_2025", r"^Diesel", "regular"),
    ]
    for src, prod_pat, qg in specs:
        mask = (
            (df["source_key"] == src)
            & df["fuel_product"].str.match(prod_pat, na=False)
            & df["quality_group"].isna()
        )
        if mask.sum():
            df.loc[mask, "quality_group"] = qg
            logger.info(
                "[fix_qg] %d rows -> quality_group='%s' (%s, /%s/)",
                mask.sum(),
                qg,
                src,
                prod_pat,
            )

    pert_mask = df["source_key"] == "id_pertamina_jakarta_2025_series"
    pertamina_specs = [
        (r"^Biosolar", "regular"),
        (r"^Dexlite$", "premium"),
        (r"^Pertamina Dex$", "super_premium"),
    ]
    for pat, qg in pertamina_specs:
        mask = (
            pert_mask
            & df["fuel_product"].str.match(pat, na=False)
            & df["quality_group"].isna()
        )
        if mask.sum():
            df.loc[mask, "quality_group"] = qg
            logger.info(
                "[fix_qg] %d Pertamina rows -> quality_group='%s' (/%s/)",
                mask.sum(),
                qg,
                pat,
            )

    return df


def fix_anre_kerosene_unit(df: pd.DataFrame) -> pd.DataFrame:
    """Convert Japan ANRE kerosene from per-18L can to per-litre.

    Idempotency guard: only applies when price_local > 500 (JPY/18L range is
    ~2400-2700; already-fixed values are ~130-150 JPY/L).
    """
    mask = (
        (df["unit"] == "18L")
        & (df["source_key"] == "jp_anre_weekly_petroleum_2025")
        & (df["price_local"] > 500)
    )
    before = df.loc[mask, "price_local"].mean()
    df.loc[mask, "price_local"] = df.loc[mask, "price_local"] / 18
    df.loc[mask, "unit"] = "L"
    after = df.loc[mask, "price_local"].mean()
    if mask.sum():
        logger.info(
            "[fix_ker] %d ANRE kerosene rows: 18L->L (÷18). Mean price: %.1f->%.1f JPY/L",
            mask.sum(),
            before,
            after,
        )
    return df


def fix_fuel_family(df: pd.DataFrame) -> pd.DataFrame:
    """Infer fuel_family for rows where it is blank, using product name keywords."""
    blank = df["fuel_family"].isna() | (df["fuel_family"].astype(str).str.strip() == "")

    keyword_map = [
        ("diesel", ["diesel", "biosolar", "dexlite", "dầu diesel", "mazut", "ado"]),
        (
            "gasoline",
            [
                "petrol",
                "gasoline",
                "ron",
                "motor spirit",
                "benzine",
                "xăng",
                "pertalite",
                "pertamax",
                "regular gasoline",
                "autogas",
            ],
        ),
        ("kerosene", ["kerosene", "kerosin", "dầu hỏa"]),
        ("lpg", ["lpg", "propane", "cylinder", "autogas"]),
        ("natural_gas", ["ngv", "natural gas", "cng", "town gas"]),
    ]

    count = 0
    for idx in df[blank].index:
        p = str(df.at[idx, "fuel_product"]).lower()
        for family, keywords in keyword_map:
            if any(kw in p for kw in keywords):
                df.at[idx, "fuel_family"] = family
                count += 1
                break

    if count:
        logger.info("[fix_ff] Inferred fuel_family for %d blank rows", count)
    return df


def fix_column_homogenization(df: pd.DataFrame) -> pd.DataFrame:
    """Homogenize fuel_family, fuel_product, and quality_group columns."""
    QG_REMAP = [
        ("octane_95", "gasoline", "premium"),
    ]
    remap_total = 0
    for old_qg, family, new_qg in QG_REMAP:
        mask = (df["quality_group"] == old_qg) & (df["fuel_family"] == family)
        if mask.sum():
            df.loc[mask, "quality_group"] = new_qg
            remap_total += mask.sum()
            logger.info(
                "[fix_homog] %d rows: quality_group '%s' -> '%s' (family=%s)",
                mask.sum(),
                old_qg,
                new_qg,
                family,
            )
    if remap_total:
        logger.info("[fix_homog] Total quality_group remapped: %d rows", remap_total)

    QG_INFER = [
        (r"(?i)^Premium Diesel$", "diesel", "premium"),
        (r"(?i)^Diesel", "diesel", "regular"),
        (r"(?i)^Low Sulphur Diesel", "diesel", "regular"),
        (r"(?i)^Kerosene", "kerosene", "regular"),
        (r"(?i)^Propane LPG$", "lpg", "regular"),
        (r"(?i)^NGV retail price$", "natural_gas", "regular"),
    ]

    total = 0
    for pat, family, qg in QG_INFER:
        mask = (
            df["quality_group"].isna()
            & (df["fuel_family"] == family)
            & df["fuel_product"].str.match(pat, na=False)
        )
        if mask.sum():
            df.loc[mask, "quality_group"] = qg
            total += mask.sum()
            logger.info(
                "[fix_homog] %d rows -> quality_group='%s' (family=%s, /%s/)",
                mask.sum(),
                qg,
                family,
                pat,
            )

    logger.info("[fix_homog] Total quality_group filled: %d rows", total)
    return df


def run_all_fixes(df: pd.DataFrame) -> pd.DataFrame:
    """Run all five one-time fixes in order."""
    df = fix_australia_units(df)
    df = fix_quality_group(df)
    df = fix_anre_kerosene_unit(df)
    df = fix_fuel_family(df)
    df = fix_column_homogenization(df)
    return df
