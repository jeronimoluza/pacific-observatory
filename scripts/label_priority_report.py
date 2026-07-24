"""What to label next: corpus-frequent, food-gated, gold-UNCOVERED n-grams.

Joins the head-probe table (corpus_df + leaf-head prediction + binary food gate)
with gold leaf depth so each candidate phrase carries: how many corpus rows it
covers (corpus_df), which leaf the head assigns, how much gold that leaf already
has, and whether the head is confident. Ranks by corpus mass so each label
retires the most observations.

Priority:
  TEACH   food-gated, uncovered, head-UNCERTAIN (conf < tau) — common corpus
          pattern the model does not yet nail; labeling lifts coverage AND head
          confidence. Highest ROI, especially into reachable thin leaves.
  CONFIRM food-gated, uncovered, head-confident — model already handles it but
          gold has no anchor; cheap verification / reinforcement.

Also rolls up to the leaf: total uncovered corpus mass reachable per leaf, so you
can see which leaves' vocabulary the corpus most wants gold to cover.
"""

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_gold_roundN_candidates import (  # noqa: E402
    GOLD_DIR,
    _gold_leaf_counts,
    _load_leaves,
)

PROBE = GOLD_DIR / "corpus_ngram_head_probe.parquet"
OUT = GOLD_DIR / "label_priority_report.parquet"
TARGET = 10


def build() -> pd.DataFrame:
    df = pd.read_parquet(PROBE)
    if "gate_food" not in df.columns:
        raise SystemExit("probe table has no gate columns; run train_food_gate.py")
    counts = _gold_leaf_counts()
    leaves = _load_leaves()  # reachable div-01 -> name

    df = df[df["gate_food"] & ~df["covered"]].copy()
    df["gold_now"] = df["pred_leaf"].map(lambda c: counts.get(c, 0))
    df["reachable"] = df["pred_leaf"].map(lambda c: c in leaves)
    df["thin"] = df["gold_now"] < TARGET
    df["priority"] = df["accepted"].map(lambda a: "CONFIRM" if a else "TEACH")
    df = df.sort_values("corpus_df", ascending=False).reset_index(drop=True)
    df.to_parquet(OUT, index=False)
    return df


def _leaf_rollup(df: pd.DataFrame) -> pd.DataFrame:
    r = (
        df[df["reachable"]]
        .groupby("pred_leaf")
        .agg(
            leaf_name=("leaf_name", "first"),
            gold_now=("gold_now", "first"),
            uncovered_ngrams=("ngram", "size"),
            corpus_mass=("corpus_df", "sum"),
        )
    )
    return r.sort_values("corpus_mass", ascending=False).reset_index()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--show", type=int, default=45)
    ap.add_argument("--min-conf", type=float, default=0.0)
    args = ap.parse_args()
    df = build()
    df = df[df["conf"] >= args.min_conf] if args.min_conf else df

    n = len(df)
    teach = df[df["priority"] == "TEACH"]
    print(
        f"food-gated + uncovered candidate phrases: {n:,} | "
        f"TEACH (head-uncertain): {len(teach):,} | "
        f"CONFIRM (head-confident): {n - len(teach):,}"
    )
    print(
        f"landing in reachable thin leaves (<{TARGET} gold): "
        f"{int((df['reachable'] & df['thin']).sum()):,}"
    )

    cols = [
        "ngram",
        "corpus_df",
        "priority",
        "pred_leaf",
        "leaf_name",
        "gold_now",
        "thin",
        "conf",
        "food_gate",
    ]
    print(
        f"\n=== LABEL NEXT — top {args.show} corpus-frequent uncovered food phrases ==="
    )
    with pd.option_context(
        "display.max_rows", args.show + 5, "display.max_colwidth", 40
    ):
        print(df.head(args.show)[cols].to_string(index=False))

    print("\n=== into REACHABLE THIN leaves (fills gold + covers corpus) — top 25 ===")
    thin = df[df["reachable"] & df["thin"]]
    with pd.option_context("display.max_rows", 30, "display.max_colwidth", 40):
        print(thin.head(25)[cols].to_string(index=False))

    print("\n=== LEAF rollup — reachable leaves by uncovered corpus mass, top 25 ===")
    roll = _leaf_rollup(df)
    with pd.option_context("display.max_rows", 30, "display.max_colwidth", 40):
        print(roll.head(25).to_string(index=False))
    print(f"\nwrote -> {OUT}")


if __name__ == "__main__":
    main()
