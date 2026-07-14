"""Coverage-ROI report for the next gold-expansion round (div-01 F&B).

For every still-thin REACHABLE div-01 leaf (< TARGET gold), estimate how many
labels-worth of corpus it can unlock BEFORE spending the budget. The key ROI
number is unique corpus rows reachable by the leaf's mined accept-patterns (a
require-list) divided by how many more labels the leaf still needs.

Ranks by "rows per needed label" so you can see which thin leaves give the most
corpus reach per label. Answers: where does the next round's labeling budget buy
the most classifiable corpus?

Reuses the round-N sampler's ngram / gating / gold helpers verbatim so the report
matches exactly what the sampler will require-list. Reads the refreshed
accept_patterns.parquet (run mine_ngram_patterns.py --round N first).
"""

import argparse
import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_gold_roundN_candidates import (  # noqa: E402
    ACCEPT_PATH,
    EXCLUDE_RX,
    GOLD_DIR,
    _gold_leaf_counts,
    _gold_names,
    _load_accept,
    _load_corpus,
    _load_leaves,
    _name_ngrams,
    _norm_key,
)

TARGET = 10
OUT = GOLD_DIR / "coverage_roi_report.parquet"


def _reachable_rows(thin_accept: dict, exclude: set) -> dict:
    """One corpus scan. leaf -> set of unique corpus names its accept-patterns hit
    (pet-food/merch rows and names already in gold removed)."""
    ng_to_leaves = defaultdict(list)
    for leaf, ngs in thin_accept.items():
        for g in ngs:
            ng_to_leaves[g].append(leaf)
    accept_set = set(ng_to_leaves)

    reach = defaultdict(set)
    corpus = _load_corpus()
    names = corpus["product_name_original"].to_numpy()
    for name in names:
        if EXCLUDE_RX.search(name.lower()):
            continue
        hit = _name_ngrams(name) & accept_set
        if not hit:
            continue
        if _norm_key(name) in exclude:
            continue
        for g in hit:
            for leaf in ng_to_leaves[g]:
                reach[leaf].add(name)
    return reach


def build(target: int) -> pd.DataFrame:
    leaves = _load_leaves()  # reachable div-01, name lookup
    counts = _gold_leaf_counts()
    exclude = _gold_names()
    accept = (
        _load_accept()
    )  # leaf -> gated require-list ngrams (div-01, pure, no-digit)

    thin = {c for c in leaves if counts.get(c, 0) < target}
    thin_accept = {c: accept[c] for c in thin if c in accept}
    reach = _reachable_rows(thin_accept, exclude)

    # per-pattern corpus_coverage for the top-pattern preview
    ap = pd.read_parquet(ACCEPT_PATH)
    cov = dict(zip(ap["pattern"], ap["corpus_coverage"]))

    rows = []
    for c in sorted(thin):
        gold_now = counts.get(c, 0)
        gap = target - gold_now
        pats = accept.get(c, set())
        n_reach = len(reach.get(c, ()))
        top = sorted(pats, key=lambda p: cov.get(p, 0), reverse=True)[:3]
        top_str = ", ".join(f"{p}({int(cov.get(p, 0))})" for p in top)
        rows.append(
            {
                "coicop_leaf": c,
                "leaf_name": leaves[c][:48],
                "gold_now": gold_now,
                "gap_to_target": gap,
                "n_patterns": len(pats),
                "reachable_corpus_rows": n_reach,
                "rows_per_needed_label": round(n_reach / gap, 1) if gap else 0.0,
                "top_patterns": top_str,
            }
        )
    df = (
        pd.DataFrame(rows)
        .sort_values(["reachable_corpus_rows", "gold_now"], ascending=[False, True])
        .reset_index(drop=True)
    )
    df.to_parquet(OUT, index=False)
    return df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", type=int, default=TARGET)
    ap.add_argument("--show", type=int, default=30)
    args = ap.parse_args()
    df = build(args.target)

    has = df[df["reachable_corpus_rows"] > 0]
    none = df[(df["n_patterns"] == 0)]
    print(f"still-thin reachable div-01 leaves (<{args.target} gold): {len(df)}")
    print(f"  with mineable corpus reach: {len(has)}")
    print(f"  with NO accept-patterns yet (need anchors/wild-mine): {len(none)}")
    print(
        f"\n=== top {args.show} by corpus reach (rows one label-batch can unlock) ==="
    )
    cols = [
        "coicop_leaf",
        "leaf_name",
        "gold_now",
        "gap_to_target",
        "reachable_corpus_rows",
        "rows_per_needed_label",
        "top_patterns",
    ]
    with pd.option_context("display.max_colwidth", 60, "display.width", 200):
        print(has[cols].head(args.show).to_string(index=False))
    if len(none):
        print(f"\n=== thin leaves with NO patterns ({len(none)}) — first 15 ===")
        print(
            none[["coicop_leaf", "leaf_name", "gold_now"]]
            .head(15)
            .to_string(index=False)
        )
    print(f"\nwrote -> {OUT}")


if __name__ == "__main__":
    main()
