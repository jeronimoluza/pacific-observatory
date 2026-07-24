"""Turn anchor n-grams into a ready-to-label batch of REAL corpus product names.

Two anchor sets, one corpus pass:
  thin    reachable div-01 leaves with <10 gold whose anchor n-grams the food gate
          kept (fills a thin leaf + covers corpus).
  rollup  the six high-corpus-mass catch-all leaves (bakery / confectionery /
          sauces / chocolate / soft drinks / bread).

For each anchor n-gram we grep the LATIN corpus for product names that contain it
(as a phrase over content tokens), dedup, then re-score each NAME through the same
frozen Qwen + v6 head. Each candidate row carries:
  anchor_leaf   the leaf the bare n-gram predicted (why we pulled the name)
  pred_leaf     what the head predicts for the FULL name
  conf/accepted head confidence on the full name (accepted = conf>=tau)
  agree         pred_leaf == anchor_leaf  (anchor is a reliable cue in context)

`agree` + `accepted` are the two measurable signals; TRUE label precision still
needs the dual-labeler. Prototype: writes candidate parquet, touches nothing live.
"""

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_gold_roundN_candidates import _gold_leaf_counts, _load_leaves  # noqa: E402
from prices.enrich.boilerplate import strip_boilerplate  # noqa: E402
from prices.enrich.classifier.predict import load_predictor  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
GOLD_DIR = ROOT / "data" / "prices" / "enrich" / "gold"
CORPUS = ROOT / "data" / "prices" / "_enrich" / "products_input.parquet"
PROBE = GOLD_DIR / "corpus_ngram_head_probe.parquet"
OUT = GOLD_DIR / "label_candidates.parquet"

ROLLUP_LEAVES = {
    "01.1.1.3.9",
    "01.1.8.9.9",
    "01.1.9.3.9",
    "01.1.8.5.1",
    "01.2.6.0.0",
    "01.1.1.3.1",
}
TARGET = 10
CAP_PER_LEAF = 60

_WORD = re.compile(r"[a-z0-9]+")
_NONLATIN = re.compile(r"[一-鿿가-힣぀-ヿ฀-๿؀-ۿЀ-ӿ]")
_UNIT = {
    "g",
    "kg",
    "mg",
    "ml",
    "l",
    "cl",
    "oz",
    "lb",
    "ct",
    "pc",
    "pcs",
    "pack",
    "packs",
    "pk",
    "x",
    "cm",
    "mm",
    "gm",
    "gr",
    "kgs",
    "ltr",
    "pieces",
    "piece",
    "count",
    "s",
}


def _content_tokens(name: str) -> list[str]:
    toks = _WORD.findall(str(name).lower())
    return [t for t in toks if not t.isdigit() and t not in _UNIT and len(t) > 1]


def _ngrams(toks: list[str]) -> set[str]:
    out = set()
    for n in (2, 3):
        for i in range(len(toks) - n + 1):
            out.add(" ".join(toks[i : i + n]))
    return out


def _anchors(counts: dict, leaves: dict) -> dict:
    """anchor n-gram -> anchor_leaf, for both thin and rollup sets."""
    df = pd.read_parquet(PROBE)
    df = df[df["gate_food"] & ~df["covered"]].copy()
    df["gold_now"] = df["pred_leaf"].map(lambda c: counts.get(c, 0))
    thin = df[df["pred_leaf"].isin(leaves) & (df["gold_now"] < TARGET)]
    roll = df[df["pred_leaf"].isin(ROLLUP_LEAVES)]
    keep = pd.concat([thin, roll], ignore_index=True).drop_duplicates("ngram")
    return dict(zip(keep["ngram"], keep["pred_leaf"]))


def _grep(anchors: dict) -> dict:
    """anchor_leaf -> {name: matched_ngram} over the latin corpus, capped."""
    df = pd.read_parquet(CORPUS, columns=["product_name_original"])
    names = df["product_name_original"].astype(str).drop_duplicates().to_numpy()
    per_leaf: dict = defaultdict(dict)
    for nm in names:
        if _NONLATIN.search(nm):
            continue
        toks = _content_tokens(strip_boilerplate(nm))
        if len(toks) < 2:
            continue
        grams = _ngrams(toks)
        for g in grams:
            leaf = anchors.get(g)
            if leaf is None or len(per_leaf[leaf]) >= CAP_PER_LEAF:
                continue
            if nm not in per_leaf[leaf]:
                per_leaf[leaf][nm] = g
    return per_leaf


def build() -> pd.DataFrame:
    counts = _gold_leaf_counts()
    leaves = _load_leaves()
    anchors = _anchors(counts, leaves)
    per_leaf = _grep(anchors)

    rows = []
    for leaf, hits in per_leaf.items():
        for nm, g in hits.items():
            rows.append({"anchor_leaf": leaf, "anchor_ngram": g, "name": nm})
    cand = pd.DataFrame(rows)
    if cand.empty:
        return cand

    pred = load_predictor()
    p = pred.predict(cand["name"].tolist())
    cand["pred_leaf"] = [str(x) for x in p.leaf]
    cand["conf"] = [round(float(x), 3) for x in p.conf]
    cand["accepted"] = [bool(x) for x in p.accepted]
    cand["agree"] = cand["pred_leaf"] == cand["anchor_leaf"]
    cand["anchor_name"] = cand["anchor_leaf"].map(lambda c: leaves.get(c, "")[:40])
    cand["gold_now"] = cand["anchor_leaf"].map(lambda c: counts.get(c, 0))
    cand["batch"] = cand["anchor_leaf"].map(
        lambda c: "rollup" if c in ROLLUP_LEAVES else "thin"
    )
    cand.to_parquet(OUT, index=False)
    return cand


def _leaf_summary(cand: pd.DataFrame, batch: str) -> pd.DataFrame:
    d = cand[cand["batch"] == batch]
    g = d.groupby(["anchor_leaf", "anchor_name"]).agg(
        gold_now=("gold_now", "first"),
        names=("name", "nunique"),
        head_agree=("agree", "mean"),
        head_accept=("accepted", "mean"),
    )
    g["names_short"] = g["names"] < TARGET
    return g.sort_values("names", ascending=False).reset_index()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--show", type=int, default=12)
    args = ap.parse_args()
    cand = build()
    if cand.empty:
        print("no candidates")
        return
    print(
        f"total candidate names: {len(cand):,} | leaves: {cand['anchor_leaf'].nunique()}"
    )

    for batch in ("thin", "rollup"):
        s = _leaf_summary(cand, batch)
        n_short = int(s["names_short"].sum())
        print(
            f"\n=== {batch.upper()} — {len(s)} leaves | "
            f"{n_short} cannot reach {TARGET} distinct names from anchors ==="
        )
        with pd.option_context("display.max_rows", 40, "display.max_colwidth", 44):
            print(
                s[
                    [
                        "anchor_leaf",
                        "anchor_name",
                        "gold_now",
                        "names",
                        "head_agree",
                        "head_accept",
                    ]
                ].to_string(index=False)
            )
        print("\n  sample names (agree=head confirms anchor):")
        d = cand[cand["batch"] == batch].sort_values(
            ["anchor_leaf", "agree", "conf"], ascending=[True, False, False]
        )
        for leaf in s["anchor_leaf"].head(args.show):
            sub = d[d["anchor_leaf"] == leaf].head(4)
            nm = leaves_name.get(leaf, leaf)
            print(f"    {leaf} {nm}")
            for _, r in sub.iterrows():
                mark = "OK " if r["agree"] else ("~  " if r["accepted"] else " . ")
                print(
                    f"      {mark} [{r['pred_leaf']} {r['conf']:.2f}] {r['name'][:60]}"
                )
    print(f"\nwrote -> {OUT}")


leaves_name = _load_leaves()

if __name__ == "__main__":
    main()
