"""Gold-labeling A/B merge stage — the join between the two independent passes.

Reads the batch metadata CSVs (`gold/batches/gold_v5_batch_NNN.csv`) and both
label passes (`gold/labels/pass_{a,b}_batch_NNN.json`), aligns them per
`gold_row_id`, and emits:

  gate1/gold_v5_merged.parquet            -- every dual-labeled row (agree +
                                             disagree) with both passes, the
                                             three agreement flags, and the
                                             disagreement_type.
  gate1/gold_v5_gate1_disagreements.csv   -- the non-agree worklist for gate-1
                                             adjudication (blinded downstream).

`disagreement_type` is the reverse-engineered taxonomy validated to 100% against
the original gold_v5_merged.parquet; functionally the pipeline only cares about
`agree` (kept as consensus) vs everything else (routed to adjudication).
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from prices.enrich import config

GOLD_DIR = config.REPO_ROOT / "data" / "prices" / "enrich" / "gold"
BATCH_DIR = GOLD_DIR / "batches"
LABELS_DIR = GOLD_DIR / "labels"
GATE_DIR = GOLD_DIR / "gate1"

MERGED_COLUMNS = [
    "gold_row_id",
    "batch",
    "product_name",
    "country",
    "source",
    "channel",
    "category",
    "declared_coicop_codes",
    "price",
    "a_verdict",
    "a_code",
    "a_division",
    "a_basis",
    "a_rationale",
    "b_verdict",
    "b_code",
    "b_division",
    "b_basis",
    "b_rationale",
    "verdict_agree",
    "code_agree",
    "division_agree",
    "disagreement_type",
    "a_code_valid",
    "b_code_valid",
]

# disagreements.csv keeps disagreement_type up front and drops the flag/validity
# columns that only matter to the merged parquet.
DISAGREEMENT_COLUMNS = [
    "gold_row_id",
    "batch",
    "disagreement_type",
    "product_name",
    "country",
    "source",
    "channel",
    "category",
    "declared_coicop_codes",
    "price",
    "a_verdict",
    "a_code",
    "a_division",
    "a_basis",
    "a_rationale",
    "b_verdict",
    "b_code",
    "b_division",
    "b_basis",
    "b_rationale",
]


def _group(code: str) -> str:
    """COICOP group prefix — the first two dotted components (e.g. `01.1`)."""
    return ".".join(str(code).split(".")[:2])


def classify_disagreement(
    a_verdict: str,
    a_code: str,
    a_division: str,
    b_verdict: str,
    b_code: str,
    b_division: str,
) -> tuple[bool, bool, bool, str]:
    """Return `(verdict_agree, code_agree, division_agree, disagreement_type)`.

    Types: `agree`, `verdict_conflict`, `leaf_within_class`/`leaf_cross_class`
    (both leaf, code differs, same/different group), `class_conflict`
    (ambiguous_class), `code_conflict` (any other same-verdict code mismatch)."""
    verdict_agree = a_verdict == b_verdict
    code_agree = a_code == b_code
    division_agree = a_division == b_division
    if verdict_agree and code_agree:
        dt = "agree"
    elif not verdict_agree:
        dt = "verdict_conflict"
    elif a_verdict == "leaf":
        dt = (
            "leaf_within_class"
            if _group(a_code) == _group(b_code)
            else "leaf_cross_class"
        )
    elif a_verdict == "ambiguous_class":
        dt = "class_conflict"
    else:
        dt = "code_conflict"
    return verdict_agree, code_agree, division_agree, dt


def _load_labels(labels_dir: Path, pass_tag: str) -> dict[str, dict]:
    by_id: dict[str, dict] = {}
    for f in sorted(labels_dir.glob(f"pass_{pass_tag}_batch_*.json")):
        if f.name.endswith(".meta.json"):  # skip the per-batch meta sidecars
            continue
        for o in json.loads(f.read_text(encoding="utf-8")):
            by_id[str(o["gold_row_id"])] = o
    return by_id


def _meta(batches_dir: Path) -> dict[str, dict]:
    by_id: dict[str, dict] = {}
    for csv in sorted(batches_dir.glob("gold_v5_batch_*.csv")):
        batch = csv.stem.split("_")[-1]
        df = pd.read_csv(csv)
        for _, r in df.iterrows():
            by_id[str(r["gold_row_id"])] = {"batch": batch, "row": r}
    return by_id


def build_merged(
    labels_dir: Path, batches_dir: Path, leaves: set[str]
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Join batch metadata with both passes into `(merged, disagreements)`."""
    a = _load_labels(labels_dir, "a")
    b = _load_labels(labels_dir, "b")
    meta = _meta(batches_dir)

    rows = []
    for rid in sorted(set(a) & set(b) & set(meta)):
        la, lb = a[rid], b[rid]
        m = meta[rid]["row"]
        av, ac, ad = (
            str(la["verdict"]),
            str(la.get("code") or ""),
            str(la.get("division") or ""),
        )
        bv, bc, bd = (
            str(lb["verdict"]),
            str(lb.get("code") or ""),
            str(lb.get("division") or ""),
        )
        verdict_agree, code_agree, division_agree, dt = classify_disagreement(
            av, ac, ad, bv, bc, bd
        )
        rows.append(
            {
                "gold_row_id": rid,
                "batch": meta[rid]["batch"],
                "product_name": m.get("product_name_original"),
                "country": m.get("country"),
                "source": m.get("source"),
                "channel": m.get("channel"),
                "category": m.get("category"),
                "declared_coicop_codes": m.get("declared_coicop_codes"),
                "price": m.get("price"),
                "a_verdict": av,
                "a_code": ac,
                "a_division": ad,
                "a_basis": str(la.get("pricing_basis_plausible") or ""),
                "a_rationale": str(la.get("rationale") or ""),
                "b_verdict": bv,
                "b_code": bc,
                "b_division": bd,
                "b_basis": str(lb.get("pricing_basis_plausible") or ""),
                "b_rationale": str(lb.get("rationale") or ""),
                "verdict_agree": verdict_agree,
                "code_agree": code_agree,
                "division_agree": division_agree,
                "disagreement_type": dt,
                # only a `leaf` verdict must carry a real leaf code; exclude /
                # ambiguous_class verdicts use class/empty codes by design.
                "a_code_valid": av != "leaf" or ac in leaves,
                "b_code_valid": bv != "leaf" or bc in leaves,
            }
        )

    merged = pd.DataFrame(rows, columns=MERGED_COLUMNS)
    disagreements = merged.loc[
        merged["disagreement_type"] != "agree", DISAGREEMENT_COLUMNS
    ].reset_index(drop=True)
    return merged, disagreements


def run(
    labels_dir: Path = LABELS_DIR,
    batches_dir: Path = BATCH_DIR,
    out_dir: Path = GATE_DIR,
    merged_name: str = "gold_v5_merged.parquet",
    disagreements_name: str = "gold_v5_gate1_disagreements.csv",
) -> dict:
    from prices.enrich.coicop_taxonomy import load_taxonomy_index

    leaves, _ = load_taxonomy_index()
    merged, disagreements = build_merged(labels_dir, batches_dir, leaves)
    out_dir.mkdir(parents=True, exist_ok=True)
    merged.to_parquet(out_dir / merged_name, index=False)
    disagreements.to_csv(out_dir / disagreements_name, index=False)
    summary = {
        "n_rows": len(merged),
        "n_agree": int((merged["disagreement_type"] == "agree").sum()),
        "n_disagree": len(disagreements),
        "disagreement_types": merged["disagreement_type"].value_counts().to_dict(),
        "merged": str(out_dir / merged_name),
        "disagreements": str(out_dir / disagreements_name),
    }
    return summary
