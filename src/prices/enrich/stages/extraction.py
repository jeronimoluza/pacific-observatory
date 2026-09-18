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
from dataclasses import replace
from pathlib import Path
from typing import Iterable

import pandas as pd
import pyarrow as pa

from prices.enrich.declared_unit import parse_declared_count, parse_declared_unit
from prices.enrich.extract import StructuralFields, extract

_QTY_BASES = frozenset({"mass", "volume", "length", "count"})
# A parsed measure, as opposed to a bare piece count. `count` basis is excluded
# on purpose below: there the count IS the quantity and already scales the
# denominator, so promoting it would double-count.
_MEASURED_BASES = frozenset({"mass", "volume", "length"})

# Sources whose trailing "(N pieces)" is a wholesale CASE size rather than a
# breakdown of the stated measure: the measure describes ONE unit and N of them
# ship together, so N multiplies the denominator. Verified per source, never
# assumed -- mangusa_cw is a bulk hypermarket whose own manifest records the
# convention ("Unoli Canola oil 2ltr (6 pieces)" at XCG 84.10, which is a case
# price: as a lone 2L bottle it implies ~$23/L of canola oil). Volume basis was
# already right (volume always multiplies); mass basis was not, and priced a
# whole case as one piece. Other sources using the same phrasing are NOT listed
# here -- the identical words mean pack-total at some of them, so each one has
# to be checked on its own evidence before it is added.
_PIECE_IS_CASE_SOURCES = frozenset({"mangusa_cw"})


def _structural_fields(
    name, category, country, lang, details=None, unit=None, source=None
) -> dict:
    sf = extract(str(name), category or None, country or None, lang or None)
    # Quantity fallback: some sources (e.g. pickaroo, aldi_au) publish the pack
    # size in a separate `details` string ("~500 g", "10 pcs") the product_name
    # omits, so the name alone resolves to `item`. When that happens, read the
    # quantity off `details`; keep the name's promo/bundle flags.
    qs = sf
    if sf.pricing_basis == "item" and details and str(details).strip():
        sf2 = extract(str(details), category or None, country or None, lang or None)
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
    piece_is_case = (
        source in _PIECE_IS_CASE_SOURCES
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


def _fingerprint_paths() -> list[Path]:
    paths = [_ENRICH_DIR / name for name in _CODE_FILES]
    for tree in _CODE_TREES:
        for p in sorted((_ENRICH_DIR / tree).rglob("*")):
            # .pyc is rewritten by the interpreter, so including it would
            # invalidate the table on every run and defeat the whole key.
            if p.is_file() and "__pycache__" not in p.parts:
                paths.append(p)
    return [p for p in paths if p.is_file()]


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
