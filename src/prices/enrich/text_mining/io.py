from pathlib import Path

import pandas as pd
import polars as pl

from prices.enrich import config

# The harness's sole write surface. Mirrors the established _enrich/_* artifact
# convention; the leading underscore matches the discovery-skip rule. NOT added
# to the cascade config.py — kept here so the read-only boundary stays crisp.
REPORT_DIR = config.ENRICH_DIR / "_text_mining"

# Layer-0 spine column subset for the full-corpus passes (column-pruned scan).
_PRODUCTS_INPUT_DEFAULT_COLUMNS = [
    "product_name_original",
    "country",
    "channel",
    "lang",
    "price",
    "n_rows",
]

# products.parquet default subset — deliberately excludes the input_hashes
# list column (expensive to materialize, never needed by the harness).
_PRODUCTS_DEFAULT_COLUMNS = [
    "product_identity_key",
    "first_name",
    "canonical_loose",
    "country",
    "lang",
    "brand",
    "count",
    "value",
    "unit",
    "category",
    "channel",
    "price",
    "n_observations",
]


def ensure_report_dir() -> Path:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    return REPORT_DIR


def _resolve_within_report_dir(name: str, suffix: str) -> Path:
    if not name.endswith(suffix):
        raise ValueError(f"name must end in {suffix!r}: {name!r}")
    if Path(name).is_absolute():
        raise ValueError(f"absolute paths are not allowed: {name!r}")
    base = REPORT_DIR.resolve()
    target = (base / name).resolve()
    if target != base and base not in target.parents:
        raise ValueError(f"name escapes the report dir: {name!r}")
    return target


def write_markdown(name: str, text: str) -> Path:
    target = _resolve_within_report_dir(name, ".md")
    ensure_report_dir()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    return target


def write_parquet(name: str, frame) -> Path:
    target = _resolve_within_report_dir(name, ".parquet")
    ensure_report_dir()
    target.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(frame, pl.DataFrame):
        frame.write_parquet(target)
    else:
        frame.to_parquet(target, index=False)
    return target


def read_products_input(columns: list[str] | None = None) -> pd.DataFrame:
    cols = columns if columns is not None else _PRODUCTS_INPUT_DEFAULT_COLUMNS
    return (
        pl.scan_parquet(config.PRODUCTS_INPUT_PARQUET)
        .select(cols)
        .collect()
        .to_pandas()
    )


def read_products(columns: list[str] | None = None) -> pd.DataFrame:
    cols = columns if columns is not None else _PRODUCTS_DEFAULT_COLUMNS
    return pl.scan_parquet(config.PRODUCTS_PARQUET).select(cols).collect().to_pandas()
