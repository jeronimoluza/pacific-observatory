"""Assemble gold-v5 FINAL from consensus + Gate-1 adjudications (W3.2 -> gold).

Final label per row:
  - disagreement_type == 'agree'  -> the A/B consensus label (label_source=consensus_AB)
  - otherwise                     -> the Sonnet Gate-1 adjudication (label_source=gate1_adjudicated)

Reads gate1/gold_v5_merged.parquet (all 3000 dual-labeled rows) and every
gate1/adjudications/adjud_out_*.json. Verifies full 3000-row coverage and that
every leaf code is a real taxonomy leaf before writing gold_v5_final.parquet.
"""

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from prices.enrich import config  # noqa: E402
from prices.enrich.tier_b.taxonomy_index import load_taxonomy_index  # noqa: E402

GATE_DIR = config.REPO_ROOT / "data" / "prices" / "enrich" / "gold" / "gate1"
ADJ_DIR = GATE_DIR / "adjudications"
GOLD_DIR = config.REPO_ROOT / "data" / "prices" / "enrich" / "gold"


def _load_adjudications() -> dict:
    out = {}
    for f in sorted(ADJ_DIR.glob("adjud_out_*.json")):
        for o in json.loads(Path(f).read_text()):
            out[str(o["gold_row_id"])] = o
    return out


def build(
    merged_name="gold_v5_merged.parquet", out_name="gold_v5_final.parquet"
) -> dict:
    leaves, _ = load_taxonomy_index()
    merged = pd.read_parquet(GATE_DIR / merged_name)
    adj = _load_adjudications()

    disagree_ids = set(
        merged.loc[merged["disagreement_type"] != "agree", "gold_row_id"].astype(str)
    )
    missing = disagree_ids - set(adj)
    if missing:
        raise SystemExit(
            f"{len(missing)} disagreement rows not yet adjudicated (e.g. "
            f"{sorted(missing)[:5]}) — adjudication incomplete."
        )

    rows = []
    for _, r in merged.iterrows():
        rid = str(r["gold_row_id"])
        base = {
            "gold_row_id": rid,
            "batch": r["batch"],
            "product_name": r["product_name"],
            "country": r["country"],
            "source": r["source"],
            "channel": r["channel"],
            "category": r["category"],
            "declared_coicop_codes": r["declared_coicop_codes"],
            "price": r["price"],
        }
        if r["disagreement_type"] == "agree":
            base.update(
                {
                    "verdict": r["a_verdict"],
                    "code": r["a_code"],
                    "division": r["a_division"],
                    "pricing_basis_plausible": r["a_basis"],
                    "label_source": "consensus_AB",
                    "confidence": "high",
                    "adjudicator_match": "",
                    "disagreement_type": "agree",
                }
            )
        else:
            a = adj[rid]
            base.update(
                {
                    "verdict": a.get("verdict", ""),
                    "code": a.get("code", "") or "",
                    "division": str(a.get("division", "")),
                    "pricing_basis_plausible": str(
                        a.get("pricing_basis_plausible", "")
                    ),
                    "label_source": "gate1_adjudicated",
                    "confidence": a.get("confidence", ""),
                    "adjudicator_match": a.get("matches_candidate", ""),
                    "disagreement_type": r["disagreement_type"],
                }
            )
        rows.append(base)

    df = pd.DataFrame(rows)

    bad = df[(df["verdict"] == "leaf") & (~df["code"].isin(leaves))]
    if len(bad):
        raise SystemExit(
            f"{len(bad)} final rows have invalid leaf codes: "
            f"{bad['gold_row_id'].head().tolist()}"
        )
    if len(df) != len(merged):
        raise SystemExit(f"row count mismatch: {len(df)} vs {len(merged)}")

    out_path = GOLD_DIR / out_name
    df.to_parquet(out_path, index=False)

    summary = {
        "n_total": len(df),
        "by_source": df["label_source"].value_counts().to_dict(),
        "verdict_dist": df["verdict"].value_counts().to_dict(),
        "adjudicated_match_dist": df.loc[
            df["label_source"] == "gate1_adjudicated", "adjudicator_match"
        ]
        .value_counts()
        .to_dict(),
        "adjudicated_confidence": df.loc[
            df["label_source"] == "gate1_adjudicated", "confidence"
        ]
        .value_counts()
        .to_dict(),
        "n_distinct_leaves": int(df.loc[df["verdict"] == "leaf", "code"].nunique()),
        "n_countries": int(df["country"].nunique()),
        "output": str(out_path),
    }
    (GOLD_DIR / (out_name.replace(".parquet", "_summary.json"))).write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return summary


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--merged", default="gold_v5_merged.parquet")
    ap.add_argument("--out", default="gold_v5_final.parquet")
    args = ap.parse_args()
    build(args.merged, args.out)
