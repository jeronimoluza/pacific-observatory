"""Classify stage — assign each product a COICOP leaf plus structural fields.

Reads ``products_input`` (already one row per ``input_hash``) and runs the two
independent enrich jobs per unique product name:

  - structural regex extraction (``extract``) overlays pricing_basis / amount /
    count / multiplier / promo flags;
  - a classifier backend predicts the COICOP leaf, accepted only where that
    backend's calibrated gate clears.

**This stage never trains anything.** Which model scores, at what grain, and
where the result lands are all properties of the backend
(``classifier/backends.py``); the default is the frozen HierLex bundle, which
has no training procedure to call at all. Training lives behind
``backends.fit_backend`` and is reached by its own command.

Source-declared narrow COICOP codes bypass the classifier (structural extraction
still runs). A basis-audit (``audit.py``) withholds trust from accepted rows
whose extracted basis contradicts the leaf's denylist.

Two artifacts come out of one scoring pass. The **decisions** table keeps EVERY
``input_hash`` — rejects and never-scored rows included — because that is the
only place coverage can be measured; ``classified.parquet`` is a filtered view
of it, carrying ``merge.ENRICHMENT_COLS`` for the backend's COICOP divisions.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Optional, Sequence

import pandas as pd
import pyarrow as pa

from prices import partition
from prices.enrich import audit, coicop_codes, coicop_taxonomy, config, uv_gate
from prices.enrich.classifier import backends
from prices.enrich.declared_unit import parse_declared_unit
from prices.enrich.extract import StructuralFields, extract
from prices.enrich.fluid_oz import remap_fluid_oz
from prices.enrich.stages import decisions_store
from prices.enrich.stages.merge import ENRICHMENT_COLS

# Re-exported: these moved to `products_reader` when this file hit its size
# limit, and `hierlex/decide.py` plus the tests import them from here.
from prices.enrich.stages.products_reader import (  # noqa: F401
    PRODUCT_COLS,
    iter_products,
    read_products,
)

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


DECISION_COLS = [*ENRICHMENT_COLS, "input_hash", "country", "leaf_top1", "gate_score"]

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
    # Carried so the table can be partitioned and scoped by country without a
    # join back to products_input. Coverage is reported per country anyway, so
    # the column the report needs was previously being recovered by re-reading
    # a 6.4 GB file to get one string per row.
    "country": pa.string(),
    "leaf_top1": pa.string(),
    "gate_score": pa.float64(),
}
_uncovered = [c for c in DECISION_COLS if c not in _DECISION_TYPES]
if _uncovered:  # ENRICHMENT_COLS grew — extend _DECISION_TYPES deliberately
    raise RuntimeError(f"no arrow type declared for decision columns: {_uncovered}")
DECISION_SCHEMA = pa.schema([(c, _DECISION_TYPES[c]) for c in DECISION_COLS])


def _score_index(scores: pd.DataFrame, key_cols: Sequence[str]) -> dict:
    """Backend scores as a lookup on the backend's own key.

    The key is the whole point: the head is country-blind and scores per name,
    HierLex scores per (name, country) because country is one of its gate
    features. Keying on the wrong one silently gives every country the same
    verdict.
    """
    if scores.empty:
        return {}
    keys = zip(*(scores[c].astype(str) for c in key_cols))
    values = zip(
        scores["leaf"],
        scores["conf"].astype(float),
        scores["accepted"].astype(bool),
        scores["leaf_top1"],
        scores["gate_score"].astype(float),
    )
    return dict(zip(keys, values))


def decide_rows(
    products: pd.DataFrame,
    scored: dict,
    key_cols: Sequence[str],
    unembedded: frozenset[str],
) -> pd.DataFrame:
    """One decision row per input_hash. Rejects and unembedded rows are RETAINED
    — they are the coverage denominator.

    `scored` is keyed on `key_cols`, the backend's own grain. `unembedded` is
    keyed by NAME whatever that grain is: whether a vector exists is a property
    of the name alone.
    """
    # Resolved on first use, not up front. `load_taxonomy_index` reads an xlsx
    # that lives under `data/` and is therefore not in the repo, so loading it
    # unconditionally makes every decide — including a corpus where no source
    # declares a code — depend on a file most checkouts do not have.
    # `load_taxonomy_index` caches at module level, so this costs one branch.
    valid_leaves = None

    out_rows: list[dict] = []
    for _, p in products.iterrows():
        name = str(p["product_name_original"])
        row = dict(_EMPTY)
        row["input_hash"] = p["input_hash"]
        country = p.get("country")
        row["country"] = None if country is None or pd.isna(country) else str(country)
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

        key = tuple(str(p.get(c) or "") for c in key_cols)
        leaf, conf, accepted, leaf_top1, gate_score = scored.get(
            key, (None, 0.0, False, None, float("nan"))
        )
        # The model's top-1 leaf REGARDLESS of acceptance. Keeping it is what
        # separates "this country has no such product" from "it has them but the
        # gate would not commit" — two findings with different remedies.
        row["leaf_top1"] = leaf_top1
        row["gate_score"] = float(gate_score)

        # parse_codes, not the raw string: is_narrow/resolved_code take a LIST.
        # Passing the "|"-joined string makes is_narrow iterate CHARACTERS, every
        # one of which fails its len>=4 test, so it returned False for every row
        # and the ADR-0002 narrow-source short-circuit never fired.
        # is_narrow also requires the resolved code to be a taxonomy LEAF — a
        # source declaring a parent node (e.g. "02.1") no longer short-circuits;
        # it falls through to the classifier below instead.
        declared = coicop_codes.parse_codes(p.get("declared_coicop_codes"))
        if declared and valid_leaves is None:
            valid_leaves, _ = coicop_taxonomy.load_taxonomy_index()
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
        elif accepted:
            row["coicop_code"] = str(leaf)
            row["confidence"] = float(conf)
            row["state"] = "classified"
            row["trust_level"] = "high"
        else:
            row["coicop_code"] = None
            row["confidence"] = float(conf)
            row["state"] = "rejected"
            row["trust_level"] = "low"

        remap_fluid_oz(row, name)

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


def classified_view(decisions: pd.DataFrame, divisions) -> pd.DataFrame:
    """The `classified.parquet` contract, derived from the decisions table.

    Same columns as before the decisions table existed, so `build/aggregate.py`
    and `build/leaf_support.py` see no change. `divisions` is a prefix or a tuple
    of prefixes, and it — not aggregate.py — is where build scope is decided, so
    an all-division scoring run cannot silently widen what `prices build` reads.
    """
    keep = decisions[classified_mask(decisions, divisions)]
    return keep[[*ENRICHMENT_COLS, "input_hash"]].reset_index(drop=True)


def classified_mask(decisions: pd.DataFrame, divisions) -> pd.Series:
    """Which decision rows reach `classified.parquet`.

    Exposed separately because the partitioned writer needs the country of the
    kept rows, and `classified_view` deliberately does not carry one — its
    column list is a contract `prices build` reads. Recomputing the prefix test
    at the call site instead would put the same rule in two places.
    """
    code = decisions["coicop_code"].astype("string").fillna("")
    prefixes = (divisions,) if isinstance(divisions, str) else tuple(divisions)
    return code.str.startswith(prefixes)


def classify_products(
    products: pd.DataFrame,
    backend: Optional[str] = None,
    version: Optional[str] = None,
    workers: int = 1,
    divisions: Optional[Sequence[str]] = None,
) -> pd.DataFrame:
    """The `classified.parquet` view for `products` — filtered to `divisions`."""
    be = backends.get(backend)
    divisions = tuple(divisions) if divisions else be.divisions
    decisions = decide_products(
        products, backend=be.name, version=version, workers=workers
    )
    return classified_view(decisions, divisions)


def decide_products(
    products: pd.DataFrame,
    backend: Optional[str] = None,
    version: Optional[str] = None,
    workers: int = 1,
) -> pd.DataFrame:
    """Full decision table for `products` — all rows, all states."""
    be = backends.get(backend)
    # The backend scores once per key (embedding, then the model, is the cost)
    # and everything below maps its verdict back onto rows. Scoring is
    # bucket-major and checkpointed per bucket, so a killed run resumes from
    # shards on disk rather than re-scoring the corpus.
    result = be.score(products, version=version, workers=workers)
    if result.unembedded:
        print(
            f"[classify] {len(result.unembedded)} unique names are not in the "
            f"embed store — recorded as state='unembedded', not scored",
            flush=True,
        )
    return decide_rows(
        products,
        _score_index(result.frame, be.key_cols),
        be.key_cols,
        result.unembedded,
    )


def countries_for(selectors, root: Optional[Path] = None) -> Optional[list[str]]:
    """The countries a selector names, or None for the whole corpus.

    Country, not source, is the scope grain — the same choice
    `build.aggregate.overlay_observations` makes, for the same reason. `prepare`
    groups on `input_hash`, whose fallback key is
    `(product_name_original, country, currency)`; two sources in one country
    selling the same URL-less product are therefore ONE products_input row. A
    source-grained rescope would split that row's evidence and silently change
    the number, so a selector that names a source recomputes its whole country.
    """
    if not selectors:
        return None
    shards = partition.select(selectors, root or partition.PER_SOURCE_DIR)
    return sorted({s.country for s in shards})


def run(
    in_path: Optional[Path] = None,
    out_path: Optional[Path] = None,
    division: Optional[str] = None,
    version: Optional[str] = None,
    backend: Optional[str] = None,
    workers: int = 1,
    full_out_path: Optional[Path] = None,
    chunk_rows: int = 500_000,
    selectors: Optional[Sequence[str]] = None,
    shard_root: Optional[Path] = None,
) -> dict:
    be = backends.get(backend)
    in_path = in_path or config.PRODUCTS_INPUT_PARQUET
    # Each backend owns its output files, so `--backend head` after a hierlex run
    # leaves the hierlex result standing instead of overwriting it with a
    # narrower, differently-calibrated one.
    out_path = out_path or be.classified_path
    full_out_path = full_out_path or be.decisions_path
    divisions = (division,) if division else be.divisions

    countries = countries_for(selectors, shard_root)
    if countries is not None and not countries:
        raise RuntimeError(
            f"no shards match {list(selectors)}; refusing to run classify over "
            "an empty scope (an unscoped run is `--stage classify` with no "
            "--only/-c)"
        )
    if countries is not None:
        print(
            f"[classify] scoped to {len(countries)} countries: "
            f"{', '.join(countries[:8])}{' …' if len(countries) > 8 else ''}",
            flush=True,
        )

    products = read_products(in_path, countries=countries)
    n_products = len(products)
    result = be.score(products, version=version, workers=workers)
    # Scoring is the last thing that needs the corpus resident. The decide loop
    # below re-reads it from parquet a chunk at a time, so holding this frame any
    # longer costs ~20 GB for nothing -- and it is the difference between the
    # loop fitting in RAM and swapping. `be.score` keeps its whole-frame
    # contract; only the lifetime changes.
    del products
    if result.unembedded:
        print(
            f"[classify] {len(result.unembedded)} unique names are not in the "
            f"embed store — recorded as state='unembedded', not scored",
            flush=True,
        )
    scored = _score_index(result.frame, be.key_cols)
    # Same reasoning as `products`: `result.frame` is 29.4M scored rows, and once
    # the lookup exists the loop reads nothing from it but `unembedded`. Keeping
    # it alive means paying for the scores twice, as a frame and as a dict.
    unembedded = result.unembedded
    del result

    dec_root = decisions_store.parts_root(full_out_path)
    view_root = decisions_store.parts_root(out_path)

    # Stream the row loop so neither the decision frame nor the corpus is ever
    # resident whole. Both tables land as one part per country, so this run
    # rewrites only the countries it actually decided and every other part on
    # disk is left exactly as it was — which is the whole reason a one-country
    # fix no longer costs a 37.4M-row rewrite.
    views: dict[str, list[pd.DataFrame]] = {}
    n_dec = 0
    n_view = 0
    with decisions_store.PartitionedWriter(dec_root, DECISION_SCHEMA) as writer:
        for chunk in iter_products(in_path, chunk_rows, countries=countries):
            dec = decide_rows(chunk, scored, be.key_cols, unembedded)
            n_dec += len(dec)
            writer.write(dec)
            # `classified` is still written from pandas, so it keeps the dtypes
            # it has always had; only its file layout changes. The country rides
            # alongside because the view's column list is a contract.
            keep = classified_mask(dec, divisions)
            view = classified_view(dec, divisions)
            n_view += len(view)
            for country, part in decisions_store.split_by_country(
                view, dec.loc[keep, "country"]
            ):
                views.setdefault(country, []).append(part)
            print(f"[classify] decided {n_dec}/{n_products} rows", flush=True)

    written_views = decisions_store.write_pandas_parts(views, view_root)
    if countries is None:
        # A full run is authoritative: a country that no longer produces rows
        # must not keep the part it produced last time. A SCOPED run prunes
        # nothing, because everything it did not write is out of its scope.
        decisions_store.prune(dec_root, set(writer.rows_by_country))
        decisions_store.prune(view_root, {p.stem for p in written_views})

    summary = {
        "backend": be.name,
        "decisions": n_dec,
        "decisions_path": str(dec_root),
        "classified": n_view,
        "classified_path": str(view_root),
        "divisions": list(divisions),
        "version": version,
        "countries": countries,
        "parts_written": len(writer.rows_by_country),
    }
    print(
        f"Wrote {n_dec} {be.name} decisions to {dec_root} "
        f"and {n_view} division-{'/'.join(divisions)} rows to {view_root} "
        f"across {len(writer.rows_by_country)} country parts"
    )
    return summary
