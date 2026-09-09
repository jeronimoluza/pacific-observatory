"""Concatenate raw price artifacts into outputs/prices/raw/raw_prices.csv.

Walks data/prices/<region>/<subregion>/<country>/<source>/ for three on-disk
shapes and emits one CSV per source dir, then concatenates them into
raw_prices.csv. A sidecar tracks per-source (max_mtime, file_count) so
unchanged sources are skipped on re-runs.

Shapes handled:
  - raw_items/*.jsonl                  (Scrapy)
  - wayback_items/*.jsonl              (Wayback Machine)
  - common_crawl_data/items/*.json     (Common Crawl, one product per file)

Output schema (16 cols, raw-only — no enrichment-derived columns):
  url_hash, product_name, price, currency, country, source, date,
  product_url, product_id, region, subregion, wayback, channel, category,
  details, unit

`channel` is per-row, looked up from the source YAML's `channel:` field at
startup. `category` is the per-item breadcrumb captured by Scrapy spiders
(`ProductItem.category`). `details` is the per-item size/pack string some
spiders capture separately from the name (e.g. pickaroo "~500 g"); it carries
the quantity the product_name omits and is consulted by the structural
extractor as a fallback. `unit` is the fetcher-declared sale unit from a
price_observations.csv ("quintal (100 kg)", "kg"): for a commodity feed whose
item name is a bare noun it is the only quantity in the row, and `prepare`,
`products_input.parquet` and `classify`'s `unit_declared` fallback have all
carried it for some time -- this stage was the one link that dropped it. All
default to "" when absent.

Rows whose `available` field is an explicit JSON `false` are dropped before the
column projection (which does not carry the flag). An out-of-stock offer is not
a price anyone can pay, and on VTEX tenants it is usually a delisted SKU whose
price has been frozen for years — the Cencosud AR banners served ~95% of their
feed that way, which is where 36% of their rows came in under 100 ARS. A
missing, null, or non-boolean `available` is unknown availability, never
unavailability: most spiders never emit the field at all.

product_name_original is NOT emitted here — prepare derives it. Currency for
Common Crawl rows (which often lack a currency field) is back-filled with the
modal currency observed in the same source's jsonl rows; rows with no
resolvable currency are dropped.

A source is built in two streaming passes over a temporary spill file rather
than accumulated whole. The modal back-fill is the reason there are two: it
needs a count over every non-empty currency in the source before any row can be
finalised, so nothing can be written until the last file has been read. Holding
the source as a list of dicts to bridge that gap made peak memory one whole
source — 19.4M rows for yahoo_shopping, 38.5M once the Common Crawl ingest
lands — on a 26 GB box. Pass 1 streams the emitters into the spill and pass 2
streams it back, so peak memory is one batch either way. The spill costs one
extra Parquet round-trip; re-reading the source's 8,160 gzipped inputs a second
time to pre-count currencies would cost a second JSON parse of all of it.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections import Counter
from itertools import batched
from pathlib import Path
from typing import Iterable, Iterator, Optional

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import yaml

from prices import partition
from prices.enrich import config, shards

logger = logging.getLogger(__name__)

DATA_PRICES_ROOT = config.REPO_ROOT / "data" / "prices"
RAW_OUT_DIR = config.REPO_ROOT / "outputs" / "prices" / "raw"
PER_SOURCE_DIR = RAW_OUT_DIR / "_per_source"
RAW_CSV = RAW_OUT_DIR / "raw_prices.csv"
STATE_FILE = RAW_OUT_DIR / ".state.json"

# Shards are Parquet: a CSV shard has no types, so every reader re-infers
# `price` from the file's own contents. See prices.enrich.shards.
SHARD_SUFFIX = ".parquet"

# The spill a source is streamed through, written beside its shard so both land
# on the same filesystem. Deliberately not `.parquet`: `partition.select` globs
# the shard tree for that suffix and would read a half-written spill as a shard.
SPILL_SUFFIX = ".spill"

# Rows per batch, in both passes. Bounds peak memory at one batch instead of
# one source.
BATCH_ROWS = 200_000

REQUIRED_COLS = ["product_name", "price", "currency", "country"]

OUTPUT_COLS = [
    "url_hash",
    "product_name",
    "price",
    "currency",
    "country",
    "source",
    "date",
    "product_url",
    "product_id",
    "region",
    "subregion",
    "wayback",
    "channel",
    "category",
    "details",
    "unit",
]

# The coicop_classification value that routes a fetcher manifest's rows into
# the classifier corpus (see _build_classifier_csv_map). Shared here so a
# future rename of the marker only needs one edit.
CLASSIFIER_MARKER = "classifier"


# Every column the emitters below can produce. `unit` and
# `declared_coicop_codes` come only from `_emit_price_obs`, so the emitters
# disagree about the key set; pinning the columns is what lets batches from
# different shapes share one spill schema.
#
# This tuple is a strict projection -- `_spill` builds each batch as
# `{col: ... for col in EMITTED_COLS}` -- so a key an emitter yields but that is
# missing here is dropped SILENTLY, with the column still present downstream and
# uniformly null. That is exactly how `declared_coicop_codes` was lost for all
# 6.14M WB RTDI rows: the emitter set it, this tuple did not list it, and the
# shards came out with the column full of None and no error anywhere. Anything
# added to an emitter must be added here too.
EMITTED_COLS = (
    "product_name",
    "price",
    "currency",
    "date",
    "product_url",
    "product_id",
    "url_hash",
    "category",
    "details",
    "unit",
    "declared_coicop_codes",
)

# `wayback` is the one non-text emitted column: the emitters set a real bool and
# never leave it null.
SPILL_SCHEMA = pa.schema(
    [pa.field(name, pa.string()) for name in EMITTED_COLS]
    + [pa.field("wayback", pa.bool_())]
)


_CHANNEL_MAP_CACHE: Optional[dict[tuple[str, str], str]] = None


def _build_source_channel_map() -> dict[tuple[str, str], str]:
    """Walk per-source YAMLs and return {(country, source): channel}. Missing
    or invalid channels are omitted; callers default to ``""``."""
    from prices.config import PriceSourceConfig, discover_prices_configs

    out: dict[tuple[str, str], str] = {}
    for path in discover_prices_configs():
        try:
            cfg = PriceSourceConfig.load(path)
        except Exception:  # malformed YAML or schema mismatch — skip silently
            continue
        if cfg.channel:
            out[(cfg.country, cfg.source)] = cfg.channel
    return out


_CLASSIFIER_CSV_MAP_CACHE: Optional[dict[tuple[str, str], str]] = None


def _build_classifier_csv_map() -> dict[tuple[str, str], str]:
    """Return {(country, source): channel} for ``scaffolding: fetcher`` sources
    whose COICOP is ``classifier`` — the fetcher price_observations.csv rows
    that belong in the classifier corpus (e.g. wholesale live-animals). Keyed by
    the config's path components (country dir, filename stem) to match the data
    walk. Read via raw YAML because PriceSourceConfig rejects fetcher manifests."""
    out: dict[tuple[str, str], str] = {}
    cfg_root = config.REPO_ROOT / "src" / "prices" / "configs"
    if not cfg_root.is_dir():
        return out
    for path in cfg_root.rglob("*.yaml"):
        try:
            y = yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception:  # malformed YAML — skip silently
            continue
        if not isinstance(y, dict):
            continue
        if (
            y.get("coicop_classification") == CLASSIFIER_MARKER
            and y.get("scaffolding") == "fetcher"
        ):
            out[(path.parent.name, path.stem)] = y.get("channel") or ""
    return out


def _classifier_csv_map() -> dict[tuple[str, str], str]:
    global _CLASSIFIER_CSV_MAP_CACHE
    if _CLASSIFIER_CSV_MAP_CACHE is None:
        _CLASSIFIER_CSV_MAP_CACHE = _build_classifier_csv_map()
    return _CLASSIFIER_CSV_MAP_CACHE


def _channel_for(country: str, source: str) -> str:
    global _CHANNEL_MAP_CACHE
    if _CHANNEL_MAP_CACHE is None:
        _CHANNEL_MAP_CACHE = _build_source_channel_map()
    ch = _CHANNEL_MAP_CACHE.get((country, source))
    if ch:
        return ch
    return _classifier_csv_map().get((country, source), "")


def _url_hash(url: Optional[str]) -> Optional[str]:
    if not url or not isinstance(url, str):
        return None
    return hashlib.md5(url.encode("utf-8")).hexdigest()


def _is_out_of_stock(obj: dict) -> bool:
    """True only for an explicit JSON ``false``.

    Absent, null, and non-boolean values all mean "unknown" and are kept: the
    field is optional and most spiders never emit it, so reading missing as
    unavailable would delete most of the corpus."""
    return obj.get("available") is False


def _emit_jsonl(path: Path, wayback: bool, stats: Counter) -> Iterable[dict]:
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if _is_out_of_stock(obj):
                stats["out_of_stock"] += 1
                continue
            yield {
                "product_name": obj.get("product_name"),
                "price": obj.get("price"),
                "currency": obj.get("currency"),
                "date": obj.get("scraped_at_utc") or obj.get("scraped_at"),
                "product_url": obj.get("url"),
                "product_id": obj.get("product_id"),
                "url_hash": obj.get("url_hash") or _url_hash(obj.get("url")),
                "wayback": wayback,
                "category": obj.get("category") or "",
                "details": obj.get("details") or "",
            }


def _emit_cc(path: Path, stats: Counter) -> Iterable[dict]:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return
    row = _cc_row(obj, stats)
    if row is not None:
        yield row


def _emit_cc_jsonl(path: Path, stats: Counter) -> Iterable[dict]:
    from prices.cc_storage import iter_jsonl

    for obj in iter_jsonl(path):
        row = _cc_row(obj, stats)
        if row is not None:
            yield row


def _cc_row(obj: dict, stats: Counter) -> Optional[dict]:
    if _is_out_of_stock(obj):
        stats["out_of_stock"] += 1
        return None
    return {
        "product_name": obj.get("product_name"),
        "price": obj.get("price"),
        "currency": obj.get("currency"),
        "date": obj.get("cc_timestamp") or obj.get("scraped_at"),
        "product_url": obj.get("url"),
        "product_id": obj.get("product_id"),
        "url_hash": _url_hash(obj.get("url")),
        "wayback": False,
        "category": obj.get("category") or "",
        "details": obj.get("details") or "",
    }


def _emit_price_obs(path: Path) -> Iterable[dict]:
    """Map a fetcher price_observations.csv row to the corpus schema. The item
    name is the product; the observation hash gives a stable url_hash."""
    try:
        df = pd.read_csv(path, low_memory=False)
    except Exception:  # noqa: BLE001 — unreadable CSV
        return
    for r in df.to_dict("records"):
        name = r.get("item_name")
        if not isinstance(name, str) or not name.strip():
            continue
        yield {
            "product_name": name,
            "price": r.get("price_local"),
            "currency": r.get("currency"),
            "date": r.get("observation_date"),
            "product_url": r.get("source_url"),
            "product_id": None,
            "url_hash": r.get("observation_hash") or _url_hash(r.get("source_url")),
            "wayback": False,
            "category": "",
            # The fetcher-declared sale unit ("quintal (100 kg)", "kg", "100
            # גרם"). For a commodity feed it is the ONLY statement of quantity
            # anywhere in the row -- the item name is a bare noun ("Ajwan",
            # "丝瓜") -- so dropping it here made `declared_unit.py` and
            # classify's `unit_declared` fallback dead code and left every such
            # row on pricing_basis="item".
            "unit": r.get("unit"),
            # A fetcher may carry a per-ITEM curated leaf (a lookup table in
            # its own code). The YAML `coicop_codes` field cannot express
            # that -- it is per-source, so it can only say "this whole feed
            # is one leaf", which is false for a multi-commodity feed.
            "declared_coicop_codes": r.get("coicop_code"),
        }


def _iter_source_files(
    source_dir: Path, country: Optional[str] = None, source: Optional[str] = None
) -> list[tuple[str, Path]]:
    """Return [(shape, path), ...] for all raw artifacts under a source dir.

    A fetcher's ``price_observations.csv`` is included only for sources declared
    ``classifier`` (see ``_classifier_csv_map``); tariff/fuel/telco fetchers
    are source-curated and must not enter the div-01 classifier corpus."""
    out: list[tuple[str, Path]] = []
    raw = source_dir / "raw_items"
    if raw.is_dir():
        out.extend(("jsonl", p) for p in raw.glob("*.jsonl"))
    wb = source_dir / "wayback_items"
    if wb.is_dir():
        out.extend(("wayback", p) for p in wb.glob("*.jsonl"))
    cc = source_dir / "common_crawl_data" / "items"
    if cc.is_dir():
        # Both layouts: one JSON per record (pre-compaction) and one JSONL per
        # crawl. A corpus captured before the change is still read in place.
        out.extend(("cc", p) for p in cc.glob("*.json"))
        out.extend(("cc_jsonl", p) for p in cc.glob("*.jsonl"))
    obs = source_dir / "price_observations.csv"
    if obs.is_file() and (country, source) in _classifier_csv_map():
        out.append(("price_obs", obs))
    return out


def _signature(files: list[tuple[str, Path]]) -> tuple[float, int]:
    if not files:
        return (0.0, 0)
    mtimes = [p.stat().st_mtime for _, p in files]
    return (max(mtimes), len(files))


def _iter_rows(files: list[tuple[str, Path]], stats: Counter) -> Iterator[dict]:
    """Every raw row of a source, in file order, one at a time."""
    for shape, path in files:
        if shape == "jsonl":
            yield from _emit_jsonl(path, False, stats)
        elif shape == "wayback":
            yield from _emit_jsonl(path, True, stats)
        elif shape == "cc":
            yield from _emit_cc(path, stats)
        elif shape == "cc_jsonl":
            yield from _emit_cc_jsonl(path, stats)
        elif shape == "price_obs":
            yield from _emit_price_obs(path)


def _text(value):
    """``str(value)``, with every null shape mapped to None.

    The same mapping `shards._as_text` applies, hoisted to the row level so a
    batch can be rendered without waiting for the rest of the source."""
    if value is None:
        return None
    if isinstance(value, float) and value != value:  # NaN, incl. numpy's
        return None
    return str(value)


def _as_text_column(series: pd.Series) -> pd.Series:
    if series.dtype == object and not series.isna().any():
        if pd.api.types.infer_dtype(series, skipna=True) in ("string", "empty"):
            # Already str-or-nothing, so str() is the identity. This is most of
            # the corpus and skipping the elementwise map here is worth the check.
            return series
    return series.map(_text)


class _ColumnTypes:
    """The dtype `pd.DataFrame(every_row)` would have inferred, per column.

    Batches are typed one at a time and pandas types a column from what it can
    see, so a column that is int64 in one batch is float64 over the whole source
    as soon as another batch holds a float or a null — and float64 renders 12 as
    "12.0" where int64 and object render it as "12". Recording the per-batch
    kinds is what lets pass 2 reproduce the whole-source rendering exactly."""

    def __init__(self) -> None:
        self.kinds: dict[str, set[str]] = {c: set() for c in EMITTED_COLS}
        self.has_null: dict[str, bool] = {c: False for c in EMITTED_COLS}

    def observe(self, frame: pd.DataFrame) -> None:
        for col in EMITTED_COLS:
            na = frame[col].isna()
            if na.any():
                self.has_null[col] = True
            if not na.all():
                # An all-null batch says nothing about the column's type: pandas
                # types it object here and float64 there depending on nothing.
                self.kinds[col].add(frame[col].dtype.kind)

    def float_columns(self) -> list[str]:
        return [
            col
            for col in EMITTED_COLS
            if self.kinds[col]
            and self.kinds[col] <= {"i", "u", "f"}
            and ("f" in self.kinds[col] or self.has_null[col])
        ]


def _as_float_text(series: pd.Series) -> pd.Series:
    """Re-render an all-numeric column's text the way float64 renders it.

    The `astype` is load-bearing: `to_numeric` reads a batch of all-integer text
    back as int64, which renders 13 as "13" — the very thing this exists to
    undo."""
    return pd.to_numeric(series, errors="coerce").astype("float64").map(_text)


def _spill_source(
    files: list[tuple[str, Path]], spill_path: Path, stats: Counter
) -> tuple[int, _ColumnTypes]:
    """Pass 1: stream every emitted row into `spill_path`, recording the types
    pandas inferred. Returns (rows written, types)."""
    n_rows = 0
    types = _ColumnTypes()
    columns = list(EMITTED_COLS) + ["wayback"]
    writer = pq.ParquetWriter(spill_path, SPILL_SCHEMA, compression="zstd")
    try:
        for batch in batched(_iter_rows(files, stats), BATCH_ROWS):
            frame = pd.DataFrame(list(batch), columns=columns)
            types.observe(frame)
            out = pd.DataFrame(
                {col: _as_text_column(frame[col]) for col in EMITTED_COLS}
            )
            out["wayback"] = frame["wayback"]
            writer.write_table(
                pa.Table.from_pandas(out, schema=SPILL_SCHEMA, preserve_index=False)
            )
            n_rows += len(batch)
    finally:
        writer.close()
    return n_rows, types


def _modal_currency(spill_path: Path, float_cols: list[str]) -> Optional[str]:
    """The most common non-empty currency in the source, counted in row order so
    a tie breaks on first appearance exactly as `Counter.most_common` did over
    the whole frame."""
    counter: Counter = Counter()
    for batch in pq.ParquetFile(spill_path).iter_batches(
        batch_size=BATCH_ROWS, columns=["currency"]
    ):
        series = batch.column(0).to_pandas()
        if "currency" in float_cols:
            series = _as_float_text(series)
        series = series[series.notna()]
        counter.update(series[series.str.len() > 0])
    if not counter:
        return None
    return counter.most_common(1)[0][0]


def _finalise_shard(
    spill_path: Path,
    shard_path: Path,
    float_cols: list[str],
    modal_currency: Optional[str],
    region: str,
    subregion: str,
    country: str,
    source: str,
) -> tuple[int, int]:
    """Pass 2: stream the spill back, apply the modal back-fill and the
    required-field screen, and write the shard. Returns (written, dropped)."""
    channel = _channel_for(country, source)
    n_rows = n_dropped = 0
    writer = None
    try:
        for batch in pq.ParquetFile(spill_path).iter_batches(batch_size=BATCH_ROWS):
            df = batch.to_pandas()
            for col in float_cols:
                df[col] = _as_float_text(df[col])

            # Back-fill currency for rows that lack it, using the modal currency
            # observed in this source's other rows.
            if modal_currency is not None:
                currency = df["currency"]
                df["currency"] = currency.where(
                    currency.notna() & (currency.str.len() > 0), modal_currency
                )

            df["country"] = country
            df["source"] = source
            df["region"] = region
            df["subregion"] = subregion
            df["channel"] = channel
            for col in ("category", "details", "unit"):
                df[col] = df[col].fillna("").astype(str)

            before = len(df)
            df = df.dropna(subset=REQUIRED_COLS)
            df = df[df["product_name"].astype(str).str.len() > 0]
            n_dropped += before - len(df)
            if df.empty:
                continue
            table = pa.Table.from_pandas(
                shards.coerce(df[OUTPUT_COLS]),
                schema=shards.SHARD_SCHEMA,
                preserve_index=False,
            )
            if writer is None:
                # Opened lazily so a source that screens out entirely leaves no
                # shard behind, exactly as returning None used to.
                shard_path.parent.mkdir(parents=True, exist_ok=True)
                writer = pq.ParquetWriter(
                    shard_path, shards.SHARD_SCHEMA, compression="zstd"
                )
            writer.write_table(table)
            n_rows += len(df)
    finally:
        if writer is not None:
            writer.close()
    return n_rows, n_dropped


def _write_source_shard(
    source_dir: Path,
    region: str,
    subregion: str,
    country: str,
    source: str,
    shard_path: Path,
    run_stats: Optional[Counter] = None,
) -> int:
    """Build one source's shard at `shard_path`. Returns the rows written; 0
    means nothing was written and no shard exists for this source."""
    files = _iter_source_files(source_dir, country, source)
    if not files:
        return 0
    stats: Counter = Counter()
    shard_path.parent.mkdir(parents=True, exist_ok=True)
    spill_path = shard_path.with_suffix(SPILL_SUFFIX)
    try:
        n_spilled, types = _spill_source(files, spill_path, stats)
        n_out_of_stock = stats["out_of_stock"]
        if n_out_of_stock:
            logger.info(
                "[concatenate] %s/%s: dropped %d out-of-stock rows",
                country,
                source,
                n_out_of_stock,
            )
            if run_stats is not None:
                run_stats["rows"] += n_out_of_stock
                run_stats["sources"] += 1
        if not n_spilled:
            return 0
        float_cols = types.float_columns()
        n_rows, n_dropped = _finalise_shard(
            spill_path,
            shard_path,
            float_cols,
            _modal_currency(spill_path, float_cols),
            region,
            subregion,
            country,
            source,
        )
    finally:
        spill_path.unlink(missing_ok=True)
    if n_dropped:
        logger.debug(
            "[%s/%s] dropped %d rows missing required fields",
            country,
            source,
            n_dropped,
        )
    return n_rows


def _walk_sources(root: Path):
    """Yield (region, subregion, country, source, source_dir) tuples."""
    for region_dir in sorted(
        p for p in root.iterdir() if p.is_dir() and not p.name.startswith("_")
    ):
        for sub_dir in sorted(p for p in region_dir.iterdir() if p.is_dir()):
            for country_dir in sorted(p for p in sub_dir.iterdir() if p.is_dir()):
                for source_dir in sorted(
                    p for p in country_dir.iterdir() if p.is_dir()
                ):
                    yield (
                        region_dir.name,
                        sub_dir.name,
                        country_dir.name,
                        source_dir.name,
                        source_dir,
                    )


def _load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except json.JSONDecodeError:
            logger.warning("state file %s is corrupt; ignoring", STATE_FILE)
    return {}


def _save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2, sort_keys=True))


def per_source_path(region: str, subregion: str, country: str, source: str) -> Path:
    return PER_SOURCE_DIR / region / subregion / country / f"{source}{SHARD_SUFFIX}"


def _write_monolith(shard_paths: list[Path]) -> int:
    """Stream the shards into raw_prices.csv one at a time.

    Opt-in — see `run`. Kept because it is the only artifact a caller outside
    this repo can read without pyarrow, and because `aggregate._observation_chunks`
    still falls back to it when no shard tree exists.

    This used to read all 1,164 shards into a list and `pd.concat` them, so the
    whole 33 GB corpus had to be resident to write a file nothing ever reads
    whole. Appending shard by shard bounds the footprint at the largest single
    source."""
    RAW_CSV.parent.mkdir(parents=True, exist_ok=True)
    n_rows = 0
    with RAW_CSV.open("w", newline="", encoding="utf-8") as fh:
        for i, path in enumerate(shard_paths):
            df = shards.read_shard(path)
            df.to_csv(fh, index=False, header=(i == 0))
            n_rows += len(df)
    return n_rows


def run(
    force: bool = False,
    write_monolith: bool = False,
    selectors: Optional[list[str]] = None,
) -> Path:
    """Refresh the per-source shards. `write_monolith` additionally writes the
    39.4 GB raw_prices.csv.

    It defaults off because every stage in the pipeline reads the shards:
    `prepare` is `prepare_shards.run` (cli.py:180), and
    `aggregate._observation_chunks` takes the CSV only when the shard tree is
    absent, which it is not. The two module-level readers left on
    `config.RAW_PRICES_CSV` are `prepare.run`, shadowed by `prepare_shards.run`
    at its only call site, and `merge.run`, which does an unchunked
    `pd.read_csv` of all 39.4 GB and cannot complete in this box's 26 GB. So the
    default run pays ~10 minutes and 39.4 GB of disk for a file no live caller
    consumes."""
    if not DATA_PRICES_ROOT.is_dir():
        raise FileNotFoundError(f"{DATA_PRICES_ROOT} not found")
    PER_SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    state = _load_state()
    new_state: dict = {}
    patterns = [partition.compile_selector(s) for s in selectors] if selectors else None

    n_total = n_refreshed = n_skipped = n_converted = 0
    run_stats: Counter = Counter()
    for region, subregion, country, source, source_dir in _walk_sources(
        DATA_PRICES_ROOT
    ):
        key = f"{region}/{subregion}/{country}/{source}"
        if patterns and not any(p.match(key) for p in patterns):
            # Out of scope, but its shard stays on disk and still feeds the
            # monolith — so carry its state forward, or the next unscoped run
            # would re-derive every source the selector happened to exclude.
            if key in state:
                new_state[key] = state[key]
            continue
        files = _iter_source_files(source_dir, country, source)
        if not files:
            continue
        n_total += 1
        sig = _signature(files)
        shard_path = per_source_path(region, subregion, country, source)

        prev = state.get(key)
        if not force and prev == list(sig):
            if shard_path.exists():
                new_state[key] = list(sig)
                n_skipped += 1
                continue
            # An unchanged source whose shard is still the old CSV: convert it
            # rather than re-walking its raw artifacts. Without this the format
            # change alone would re-derive all 1,164 sources from 43 GB of
            # scrape output, for no new data.
            legacy = shard_path.with_suffix(".csv")
            if legacy.exists():
                shards.write_shard(shards.read_shard(legacy), shard_path)
                new_state[key] = list(sig)
                n_converted += 1
                continue

        n_rows = _write_source_shard(
            source_dir,
            region,
            subregion,
            country,
            source,
            shard_path,
            run_stats=run_stats,
        )
        if not n_rows:
            continue
        new_state[key] = list(sig)
        n_refreshed += 1
        logger.info("[concatenate] %s: %d rows", key, n_rows)

    logger.info(
        "[concatenate] sources: %d total, %d refreshed, %d unchanged, %d converted",
        n_total,
        n_refreshed,
        n_skipped,
        n_converted,
    )
    if run_stats["rows"]:
        logger.info(
            "[concatenate] dropped %d out-of-stock rows across %d source(s)",
            run_stats["rows"],
            run_stats["sources"],
        )

    shard_paths = [s.path for s in partition.select(None, PER_SOURCE_DIR)]
    if not shard_paths:
        raise RuntimeError("no per-source shards produced — check data/prices/ layout")
    _save_state(new_state)

    if not write_monolith:
        return PER_SOURCE_DIR

    # Rebuilt whole whenever it is asked for, even when every source was
    # skipped, so an opted-in monolith is never partially stale.
    n_rows = _write_monolith(shard_paths)
    logger.info(
        "[concatenate] wrote %s (%d rows from %d sources)",
        RAW_CSV,
        n_rows,
        len(shard_paths),
    )
    return RAW_CSV


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )
    run()
