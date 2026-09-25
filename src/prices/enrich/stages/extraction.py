"""Extraction as its own stage, so a regex edit stops re-running the model.

`decide_rows` is roughly half regex extraction and half scoring, and its own
docstring measures the extraction half at ~68 minutes over 43.1M rows: one
pass of the C regex engine per pattern per name across ~68 patterns at
~10.5k rows/s on one core. Extraction and scoring are siblings in a DAG, not
a chain -- nothing extraction produces is read by the scorer, and nothing the
scorer produces is read by extraction. Fused, changing either recomputes
both. Split, each rung reuses the other's output.

`_structural_fields` and its three constants were MOVED here verbatim from
`stages/classify.py`, not copied. Two live definitions of one rule is the bug
class that produced the `input_hash` drift, where `prepare._row_input_dict`
and `shards.input_hashes` had to be kept in step by hand. classify now
imports this one.

**The freshness key hashes the extraction code, not the repo.** Every other
stage keys on input mtimes, which is right for them and wrong here: a regex
edit changes no input file, so an mtime key would silently serve a stale
table -- the exact defect `concatenate._signature` has. Keying on the whole
repo is the opposite error, making an unrelated commit cost 68 minutes. The
surface is the four extract modules, the `regex_patterns` tree and its vocab
YAMLs. `__pycache__` is excluded: `.pyc` files are rewritten by the
interpreter, so including them would invalidate the table on every run.

The grain is **(input_hash, country)**, not `input_hash` alone. Post-fold the
hash carries `source` but not `country` for rows that have a URL, so one
product URL sold into two countries is one hash and two rows. Measured on the
47,493,743-row production table: **8,339 hashes span more than one country**
(0.0176%). Keying on the hash alone drops one row of each pair at the join --
rare enough to pass every smoke test and never be noticed.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import replace
from pathlib import Path
from typing import Iterable, Optional, Sequence

import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from prices.enrich import config
from prices.enrich.declared_unit import parse_declared_count, parse_declared_unit
from prices.enrich.extract import StructuralFields, extract
from prices.enrich.regex_patterns.dict_view import pattern_set
from prices.enrich.stages import decisions_store, products_reader

_QTY_BASES = frozenset({"mass", "volume", "length", "count"})
# A parsed measure, as opposed to a bare piece count. `count` basis is excluded
# on purpose below: there the count IS the quantity and already scales the
# denominator, so promoting it would double-count.
_MEASURED_BASES = frozenset({"mass", "volume", "length"})


def _structural_fields(
    name, category, country, lang, details=None, unit=None, source=None
) -> dict:
    sf = extract(
        str(name), category or None, country or None, lang or None, source or None
    )
    # Quantity fallback: some sources (e.g. pickaroo, aldi_au) publish the pack
    # size in a separate `details` string ("~500 g", "10 pcs") the product_name
    # omits, so the name alone resolves to `item`. When that happens, read the
    # quantity off `details`; keep the name's promo/bundle flags.
    qs = sf
    if sf.pricing_basis == "item" and details and str(details).strip():
        sf2 = extract(
            str(details), category or None, country or None, lang or None, source or None
        )
        if sf2.pricing_basis in _QTY_BASES:
            qs = sf2
    # Second fallback: a fetcher-declared `unit` (e.g. agmarknet's "quintal
    # (100 kg)") is the last resort, only when name and details found no
    # quantity at all -- a per-row regex match on the name is more specific
    # evidence than a source-level sale-unit declaration. This also makes the
    # declared unit take precedence over the build-time `derived_typical`
    # leaf-average guess, since that guess only ever applies to rows still
    # carrying pricing_basis="item" by the time they reach the build.
    unit_declared = False
    if qs.pricing_basis == "item" and unit and str(unit).strip():
        basis, amount, su = parse_declared_unit(unit)
        declared_count = None if basis is not None else parse_declared_count(unit)
        # A countable declared unit ("each", "30 pcs", "Dozen") states the
        # denominator in PIECES, and `merge.compute_unit_value` divides a
        # count-basis row by `count * multiplier` and never by `amount_value`
        # -- so it fills `count` and leaves `amount_value` empty, which is the
        # same shape `extract_decide._finish` emits for a pack count read off
        # the name. Without it the row keeps `item` basis and the build's
        # `qa_quantity` gate quarantines it as `review_missing_qty` on every
        # leaf outside `SOLD_BY_ITEM_LEAVES`, however explicitly the source
        # said the price was per piece.
        if basis is not None or declared_count is not None:
            qs = StructuralFields(
                pricing_basis=basis if basis is not None else "count",
                amount_value=amount,
                standard_unit=su if basis is not None else "unit",
                count=qs.count if basis is not None else declared_count,
                multiplier=qs.multiplier,
                is_promotion=qs.is_promotion,
                is_bundle=qs.is_bundle,
                is_multipack=qs.is_multipack,
                promo_reason=qs.promo_reason,
            )
            unit_declared = True
    # A source-patch flag (regex_patterns/source/<source>/patch.py): the
    # trailing "(N pieces)" is a wholesale case, so N multiplies the measure.
    piece_is_case = (
        "piece_is_case" in pattern_set(source).flags
        and qs.pricing_basis in _MEASURED_BASES
        and qs.multiplier == 1
        and qs.count is not None
        and qs.count > 1
    )
    if piece_is_case:
        qs = replace(qs, count=1, multiplier=qs.count)
    return {
        "pricing_basis": qs.pricing_basis,
        "amount_value": qs.amount_value,
        "standard_unit": qs.standard_unit,
        "count": qs.count,
        "multiplier": qs.multiplier,
        "is_promotion": sf.is_promotion,
        "is_bundle": sf.is_bundle,
        "is_multipack": sf.is_multipack or piece_is_case,
        "promo_reason": sf.promo_reason,
        "unit_declared": unit_declared,
    }


# The columns extraction owns. `source` rides along so the table can be
# partitioned and scoped without a join back to the 8 GB products_input, the
# same reason `country` is carried on decisions.
EXTRACTION_FIELDS = [
    "pricing_basis",
    "amount_value",
    "standard_unit",
    "count",
    "multiplier",
    "is_promotion",
    "is_bundle",
    "is_multipack",
    "promo_reason",
    "unit_declared",
]
EXTRACTION_COLS = ["input_hash", "country", "source", *EXTRACTION_FIELDS]

# Declared, never inferred, for the reason the decisions writer states: a
# chunk whose `promo_reason` is entirely null infers arrow type `null`, and
# the first later chunk carrying a real string fails to cast, hours in.
_EXTRACTION_TYPES = {
    "input_hash": pa.string(),
    "country": pa.string(),
    "source": pa.string(),
    "pricing_basis": pa.string(),
    "amount_value": pa.float64(),
    "standard_unit": pa.string(),
    "count": pa.float64(),
    "multiplier": pa.float64(),
    "is_promotion": pa.bool_(),
    "is_bundle": pa.bool_(),
    "is_multipack": pa.bool_(),
    "promo_reason": pa.string(),
    "unit_declared": pa.bool_(),
}
_uncovered = [c for c in EXTRACTION_COLS if c not in _EXTRACTION_TYPES]
if _uncovered:  # the field list grew -- extend _EXTRACTION_TYPES deliberately
    raise RuntimeError(f"no arrow type declared for extraction columns: {_uncovered}")
EXTRACTION_SCHEMA = pa.schema([(c, _EXTRACTION_TYPES[c]) for c in EXTRACTION_COLS])

_ENRICH_DIR = Path(__file__).resolve().parents[1]
# Everything whose edit can change an extracted value.
_CODE_FILES = (
    "extract.py",
    "extract_patterns.py",
    "extract_decide.py",
    "declared_unit.py",
)
_CODE_TREES = ("regex_patterns",)
# Source patches are keyed per source (`source_patch_hashes`), not globally:
# in the global key, a one-line tiki fix would restale all 48.5M rows.
_SOURCE_PATCH_DIR = _ENRICH_DIR / "regex_patterns" / "source"


def _code_files(tree: Path) -> list[Path]:
    # .pyc is rewritten by the interpreter, so including it would invalidate
    # the table on every run and defeat the whole key.
    return [
        p for p in sorted(tree.rglob("*"))
        if p.is_file() and "__pycache__" not in p.parts
    ]


def _fingerprint_paths() -> list[Path]:
    paths = [_ENRICH_DIR / name for name in _CODE_FILES]
    for tree in _CODE_TREES:
        for p in _code_files(_ENRICH_DIR / tree):
            if p.parent != _SOURCE_PATCH_DIR and _SOURCE_PATCH_DIR in p.parents:
                continue  # inside source/<slug>/
            paths.append(p)
    return [p for p in paths if p.is_file()]


def source_patch_hashes() -> dict[str, str]:
    """`{source: content hash}` for every source that has a patch directory."""
    out = {}
    if not _SOURCE_PATCH_DIR.is_dir():
        return out
    for d in sorted(_SOURCE_PATCH_DIR.iterdir()):
        if not d.is_dir() or d.name == "__pycache__":
            continue
        h = hashlib.sha256()
        for p in _code_files(d):
            h.update(str(p.relative_to(d)).encode())
            h.update(p.read_bytes())
        out[d.name] = h.hexdigest()[:16]
    return out


def code_fingerprint() -> str:
    """Hash of the extraction code, as the stage's freshness key.

    Content, not mtime: a checkout or a touch must not re-run 68 minutes, and
    a one-character regex edit must.
    """
    h = hashlib.sha256()
    for path in sorted(_fingerprint_paths()):
        h.update(str(path.relative_to(_ENRICH_DIR)).encode())
        h.update(path.read_bytes())
    return h.hexdigest()[:16]


def extract_frame(products: pd.DataFrame) -> pd.DataFrame:
    """Run extraction over a products_input frame, one row in, one row out.

    Deliberately row-wise rather than vectorised: this is the same loop
    `decide_rows` runs, and the split has to be byte-identical before the
    vocabulary work changes any value.
    """
    cols = ("product_name_original", "category", "country", "lang", "details",
            "unit", "source", "input_hash")
    have = {c: (products[c].to_numpy(dtype=object) if c in products.columns
                else [None] * len(products)) for c in cols}
    rows = []
    for i in range(len(products)):
        country = have["country"][i]
        source = have["source"][i]
        row = {
            "input_hash": have["input_hash"][i],
            "country": None if country is None or pd.isna(country) else str(country),
            "source": None if source is None or pd.isna(source) else str(source),
        }
        row.update(
            _structural_fields(
                str(have["product_name_original"][i]),
                have["category"][i],
                have["country"][i],
                have["lang"][i],
                have["details"][i],
                have["unit"][i],
                have["source"][i],
            )
        )
        rows.append(row)
    return pd.DataFrame(rows, columns=EXTRACTION_COLS)


# ── Layout: <root>/<country>/<source>.parquet ──────────────────────────────
#
# Country outer, source inner (spec Q13). Per-source freshness then means
# "rewrite one source's files", never a read-modify-write of a whole country
# part (a rakuten edit would otherwise rewrite Japan's file). Country stays the
# outer level because per-country readers would otherwise open ~2,111 files:
# 7 sources span more than one country. The layout is extraction's own;
# `decisions_store` keeps the flat per-country layout the classify output uses.
#
# Rows reach the stage in products_input order, not grouped by source, and one
# open writer per (country, source) would pass the 1,024-descriptor limit. So a
# run still stages one part per country beside the root and splits each staged
# part into its source files at the end.


def _staging_root(root: Path) -> Path:
    return root.with_name(root.name + ".staging")


def nest_part(part: Path, country_dir: Path) -> dict[str, Path]:
    """Split one flat country part into `<country_dir>/<source>.parquet`.

    Every source in the part is written whole, each file via `.tmp` + rename;
    row order within a source is kept. Returns `{source file stem: path}`.
    """
    table = pq.read_table(part)
    col = table.column("source")
    by_stem: dict[str, object] = {}
    for src in pc.unique(col).to_pylist():
        stem = decisions_store.part_name(src)
        if stem in by_stem:  # two source names sanitising to one filename
            raise RuntimeError(
                f"{part}: sources {by_stem[stem]!r} and {src!r} share file stem {stem!r}"
            )
        by_stem[stem] = src
    country_dir.mkdir(parents=True, exist_ok=True)
    written = {}
    for stem, src in by_stem.items():
        mask = pc.is_null(col) if src is None else pc.equal(col, src)
        final = country_dir / f"{stem}.parquet"
        tmp = final.with_name(final.name + ".tmp")
        pq.write_table(table.filter(mask), tmp)
        tmp.replace(final)
        written[stem] = final
    return written


def _prune_nested(root: Path, scope, written: dict[str, set[str]]) -> None:
    """Drop source files this run was responsible for but did not write.

    A full run owns everything; a scoped run owns only the countries it took
    whole and the named sources of the ones it took in part -- nothing outside
    its scope is touched. A source file this run owned and wrote nothing for is
    empty now, not untouched, and keeping it would serve last run's rows.
    """
    if scope is None:
        owned = {d.name: None for d in root.iterdir() if d.is_dir()}
    else:
        owned = {
            decisions_store.part_name(c): (
                None if srcs is None else {decisions_store.part_name(s) for s in srcs}
            )
            for c, srcs in scope.items()
        }
    for country, stems in owned.items():
        cdir = root / country
        if not cdir.is_dir():
            continue
        keep = written.get(country, set())
        for f in cdir.glob("*.parquet"):
            if f.stem not in keep and (stems is None or f.stem in stems):
                f.unlink()
        if not any(cdir.iterdir()):
            cdir.rmdir()


def part_files(root: Path, countries: Optional[Iterable[str]] = None) -> list[Path]:
    """Every source file, optionally only those of `countries`."""
    root = Path(root)
    if not root.is_dir():
        return []
    if countries is None:
        return sorted(root.glob("*/*.parquet"))
    wanted = {decisions_store.part_name(c) for c in countries}
    return sorted(p for p in root.glob("*/*.parquet") if p.parent.name in wanted)


def read(
    path: Optional[Path] = None,
    columns: Optional[Sequence[str]] = None,
    countries: Optional[Iterable[str]] = None,
) -> pd.DataFrame:
    """The extraction table (or the named countries of it) as one frame."""
    root = decisions_store.parts_root(path or config.EXTRACTION_PARQUET)
    paths = part_files(root, countries)
    if not paths:
        return pd.DataFrame(columns=list(columns) if columns else None)
    return pd.concat(
        [pd.read_parquet(p, columns=columns) for p in paths], ignore_index=True
    )


def row_count(path: Optional[Path] = None) -> int:
    root = decisions_store.parts_root(path or config.EXTRACTION_PARQUET)
    return sum(pq.ParquetFile(p).metadata.num_rows for p in part_files(root))


def _state_path(out_path: Path) -> Path:
    """The freshness key, beside the parts directory and never inside it.

    Inside, a full run's `prune` would have to learn to spare it. Outside, the
    two cannot interact at all.
    """
    root = decisions_store.parts_root(out_path)
    return root.with_name(root.name + ".state.json")


def _read_state(out_path: Path) -> dict:
    try:
        state = json.loads(_state_path(out_path).read_text())
    except (OSError, ValueError):
        return {}
    return state if isinstance(state, dict) else {}


def _scope_of_sources(in_path: Path, sources: Sequence[str]) -> dict:
    """`{country: frozenset(sources)}` covering every row of `sources`."""
    import pyarrow.dataset as pads

    keys = (
        pads.dataset(in_path)
        .to_table(columns=["country", "source"], filter=pads.field("source").isin(list(sources)))
        .to_pandas()
        .drop_duplicates()
    )
    return {
        country: frozenset(grp["source"])
        for country, grp in keys.groupby("country", dropna=False)
    }


def run(
    in_path: Optional[Path] = None,
    out_path: Optional[Path] = None,
    selectors: Optional[Sequence[str]] = None,
    shard_root: Optional[Path] = None,
    chunk_rows: int = 500_000,
    force: bool = False,
) -> dict:
    """Extract structural fields for every product into a standalone table.

    Freshness is `code_fingerprint()`, so a regex edit re-runs and an unrelated
    commit does not -- see the module docstring for why an mtime key is the
    wrong one here.

    **Only an UNSCOPED run stamps that key.** A scoped run has read one source
    and knows nothing about the countries it never opened, so letting it write
    the fingerprint would mark the whole table current on the strength of a few
    hundred rows -- the same confusion between "what I looked at" and "what is
    true" that the CC ledger's filename rule made.

    The one exception is a source patch (`regex_patterns/source/<source>/`),
    keyed per source in the same state file: when the shared code is current
    and only patches changed, an unscoped run re-extracts just those sources
    and stamps the table, because every other source is known current.
    """
    # Imported here, not at module scope: classify imports THIS module for
    # `_structural_fields`, so a top-level import back into classify is a cycle.
    from prices.enrich.stages import classify

    in_path = in_path or config.PRODUCTS_INPUT_PARQUET
    out_path = out_path or config.EXTRACTION_PARQUET
    root = decisions_store.parts_root(out_path)
    scope = classify.scope_for(selectors, shard_root)
    fingerprint = code_fingerprint()
    patches = source_patch_hashes()
    state = _read_state(out_path)
    stamp = scope is None
    refreshed: list[str] = []

    if not force and scope is None and root.is_dir() and state.get("fingerprint") == fingerprint:
        # Shared code unchanged: only sources whose patch changed (added,
        # edited or deleted) are stale. Re-extract exactly those and stamp the
        # table current -- every other source is already current.
        done = state.get("sources", {})
        refreshed = sorted(s for s in patches.keys() | done.keys() if patches.get(s) != done.get(s))
        if not refreshed:
            return {
                "rows": row_count(out_path),
                "countries": sum(1 for d in root.iterdir() if d.is_dir()),
                "fingerprint": fingerprint,
                "skipped": True,
            }
        scope = _scope_of_sources(in_path, refreshed)

    # Every source this run reads it reads WHOLE (a scope never splits a
    # source within a country), so each source file is replaced outright and
    # nothing has to be merged into.
    staging = _staging_root(root)
    shutil.rmtree(staging, ignore_errors=True)
    writer = decisions_store.PartitionedWriter(staging, EXTRACTION_SCHEMA)
    rows = 0
    try:
        for chunk in products_reader.iter_products(in_path, chunk_rows, scope=scope):
            frame = extract_frame(chunk)
            writer.write(frame)
            rows += len(frame)
        staged = writer.close()
    except BaseException:
        # Publish nothing on the way out: a half-written part reads exactly
        # like a complete one.
        writer.abort()
        shutil.rmtree(staging, ignore_errors=True)
        raise

    root.mkdir(parents=True, exist_ok=True)
    written: dict[str, set[str]] = {}
    for part in staged:
        written[part.stem] = set(nest_part(part, root / part.stem))
    shutil.rmtree(staging, ignore_errors=True)
    _prune_nested(root, scope, written)
    if stamp:
        _state_path(out_path).write_text(
            json.dumps({"fingerprint": fingerprint, "sources": patches})
        )

    return {
        "rows": rows,
        "countries": len(written),
        "fingerprint": fingerprint,
        "skipped": False,
        "refreshed": refreshed,
    }
