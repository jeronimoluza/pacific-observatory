import re
from pathlib import Path
from typing import Optional

import pandas as pd

from prices.enrich import config
from prices.enrich.versioning import input_hash

# Currencies that use European-style number formatting:
# '.' = thousands separator, ',' = decimal separator.
_EU_FORMAT_CURRENCIES = {"EUR", "ARS", "BRL", "CLP", "COP", "IDR"}


def parse_price(price_str, currency: Optional[str] = None) -> Optional[float]:
    """Parse a price value (string or numeric) to a float.

    Currency-aware: IDR/EUR/ARS/BRL/CLP/COP use '.' as thousands and ','
    as decimal; everything else uses ',' as thousands and '.' as decimal.
    """
    if isinstance(price_str, (int, float)):
        return float(price_str) if not pd.isna(price_str) else None
    if not isinstance(price_str, str):
        return None

    cleaned = price_str.strip()
    if not cleaned:
        return None

    if currency == "IDR":
        cleaned = re.sub(r"Rp\s*", "", cleaned, flags=re.IGNORECASE)

    if currency in _EU_FORMAT_CURRENCIES:
        # '.' = thousands, ',' = decimal
        match = re.search(r"[\d.]+,?\d*", cleaned)
        if not match:
            return None
        number_str = match.group().replace(".", "").replace(",", ".")
    else:
        # ',' = thousands, '.' = decimal
        match = re.search(r"[\d,]+\.?\d*", cleaned)
        if not match:
            return None
        number_str = match.group().replace(",", "")

    try:
        return float(number_str)
    except (ValueError, TypeError):
        return None


def _row_input_dict(row: pd.Series) -> dict:
    return {
        "product_name_original": str(row["product_name"]),
        "category": "" if pd.isna(row.get("category")) else str(row["category"]),
        "country": str(row["country"]),
        "currency": str(row["currency"]),
    }


def prepare_input(raw: pd.DataFrame) -> pd.DataFrame:
    df = raw.copy()
    if "product_name_original" not in df.columns:
        df["product_name_original"] = df["product_name"].astype(str)
    else:
        df["product_name_original"] = (
            df["product_name_original"].fillna(df["product_name"]).astype(str)
        )
    if "category" not in df.columns:
        df["category"] = ""
    df["price"] = df.apply(lambda r: parse_price(r["price"], r.get("currency")), axis=1)
    df["input_hash"] = df.apply(lambda r: input_hash(_row_input_dict(r)), axis=1)
    grouped = df.groupby("input_hash", as_index=False).agg(
        product_name_original=("product_name_original", "first"),
        category=("category", "first"),
        country=("country", "first"),
        currency=("currency", "first"),
        price=("price", "median"),
        n_rows=("input_hash", "size"),
    )
    return grouped


def run(
    csv_path: Optional[Path] = None, out_path: Optional[Path] = None
) -> pd.DataFrame:
    csv_path = csv_path or config.RAW_PRICES_CSV
    out_path = out_path or config.PRODUCTS_INPUT_PARQUET
    raw = pd.read_csv(csv_path, low_memory=False)
    prepared = prepare_input(raw)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    prepared.to_parquet(out_path, index=False)
    return prepared
