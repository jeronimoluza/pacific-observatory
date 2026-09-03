import re
from functools import lru_cache
from pathlib import Path
from typing import Optional

import pandas as pd

from core.config import load_countries
from prices.enrich import config
from prices.enrich.versioning import input_hash

# Currencies that use European-style number formatting:
# '.' = thousands separator, ',' = decimal separator.
_EU_FORMAT_CURRENCIES = {"EUR", "ARS", "BRL", "CLP", "COP", "IDR", "VND"}

# Currency tokens stripped BEFORE the numeric search. Stripping is what makes a
# repeated token dangerous: an archive parser that flattens a sale price and its
# struck-through original into one node yields "Rp 78.875Rp 102.975", and
# removing every "Rp" glues the digit runs into "78.875102.975" -- which the
# EU-format rules then read as a single 11-digit number. Every other currency is
# safe by accident: its symbol survives into the search, where the numeric regex
# stops at it.
_STRIPPED_CURRENCY_TOKENS = {"IDR": r"Rp"}

# A bare numeral: digits optionally interleaved with '.'/',', but always
# starting and ending on a digit so a trailing sentence period or a leading
# currency symbol is never pulled into the match.
_NUMBER_RE = re.compile(r"\d[\d.,]*\d|\d")


def _normalize_number(raw: str, currency: Optional[str]) -> Optional[str]:
    """Rewrite a bare numeral run to a plain dot-decimal string.

    Decimal-vs-thousands is decided from the numeral's own shape first; the
    currency's locale convention (EU: ',' decimal / '.' thousands; else '.'
    decimal / ',' thousands) only breaks a tie when the shape is genuinely
    ambiguous -- a single separator with exactly three trailing digits, which
    is the one case that both a real thousands group and a decimal fraction
    can produce. Everything else follows from the digits alone:

    - both separators present -> the LAST one is decimal, the rest thousands.
    - the same separator repeated -> thousands (a number has one decimal point).
    - a single separator with a trailing-digit count other than 3 -> decimal
      (a thousands group is always exactly 3 digits).
    - a single separator matching the currency's NATIVE decimal char -> decimal,
      regardless of trailing digit count (that char never groups thousands in
      this locale).
    """
    dots = raw.count(".")
    commas = raw.count(",")

    if dots and commas:
        decimal_pos = max(raw.rfind("."), raw.rfind(","))
        int_part = raw[:decimal_pos].replace(".", "").replace(",", "")
        frac_part = raw[decimal_pos + 1 :]
        if not int_part and not frac_part:
            return None
        return f"{int_part}.{frac_part}" if frac_part else int_part

    sep_char = "." if dots else ("," if commas else None)
    if sep_char is None:
        return raw

    if (dots or commas) > 1:
        return raw.replace(sep_char, "")

    digits_after = len(raw) - raw.rfind(sep_char) - 1
    native_decimal_char = "," if currency in _EU_FORMAT_CURRENCIES else "."

    if digits_after != 3 or sep_char == native_decimal_char:
        return raw.replace(",", ".") if sep_char == "," else raw

    return raw.replace(sep_char, "")


def parse_price(price_str, currency: Optional[str] = None) -> Optional[float]:
    """Parse a price value (string or numeric) to a float. See
    `_normalize_number` for how decimal-vs-thousands is decided for strings."""
    if isinstance(price_str, (int, float)):
        return float(price_str) if not pd.isna(price_str) else None
    if not isinstance(price_str, str):
        return None

    cleaned = price_str.strip()
    if not cleaned:
        return None

    token = _STRIPPED_CURRENCY_TOKENS.get(currency)
    if token:
        # A price field names its currency at most once. Two occurrences means
        # the markup fused two prices; refuse rather than guess which half is
        # real. A wrong price here ships as a trusted unit value, and the
        # outlier audit cannot see it when it is alone in its cell-month.
        if len(re.findall(token, cleaned, flags=re.IGNORECASE)) > 1:
            return None
        cleaned = re.sub(token + r"\s*", "", cleaned, flags=re.IGNORECASE)

    match = _NUMBER_RE.search(cleaned)
    if not match:
        return None
    number_str = _normalize_number(match.group(), currency)
    if not number_str:
        return None

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


# These three walk countries.yaml and all 1,463 per-source YAMLs, which costs
# ~1.2s and does not depend on the frame being prepared. prepare_input called
# them on every invocation, which was free while it ran once over the whole
# corpus and is not once it runs per country.
@lru_cache(maxsize=1)
def _build_country_lang_map() -> dict[str, str]:
    """Country slug → first language from countries.yaml; '' if missing."""
    out: dict[str, str] = {}
    for slug, meta in load_countries().items():
        langs = meta.get("languages") or []
        out[slug] = langs[0] if langs else ""
    return out


@lru_cache(maxsize=1)
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


@lru_cache(maxsize=1)
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


def _derive(raw: pd.DataFrame) -> pd.DataFrame:
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
    if "unit" not in df.columns:
        df["unit"] = ""
    else:
        df["unit"] = df["unit"].fillna("").astype(str)
    if "product_url" not in df.columns:
        df["product_url"] = ""
    df["product_url"] = df["product_url"].map(_clean_url)
    if "date" in df.columns:
        # format="mixed": Common Crawl writes compact numeric timestamps
        # ("20251212100333") while live scrapes write ISO. Inferring a single
        # format from the first row coerces every other shape to NaT.
        # utc=True is required, not cosmetic: the corpus mixes tz-aware ISO,
        # tz-naive ISO, RFC2822 (Common Crawl) and compact numeric stamps. With
        # mixed offsets and no utc=True pandas returns object dtype, and the
        # `observation_date=max` aggregation below dies with "agg function
        # failed [how->max,dtype->object]".
        # A chunk holding only Common Crawl rows infers int64 for `date`, and
        # pandas then reads the compact stamp 20240722014727 as NANOSECONDS
        # since epoch -- every such row lands on 1970-01-01, silently. A chunk
        # that mixes CC with ISO rows infers object and parses correctly, so the
        # corruption depends on chunk composition rather than on the data.
        # Rendering compact stamps as text first makes the parse independent of
        # how the chunk happened to be typed.
        raw = df["date"]
        num = pd.to_numeric(raw, errors="coerce")
        compact = num.notna() & (num >= 1e13) & (num < 1e15)
        if compact.any():
            raw = raw.astype(object).copy()
            raw[compact] = num[compact].astype("int64").astype(str)
        df["observation_date"] = pd.to_datetime(
            raw, errors="coerce", format="mixed", utc=True
        )
    else:
        df["observation_date"] = pd.NaT
    df["price"] = df.apply(lambda r: parse_price(r["price"], r.get("currency")), axis=1)
    # Shards carry input_hash already; it is a pure function of the raw row, so
    # recomputing it here would hash 20M rows a second time for the same answer.
    if "input_hash" not in df.columns or df["input_hash"].isna().any():
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

    return df


def _aggregate(df: pd.DataFrame) -> pd.DataFrame:
    agg = dict(
        product_name_original=("product_name_original", "first"),
        product_url=("product_url", _first_non_empty),
        category=("category", _first_non_empty),
        details=("details", _first_non_empty),
        unit=("unit", _first_non_empty),
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


def prepare_input(raw: pd.DataFrame) -> pd.DataFrame:
    return _aggregate(_derive(raw))


SHUFFLE_BUCKETS = 64
CHUNK_ROWS = 2_000_000


def prepare_input_streaming(
    chunks,
    out_path: Path,
    shuffle_dir: Optional[Path] = None,
    n_buckets: int = SHUFFLE_BUCKETS,
    verbose: bool = True,
) -> int:
    """Chunked `prepare_input` that never holds the corpus in memory.

    Reading raw_prices.csv whole costs ~1 GB per million rows; at corpus scale
    that is tens of GB, which does not fit. The work is split in two passes.

    Pass 1 derives each chunk (row-wise: price parsing, url cleaning, lang, and
    `input_hash`) and shards it to disk by `input_hash`, so every row sharing an
    input_hash lands in the SAME bucket. Pass 2 then runs `_aggregate` on one
    whole bucket at a time.

    That partitioning is the whole point: it means `_aggregate` is reused
    VERBATIM. `price=median` and `_modal_or_empty` do not decompose across
    arbitrary chunks, but they need no special handling here because each group
    is never split across buckets.

    Returns the number of output rows. Writes `out_path` incrementally.
    """
    import pyarrow as pa
    import pyarrow.parquet as pq

    shuffle_dir = (
        Path(shuffle_dir) if shuffle_dir else config.ENRICH_DIR / "_prepare_shuffle"
    )
    shuffle_dir.mkdir(parents=True, exist_ok=True)
    for stale in shuffle_dir.glob("part_*.parquet"):
        stale.unlink()

    n_in = 0
    for i, chunk in enumerate(chunks):
        derived = _derive(chunk)
        n_in += len(derived)
        bucket = derived["input_hash"].str[:2].map(lambda h: int(h, 16) % n_buckets)
        for b, part in derived.groupby(bucket, sort=False):
            part.to_parquet(shuffle_dir / f"part_{b:03d}_{i:04d}.parquet", index=False)
        if verbose:
            print(
                f"  [prepare] pass1 chunk {i}: {len(derived)} rows (total {n_in})",
                flush=True,
            )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    writer = None
    schema = None
    n_out = 0
    try:
        for b in range(n_buckets):
            files = sorted(shuffle_dir.glob(f"part_{b:03d}_*.parquet"))
            if not files:
                continue
            df = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
            agg = _aggregate(df)
            n_out += len(agg)
            table = pa.Table.from_pandas(agg, preserve_index=False)
            if writer is None:
                schema = table.schema
                writer = pq.ParquetWriter(out_path, schema)
            else:
                # Pin the first bucket's schema. A bucket whose price or
                # observation_date happens to be entirely null would otherwise
                # infer a null column type and fail the append.
                table = table.cast(schema)
            writer.write_table(table)
            for f in files:
                f.unlink()
            if verbose:
                print(
                    f"  [prepare] pass2 bucket {b}: {len(df)} rows -> {len(agg)} products",
                    flush=True,
                )
    finally:
        if writer is not None:
            writer.close()
    if verbose:
        print(f"  [prepare] {n_in} raw rows -> {n_out} products", flush=True)
    return n_out


def run(
    csv_path: Optional[Path] = None,
    out_path: Optional[Path] = None,
    chunk_rows: int = CHUNK_ROWS,
) -> int:
    csv_path = csv_path or config.RAW_PRICES_CSV
    out_path = out_path or config.PRODUCTS_INPUT_PARQUET
    # dtype={"price": str} pins the column so every chunk takes the SAME code
    # path in parse_price regardless of what else shares its 2M-row window --
    # left to inference, a chunk that happens to be all-numeric reads "price"
    # as float64 (parse_price's early-return branch) while a chunk sharing the
    # window with even one non-numeric row reads it as object/str (the regex
    # branch). Both branches are correct on their own, but the split made the
    # SAME raw value parse differently build-to-build depending on chunk
    # placement. Plain `str` (not pandas' nullable "string" dtype) so memory
    # stays at ordinary object-column cost on a 33 GB CSV.
    chunks = pd.read_csv(
        csv_path, low_memory=False, chunksize=chunk_rows, dtype={"price": str}
    )
    return prepare_input_streaming(chunks, out_path)
