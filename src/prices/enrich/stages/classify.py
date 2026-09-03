"""Classify stage — assign each product a COICOP leaf plus structural fields.

Reads ``products_input`` (already one row per ``input_hash``) and runs the two
independent enrich jobs per unique product name:

  - structural regex extraction (``extract``) overlays pricing_basis / amount /
    count / multiplier / promo flags;
  - (embedding -> head) classification predicts the COICOP leaf, accepted only
    where the head's global confidence gate clears AND no trap veto fires.

Source-declared narrow COICOP codes bypass the classifier (structural extraction
still runs). A basis-audit (``audit.py``) withholds trust from accepted rows
whose extracted basis contradicts the leaf's denylist. Output is keyed by
``input_hash`` with ``merge.ENRICHMENT_COLS``, filtered to a single COICOP
division (default 01 — the EAP F&B PoC).
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Optional

import pandas as pd
import pyarrow as pa

from prices.enrich import audit, coicop_codes, coicop_taxonomy, config, uv_gate
from prices.enrich.classifier import batch_embed, embed_store, fb_filter
from prices.enrich.classifier.predict import load_predictor
from prices.enrich.declared_unit import parse_declared_unit
from prices.enrich.extract import StructuralFields, extract
from prices.enrich.stages.merge import ENRICHMENT_COLS

_EMPTY = {c: None for c in ENRICHMENT_COLS}


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
        if basis is not None:
            qs = StructuralFields(
                pricing_basis=basis,
                amount_value=amount,
                standard_unit=su,
                count=qs.count,
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


DECISION_COLS = [*ENRICHMENT_COLS, "input_hash", "leaf_top1", "gate_score"]

# Explicit arrow schema for the decisions writer. Inferring it from the first
# chunk is a trap: a chunk whose `promo_reason` or `coicop_code` happens to be
# entirely null infers arrow type `null`, and the first later chunk carrying a
# real string then fails to cast — hours into the run. Numerics are float64 here
# (not the view's int64) because rejected rows widen the population.
# `classified.parquet` is unaffected: it is written from pandas, so it keeps the
# dtypes it has always had.
_DECISION_TYPES = {
    "pricing_basis": pa.string(),
    "amount_value": pa.float64(),
    "standard_unit": pa.string(),
    "count": pa.float64(),
    "multiplier": pa.float64(),
    "coicop_code": pa.string(),
    "is_promotion": pa.bool_(),
    "is_bundle": pa.bool_(),
    "is_multipack": pa.bool_(),
    "uv_trusted": pa.bool_(),
    "unit_declared": pa.bool_(),
    "promo_reason": pa.string(),
    "confidence": pa.float64(),
    "state": pa.string(),
    "dimensions_json": pa.string(),
    "trust_level": pa.string(),
    "input_hash": pa.string(),
    "leaf_top1": pa.string(),
    "gate_score": pa.float64(),
}
_uncovered = [c for c in DECISION_COLS if c not in _DECISION_TYPES]
if _uncovered:  # ENRICHMENT_COLS grew — extend _DECISION_TYPES deliberately
    raise RuntimeError(f"no arrow type declared for decision columns: {_uncovered}")
DECISION_SCHEMA = pa.schema([(c, _DECISION_TYPES[c]) for c in DECISION_COLS])

# Only what the decision loop actually reads. products_input carries pricing and
# provenance columns too; at corpus scale projecting is worth several GB.
PRODUCT_COLS = [
    "input_hash",
    "product_name_original",
    "category",
    "country",
    "lang",
    "details",
    "unit",
    "declared_coicop_codes",
]


def _split_by_store_coverage(uniq) -> tuple[list[str], set[str]]:
    """Partition names into (embedded, unembedded) against the production store.

    The `gpu_bf16` blocks are `backend: "store"` — vectors built on a GPU box and
    shipped read-only, with no local encoder. `batch_embed._build_store` raises
    KeyError on the first hole, so a single name collected after the last embed
    run would abort a multi-hour pass. Screening here turns that into a reported
    row state instead.

    A name is usable only if EVERY production block has it, so the unembedded set
    is the union of the per-block misses. Uses `missing_keys` (keys-only), which
    reads ~10 ms/bucket instead of paging in vectors from a 118 GB store.
    """
    names = [str(n) for n in uniq]
    bucket_names = embed_store.buckets_for(names)
    missing: set[str] = set()
    for block in config.CLASSIFIER_EMBED_ENSEMBLE:
        for nm in embed_store.missing_keys(block["tag"], bucket_names).values():
            missing.update(nm)
    embedded = [n for n in names if n not in missing]
    return embedded, missing


def score_unique_names(products: pd.DataFrame, division, version=None):
    """Score every unique product name once. Returns the predictor plus the
    name->value maps and the unembedded set."""
    predictor = load_predictor(version)
    uniq = pd.Index(products["product_name_original"].astype(str).unique())

    # The cheap F&B pre-filter narrows the unique names to the in-scope division
    # so only survivors pay the ensemble embed. `division is None` means "all
    # divisions": skip it entirely rather than pay a vectorizer pass whose result
    # would be discarded.
    if division is not None:
        scoped = fb_filter.in_scope_names(uniq, division)
        uniq = pd.Index([n for n in uniq if n in scoped])

    embedded, unembedded = _split_by_store_coverage(uniq)
    if unembedded:
        print(
            f"[classify] {len(unembedded)} of {len(uniq)} unique names are not in the "
            f"embed store — recorded as state='unembedded', not scored",
            flush=True,
        )
    leaf_by, conf_by, ok_by, gate_by = batch_embed.embed_and_predict(
        predictor, pd.Index(embedded)
    )
    return leaf_by, conf_by, ok_by, gate_by, unembedded


def decide_rows(
    products: pd.DataFrame, leaf_by, conf_by, ok_by, gate_by, unembedded, key_fn=None
) -> pd.DataFrame:
    """One decision row per input_hash. Rejects and unembedded rows are RETAINED
    — they are the coverage denominator.

    The score maps are keyed by product name by default. `key_fn(row)` overrides
    that for a model scored at a finer grain — HierLex keys on (name, country),
    because country is one of its gate features. `unembedded` stays name-keyed
    either way: whether a vector exists is a property of the name alone.
    """
    # Loaded once per call; `load_taxonomy_index` caches the parsed xlsx at
    # module level, so repeated `decide_rows` calls across chunks pay no I/O.
    valid_leaves, _ = coicop_taxonomy.load_taxonomy_index()

    out_rows: list[dict] = []
    for _, p in products.iterrows():
        name = str(p["product_name_original"])
        key = name if key_fn is None else key_fn(p)
        row = dict(_EMPTY)
        row["input_hash"] = p["input_hash"]
        row.update(
            _structural_fields(
                name,
                p.get("category"),
                p.get("country"),
                p.get("lang"),
                p.get("details"),
                p.get("unit"),
                p.get("source"),
            )
        )
        # The head's top-1 leaf REGARDLESS of acceptance. Keeping it is what
        # separates "this country has no such product" from "it has them but the
        # gate would not commit" — two findings with different remedies.
        row["leaf_top1"] = leaf_by.get(key)
        row["gate_score"] = float(gate_by.get(key, float("nan")))

        # parse_codes, not the raw string: is_narrow/resolved_code take a LIST.
        # Passing the "|"-joined string makes is_narrow iterate CHARACTERS, every
        # one of which fails its len>=4 test, so it returned False for every row
        # and the ADR-0002 narrow-source short-circuit never fired.
        # is_narrow also requires the resolved code to be a taxonomy LEAF — a
        # source declaring a parent node (e.g. "02.1") no longer short-circuits;
        # it falls through to the classifier below instead.
        declared = coicop_codes.parse_codes(p.get("declared_coicop_codes"))
        if declared and coicop_codes.is_narrow(declared, valid_leaves):
            row["coicop_code"] = coicop_codes.resolved_code(declared)
            row["confidence"] = 1.0
            row["state"] = "narrow_source"
            row["trust_level"] = "high"
        elif name in unembedded:
            # Never scored: a scraping/embedding backlog item, NOT a model
            # refusal. Kept distinct from "rejected" so the coverage report can
            # tell the two apart.
            row["coicop_code"] = None
            row["confidence"] = float("nan")
            row["state"] = "unembedded"
            row["trust_level"] = "low"
        elif ok_by.get(key, False):
            row["coicop_code"] = str(leaf_by[key])
            row["confidence"] = float(conf_by[key])
            row["state"] = "classified"
            row["trust_level"] = "high"
        else:
            row["coicop_code"] = None
            row["confidence"] = float(conf_by.get(key, 0.0))
            row["state"] = "rejected"
            row["trust_level"] = "low"

        if row["trust_level"] == "high":
            verdict = audit.audit(
                row.get("coicop_code"), row.get("pricing_basis"), audit._denylist_map()
            )
            if verdict == audit.REJECT:
                row["trust_level"] = "low"
                row["state"] = "rejected"
            elif verdict == audit.FLAG:
                row["trust_level"] = "flagged"
                row["state"] = "flagged_basis"

        # Unit-value adoption gate (layer 1). Independent of `state`: it answers
        # only "is this row's DENOMINATOR adoptable", never whether the leaf is
        # right. Runs after the basis-audit because a pair that audit ruled
        # physically impossible is not adoptable however permissive the
        # category allow-list is.
        adopt, _reason = uv_gate.gate(row["coicop_code"], row["pricing_basis"])
        if adopt and row["pricing_basis"] in uv_gate.GATED_BASES:
            adopt = row["trust_level"] == "high"
        row["uv_trusted"] = adopt

        out_rows.append(row)
    return pd.DataFrame(out_rows, columns=DECISION_COLS)


def classified_view(decisions: pd.DataFrame, division) -> pd.DataFrame:
    """The `classified.parquet` contract, derived from the decisions table.

    Same columns as before the decisions table existed, so `build/aggregate.py`
    and `build/leaf_support.py` see no change. `division` is a prefix or a tuple
    of prefixes, and it — not aggregate.py — is where build scope is decided, so
    an all-division scoring run cannot silently widen what `prices build` reads.
    """
    code = decisions["coicop_code"].astype("string").fillna("")
    prefixes = (division,) if isinstance(division, str) else tuple(division)
    keep = decisions[code.str.startswith(prefixes)]
    return keep[[*ENRICHMENT_COLS, "input_hash"]].reset_index(drop=True)


def classify_products(
    products: pd.DataFrame, division, version: Optional[str] = None
) -> pd.DataFrame:
    """Full decision table for `products` — all rows, all states."""
    maps = score_unique_names(products, division, version)
    return decide_rows(products, *maps)


def run(
    in_path: Optional[Path] = None,
    out_path: Optional[Path] = None,
    division: Optional[str] = None,
    version: Optional[str] = None,
    full_out_path: Optional[Path] = None,
    chunk_rows: int = 500_000,
) -> dict:
    in_path = in_path or config.PRODUCTS_INPUT_PARQUET
    out_path = out_path or config.CLASSIFIED_PARQUET
    full_out_path = full_out_path or config.DECISIONS_PARQUET
    division = division if division is not None else config.CLASSIFIER_DEFAULT_DIVISION
    # "all" is the sentinel for an all-division run; anything else stays a prefix.
    div = None if str(division).lower() == "all" else str(division)

    import pyarrow.parquet as pq

    products = pd.read_parquet(in_path, columns=PRODUCT_COLS)
    maps = score_unique_names(products, div, version)

    full_out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Stream the row loop so the decision frame is never resident whole
    # alongside `products`.
    writer = None
    views: list[pd.DataFrame] = []
    n_dec = 0
    try:
        for start in range(0, len(products), chunk_rows):
            chunk = products.iloc[start : start + chunk_rows]
            dec = decide_rows(chunk, *maps)
            n_dec += len(dec)
            views.append(classified_view(dec, config.BUILD_DIVISIONS))
            table = pa.Table.from_pandas(
                dec, schema=DECISION_SCHEMA, preserve_index=False
            )
            if writer is None:
                writer = pq.ParquetWriter(full_out_path, DECISION_SCHEMA)
            writer.write_table(table)
            print(f"[classify] decided {n_dec}/{len(products)} rows", flush=True)
    finally:
        if writer is not None:
            writer.close()

    view = (
        pd.concat(views, ignore_index=True)
        if views
        else pd.DataFrame(columns=[*ENRICHMENT_COLS, "input_hash"])
    )
    view.to_parquet(out_path, index=False)

    summary = {
        "decisions": n_dec,
        "decisions_path": str(full_out_path),
        "classified": len(view),
        "classified_path": str(out_path),
        "division": division,
        "version": version,
    }
    print(
        f"Wrote {n_dec} decisions to {full_out_path} "
        f"and {len(view)} division-{'/'.join(config.BUILD_DIVISIONS)} rows to {out_path}"
    )
    return summary
