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
whose extracted basis contradicts the leaf's denylist. Output is keyed by
``input_hash`` with ``merge.ENRICHMENT_COLS``, filtered to the backend's COICOP
divisions.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Sequence

import pandas as pd

from prices.enrich import audit, coicop_codes, config
from prices.enrich.classifier import backends
from prices.enrich.extract import extract
from prices.enrich.stages.merge import ENRICHMENT_COLS

_EMPTY = {c: None for c in ENRICHMENT_COLS}


_QTY_BASES = frozenset({"mass", "volume", "length", "count"})


def _structural_fields(name, category, country, lang, details=None) -> dict:
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
    return {
        "pricing_basis": qs.pricing_basis,
        "amount_value": qs.amount_value,
        "standard_unit": qs.standard_unit,
        "count": qs.count,
        "multiplier": qs.multiplier,
        "is_promotion": sf.is_promotion,
        "is_bundle": sf.is_bundle,
        "is_multipack": sf.is_multipack,
        "promo_reason": sf.promo_reason,
    }


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
    )
    return dict(zip(keys, values))


def classify_products(
    products: pd.DataFrame,
    backend: Optional[str] = None,
    version: Optional[str] = None,
    workers: int = 1,
    divisions: Optional[Sequence[str]] = None,
) -> pd.DataFrame:
    be = backends.get(backend)
    divisions = tuple(divisions) if divisions else be.divisions

    # The backend scores once per key (embedding, then the model, is the cost)
    # and everything below maps its verdict back onto rows. Scoring is
    # bucket-major and checkpointed per bucket, so a killed run resumes from
    # shards on disk rather than re-scoring the corpus.
    scored = _score_index(
        be.score(products, version=version, workers=workers), be.key_cols
    )

    out_rows: list[dict] = []
    for _, p in products.iterrows():
        name = str(p["product_name_original"])
        row = dict(_EMPTY)
        row["input_hash"] = p["input_hash"]
        row.update(
            _structural_fields(
                name,
                p.get("category"),
                p.get("country"),
                p.get("lang"),
                p.get("details"),
            )
        )

        key = tuple(str(p.get(c) or "") for c in be.key_cols)
        leaf, conf, accepted = scored.get(key, (None, 0.0, False))

        # parse_codes, not str(): prepare serializes these pipe-joined, and
        # is_narrow over a raw string iterates CHARACTERS, every one of which
        # fails its len>=4 test. That made this branch unreachable.
        declared = coicop_codes.parse_codes(p.get("declared_coicop_codes"))
        if declared and coicop_codes.is_narrow(declared):
            row["coicop_code"] = coicop_codes.resolved_code(declared)
            row["confidence"] = 1.0
            row["state"] = "narrow_source"
            row["trust_level"] = "high"
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

        out_rows.append(row)

    out = pd.DataFrame(out_rows)
    code = out["coicop_code"].astype("string").fillna("")
    return out[code.str.startswith(divisions)].reset_index(drop=True)


def run(
    in_path: Optional[Path] = None,
    out_path: Optional[Path] = None,
    division: Optional[str] = None,
    version: Optional[str] = None,
    backend: Optional[str] = None,
    workers: int = 1,
) -> pd.DataFrame:
    be = backends.get(backend)
    in_path = in_path or config.PRODUCTS_INPUT_PARQUET
    # Each backend owns its output file, so `--backend head` after a hierlex run
    # leaves the hierlex result standing instead of overwriting it with a
    # narrower, differently-calibrated one.
    out_path = out_path or be.classified_path
    divisions = (division,) if division else be.divisions
    products = pd.read_parquet(in_path)
    classified = classify_products(
        products, backend=be.name, version=version, workers=workers, divisions=divisions
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    classified.to_parquet(out_path, index=False)
    print(
        f"Wrote {len(classified)} {be.name} classifications "
        f"(divisions {', '.join(divisions)}) to {out_path}"
    )
    return classified
