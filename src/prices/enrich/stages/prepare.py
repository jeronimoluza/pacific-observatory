import re
from pathlib import Path
from typing import Optional

import pandas as pd

from core.config import load_countries
from prices.enrich import config
from prices.enrich.versioning import input_hash

# Currencies that use European-style number formatting:
# '.' = thousands separator, ',' = decimal separator.
_EU_FORMAT_CURRENCIES = {"EUR", "ARS", "BRL", "CLP", "COP", "IDR", "VND"}


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


def _clean_url(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value).strip()


def _row_input_dict(row: pd.Series) -> dict:
    """Dedup identity = (product_name, product_url). Rows with no URL (wayback /
    common-crawl) fall back to (name, country, currency) so they are not
    over-collapsed by a shared empty URL."""
    name = row.get("product_name_original")
    if name is None or (isinstance(name, float) and pd.isna(name)):
        name = row.get("product_name")
    url = _clean_url(row.get("product_url"))
    if url:
        return {"product_name_original": str(name), "product_url": url}
    return {
        "product_name_original": str(name),
        "country": str(row["country"]),
        "currency": str(row["currency"]),
    }


def _build_country_lang_map() -> dict[str, str]:
    """Country slug → first language from countries.yaml; '' if missing."""
    out: dict[str, str] = {}
    for slug, meta in load_countries().items():
        langs = meta.get("languages") or []
        out[slug] = langs[0] if langs else ""
    return out


def _build_source_channel_map() -> dict[tuple[str, str], str]:
    """(country, source) → channel from per-source YAML; missing keys default
    to '' downstream."""
    from prices.config import PriceSourceConfig, discover_prices_configs

    out: dict[tuple[str, str], str] = {}
    for path in discover_prices_configs():
        try:
            cfg = PriceSourceConfig.load(path)
        except Exception:
            continue
        if cfg.channel:
            out[(cfg.country, cfg.source)] = cfg.channel
    return out


def _build_source_coicop_codes_map() -> dict[tuple[str, str], str]:
    """(country, source) → `|`-joined declared coicop_codes from per-source
    YAML. Missing or empty declarations are absent from the map."""
    from prices.config import PriceSourceConfig, discover_prices_configs
    from prices.enrich.coicop_codes import serialize_codes

    out: dict[tuple[str, str], str] = {}
    for path in discover_prices_configs():
        try:
            cfg = PriceSourceConfig.load(path)
        except Exception:
            continue
        serialized = serialize_codes(cfg.coicop_codes)
        if serialized:
            out[(cfg.country, cfg.source)] = serialized
    return out


def _modal_or_empty(series: pd.Series) -> str:
    mode = series.mode()
    return str(mode.iloc[0]) if not mode.empty else ""


def _first_non_empty(series: pd.Series) -> str:
    for v in series:
        s = "" if pd.isna(v) else str(v)
        if s:
            return s
    return ""


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
    else:
        df["category"] = df["category"].fillna("").astype(str)
    if "details" not in df.columns:
        df["details"] = ""
    else:
        df["details"] = df["details"].fillna("").astype(str)
    if "product_url" not in df.columns:
        df["product_url"] = ""
    df["product_url"] = df["product_url"].map(_clean_url)
    if "date" in df.columns:
        df["observation_date"] = pd.to_datetime(df["date"], errors="coerce")
    else:
        df["observation_date"] = pd.NaT
    df["price"] = df.apply(lambda r: parse_price(r["price"], r.get("currency")), axis=1)
    df["input_hash"] = df.apply(lambda r: input_hash(_row_input_dict(r)), axis=1)
    lang_map = _build_country_lang_map()
    df["lang"] = df["country"].map(lang_map).fillna("").astype(str)

    # Channel — per-row from concatenate when present; fall back to source-YAML
    # lookup for rows produced before this change shipped.
    channel_map = _build_source_channel_map()
    if "channel" not in df.columns:
        df["channel"] = ""
    df["channel"] = df["channel"].fillna("").astype(str)
    if "source" in df.columns:
        fallback = df.set_index(["country", "source"]).index.map(
            lambda k: channel_map.get(k, "")
        )
        df["channel"] = df["channel"].where(
            df["channel"] != "", pd.Series(fallback, index=df.index)
        )

    coicop_codes_map = _build_source_coicop_codes_map()
    if "source" in df.columns:
        declared = df.set_index(["country", "source"]).index.map(
            lambda k: coicop_codes_map.get(k, "")
        )
        df["declared_coicop_codes"] = pd.Series(declared, index=df.index).astype(str)
    else:
        df["declared_coicop_codes"] = ""

    agg = dict(
        product_name_original=("product_name_original", "first"),
        product_url=("product_url", _first_non_empty),
        category=("category", _first_non_empty),
        details=("details", _first_non_empty),
        country=("country", "first"),
        currency=("currency", "first"),
        lang=("lang", "first"),
        channel=("channel", _modal_or_empty),
        declared_coicop_codes=("declared_coicop_codes", _modal_or_empty),
        observation_date=("observation_date", "max"),
        price=("price", "median"),
        n_rows=("input_hash", "size"),
    )
    for col in ("source", "region", "subregion"):
        if col in df.columns:
            agg[col] = (col, _first_non_empty)
    grouped = df.groupby("input_hash", as_index=False).agg(**agg)
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
