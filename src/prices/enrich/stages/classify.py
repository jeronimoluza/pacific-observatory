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

from pathlib import Path
from typing import Optional

import pandas as pd

from prices.enrich import audit, config, coicop_codes
from prices.enrich.classifier.predict import load_predictor
from prices.enrich.extract import extract
from prices.enrich.stages.merge import ENRICHMENT_COLS

_EMPTY = {c: None for c in ENRICHMENT_COLS}


def _structural_fields(name, category, country, lang) -> dict:
    sf = extract(str(name), category or None, country or None, lang or None)
    return {
        "pricing_basis": sf.pricing_basis,
        "amount_value": sf.amount_value,
        "standard_unit": sf.standard_unit,
        "count": sf.count,
        "multiplier": sf.multiplier,
        "is_promotion": sf.is_promotion,
        "is_bundle": sf.is_bundle,
        "is_multipack": sf.is_multipack,
        "promo_reason": sf.promo_reason,
    }


def classify_products(
    products: pd.DataFrame, division: str, version: Optional[str] = None
) -> pd.DataFrame:
    predictor = load_predictor(version)
    names = products["product_name_original"].astype(str)

    # Head predicts once per unique name (embedding is the cost), mapped back.
    uniq = pd.Index(names.unique())
    pred = predictor.predict(uniq.tolist())
    leaf_by = dict(zip(uniq, pred.leaf))
    conf_by = dict(zip(uniq, pred.conf))
    ok_by = dict(zip(uniq, pred.accepted))

    out_rows: list[dict] = []
    for _, p in products.iterrows():
        name = str(p["product_name_original"])
        row = dict(_EMPTY)
        row["input_hash"] = p["input_hash"]
        row.update(
            _structural_fields(name, p.get("category"), p.get("country"), p.get("lang"))
        )

        declared = str(p.get("declared_coicop_codes") or "")
        if declared and coicop_codes.is_narrow(declared):
            row["coicop_code"] = coicop_codes.resolved_code(declared)
            row["confidence"] = 1.0
            row["state"] = "narrow_source"
            row["trust_level"] = "high"
        elif ok_by.get(name, False):
            row["coicop_code"] = str(leaf_by[name])
            row["confidence"] = float(conf_by[name])
            row["state"] = "classified"
            row["trust_level"] = "high"
        else:
            row["coicop_code"] = None
            row["confidence"] = float(conf_by.get(name, 0.0))
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
    return out[code.str.startswith(division)].reset_index(drop=True)


def run(
    in_path: Optional[Path] = None,
    out_path: Optional[Path] = None,
    division: Optional[str] = None,
    version: Optional[str] = None,
) -> pd.DataFrame:
    in_path = in_path or config.PRODUCTS_INPUT_PARQUET
    out_path = out_path or config.CLASSIFIED_PARQUET
    division = division or config.CLASSIFIER_DEFAULT_DIVISION
    products = pd.read_parquet(in_path)
    classified = classify_products(products, division=division, version=version)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    classified.to_parquet(out_path, index=False)
    print(f"Wrote {len(classified)} division-{division} classifications to {out_path}")
    return classified
