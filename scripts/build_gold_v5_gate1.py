"""Gold v5 Gate-1 adjudication builder (W3.2 -> Gate 1).

Merges Pass A (codex/gpt-5 family) and Pass B (Gemini flash-lite) labels per
batch, joins product context from the batch CSVs, and emits the disagreement
worklist that a 3rd model family (Claude) adjudicates at Gate 1. Only batches
with BOTH passes present are included; missing pairs are reported, not fabricated.

Outputs under data/prices/enrich/gold/gate1/:
  gold_v5_merged.parquet          -- every dual-labeled row (agree + disagree)
  gold_v5_gate1_disagreements.csv -- adjudication worklist (disagreements only)
  gold_v5_gate1_summary.json      -- agreement rates + coverage
"""

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from prices.enrich import config  # noqa: E402
from prices.enrich.tier_b.taxonomy_index import load_taxonomy_index  # noqa: E402

GOLD_DIR = config.REPO_ROOT / "data" / "prices" / "enrich" / "gold"
BATCH_DIR = GOLD_DIR / "batches"
LABELS_DIR = GOLD_DIR / "labels"
OUT_DIR = GOLD_DIR / "gate1"


def _norm_basis(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    return str(v).strip().lower()


def _load_pass(path: Path) -> dict:
    rows = json.loads(path.read_text(encoding="utf-8"))
    out = {}
    for r in rows:
        out[str(r["gold_row_id"])] = {
            "verdict": str(r.get("verdict", "")).strip(),
            "code": str(r.get("code", "")).strip(),
            "division": str(r.get("division", "")).strip(),
            "basis": _norm_basis(r.get("pricing_basis_plausible")),
            "rationale": str(r.get("rationale", "")).strip(),
        }
    return out


def _class_of(code: str) -> str:
    parts = code.split(".")
    return ".".join(parts[:2]) if len(parts) >= 2 else code


def _disagreement_type(a: dict, b: dict) -> str:
    if a["verdict"] != b["verdict"]:
        return "verdict_conflict"
    if a["code"] == b["code"]:
        return "agree"
    if a["verdict"] == "leaf":
        return (
            "leaf_within_class"
            if _class_of(a["code"]) == _class_of(b["code"])
            else "leaf_cross_class"
        )
    if a["verdict"] == "ambiguous_class":
        return "class_conflict"
    return "code_conflict"


def build(only_disagree_types=None, tag="", min_batch=0) -> dict:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    sfx = f"_{tag}" if tag else ""
    leaves, _ = load_taxonomy_index()
    batches = sorted(BATCH_DIR.glob("gold_v5_batch_*.csv"))
    if min_batch:
        batches = [p for p in batches if int(p.stem.split("_")[-1]) >= min_batch]

    merged_rows = []
    coverage = {"paired": [], "pass_a_only": [], "pass_b_only": [], "neither": []}

    for bpath in batches:
        b = bpath.stem.split("_")[-1]
        pa_path = LABELS_DIR / f"pass_a_batch_{b}.json"
        pb_path = LABELS_DIR / f"pass_b_batch_{b}.json"
        has_a, has_b = pa_path.exists(), pb_path.exists()
        if has_a and has_b:
            coverage["paired"].append(b)
        elif has_a:
            coverage["pass_a_only"].append(b)
            continue
        elif has_b:
            coverage["pass_b_only"].append(b)
            continue
        else:
            coverage["neither"].append(b)
            continue

        pa = _load_pass(pa_path)
        pb = _load_pass(pb_path)
        ctx = pd.read_csv(bpath).set_index("gold_row_id")

        for rid in ctx.index.astype(str):
            a, bl = pa.get(rid), pb.get(rid)
            if a is None or bl is None:
                continue
            c = ctx.loc[rid]
            dtype = _disagreement_type(a, bl)
            merged_rows.append(
                {
                    "gold_row_id": rid,
                    "batch": b,
                    "product_name": c.get("product_name_original", ""),
                    "country": c.get("country", ""),
                    "source": c.get("source", ""),
                    "channel": c.get("channel", ""),
                    "category": c.get("category", ""),
                    "declared_coicop_codes": c.get("declared_coicop_codes", ""),
                    "price": c.get("price", ""),
                    "a_verdict": a["verdict"],
                    "a_code": a["code"],
                    "a_division": a["division"],
                    "a_basis": a["basis"],
                    "a_rationale": a["rationale"],
                    "b_verdict": bl["verdict"],
                    "b_code": bl["code"],
                    "b_division": bl["division"],
                    "b_basis": bl["basis"],
                    "b_rationale": bl["rationale"],
                    "verdict_agree": a["verdict"] == bl["verdict"],
                    "code_agree": a["code"] == bl["code"],
                    "division_agree": a["division"] == bl["division"],
                    "disagreement_type": dtype,
                    "a_code_valid": (a["verdict"] != "leaf") or (a["code"] in leaves),
                    "b_code_valid": (bl["verdict"] != "leaf") or (bl["code"] in leaves),
                }
            )

    df = pd.DataFrame(merged_rows)
    if df.empty:
        raise SystemExit("No dual-labeled batches found — need both passes present.")

    merged_path = OUT_DIR / f"gold_v5_merged{sfx}.parquet"
    df.to_parquet(merged_path, index=False)

    dis = df[df["disagreement_type"] != "agree"].copy()
    if only_disagree_types:
        dis = dis[dis["disagreement_type"].isin(only_disagree_types)]
    dis = dis.sort_values(["disagreement_type", "batch", "gold_row_id"])
    cols = [
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
    dis_path = OUT_DIR / f"gold_v5_gate1_disagreements{sfx}.csv"
    dis[cols].to_csv(dis_path, index=False)

    n = len(df)
    summary = {
        "n_dual_labeled": n,
        "n_batches_paired": len(coverage["paired"]),
        "coverage": {k: v for k, v in coverage.items() if v},
        "agreement": {
            "verdict": round(df["verdict_agree"].mean(), 4),
            "code_exact": round(df["code_agree"].mean(), 4),
            "division": round(df["division_agree"].mean(), 4),
        },
        "disagreement_breakdown": df["disagreement_type"].value_counts().to_dict(),
        "n_disagreements": int((df["disagreement_type"] != "agree").sum()),
        "invalid_codes": {
            "pass_a": int((~df["a_code_valid"]).sum()),
            "pass_b": int((~df["b_code_valid"]).sum()),
        },
        "outputs": {
            "merged": str(merged_path),
            "disagreements": str(dis_path),
        },
    }
    (OUT_DIR / f"gold_v5_gate1_summary{sfx}.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--only-types",
        nargs="*",
        default=None,
        help="Restrict disagreement CSV to these disagreement_type values",
    )
    ap.add_argument(
        "--tag",
        default="",
        help="Filename suffix for outputs (e.g. 5k) to avoid overwriting the 3k set",
    )
    ap.add_argument(
        "--min-batch",
        type=int,
        default=0,
        help="Only include batches with index >= this (scope a round, e.g. 54)",
    )
    args = ap.parse_args()
    s = build(args.only_types, args.tag, args.min_batch)
    print(json.dumps(s, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
