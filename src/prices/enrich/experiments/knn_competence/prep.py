"""Stage 1 — build the held-out eval items with KNN candidates + difficulty.

Splits the (corrected) div-01 gold name-disjointly into an INDEX pool and an
EVAL pool, embeds both with the production ensemble (block-cached → cheap), and
for each EVAL item retrieves its K nearest INDEX neighbours by cosine. The
distinct neighbour leaves become the grounded candidate set; the entropy of the
neighbour-leaf vote distribution is the difficulty signal. Emits one JSONL row
per sampled eval item, stratified across entropy deciles so the difficulty axis
is actually spanned.

Run: python -m prices.enrich.experiments.knn_competence.prep [--n 400] [--k 12]
"""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path

import numpy as np

from prices.enrich import config
from prices.enrich.classifier.dataset import _load_gold

GOLD_DIR = config.REPO_ROOT / "data" / "prices" / "enrich" / "gold"
CATEGORIES_CSV = (
    config.REPO_ROOT / "data" / "prices" / "enrich" / "coicop_categories.csv"
)
OUT_DIR = (
    config.REPO_ROOT / "data" / "prices" / "enrich" / "_experiments" / "knn_competence"
)
SEED = 0


def _leaf_titles() -> dict[str, str]:
    out: dict[str, str] = {}
    for line in (GOLD_DIR / "coicop_leaves.txt").read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        parts = re.split(r"[\t ]", line, 1)
        out[parts[0]] = parts[1].strip() if len(parts) > 1 else ""
    return out


def _subclass_notes() -> tuple[dict[str, str], dict[str, str]]:
    import pandas as pd

    t = pd.read_csv(CATEGORIES_CSV)
    note = dict(zip(t["coicop_code"].astype(str), t["keywords"].astype(str)))
    title = dict(zip(t["coicop_code"].astype(str), t["coicop_title"].astype(str)))
    return note, title


def candidate_note(leaf: str, leaf_titles, sub_note, sub_title) -> str:
    """One grounded-choice line: leaf code + title + parent subclass note."""
    parent = ".".join(leaf.split(".")[:4])
    lt = leaf_titles.get(leaf, "")
    note = sub_note.get(parent, "")
    note = re.sub(r"\s+", " ", note)[:360]
    st = sub_title.get(parent, "")
    return f"{leaf} — {lt} (subclass {parent} {st}: {note})"


def _entropy_bits(counts: list[int]) -> float:
    n = sum(counts)
    if n == 0:
        return 0.0
    ent = 0.0
    for c in counts:
        if c:
            p = c / n
            ent -= p * math.log2(p)
    return ent


def build(n: int = 400, k: int = 12) -> Path:
    leaf_titles = _leaf_titles()
    valid = set(leaf_titles)
    sub_note, sub_title = _subclass_notes()

    g = _load_gold()
    g = g[(g["verdict"] == "leaf") & (g["division"] == "01")].copy()
    g = g[g["code"].isin(valid)]
    # one row per product name (name-disjoint truth), keep first label
    g["product_name"] = g["product_name"].astype(str)
    g = g.drop_duplicates(subset="product_name").reset_index(drop=True)

    rng = np.random.default_rng(SEED)
    perm = rng.permutation(len(g))
    n_eval_pool = max(n * 3, int(0.2 * len(g)))
    eval_idx = set(perm[:n_eval_pool].tolist())
    ev = g.iloc[sorted(eval_idx)].reset_index(drop=True)
    ix = g.iloc[[i for i in range(len(g)) if i not in eval_idx]].reset_index(drop=True)

    from prices.enrich import embedding

    print(f"embedding index ({len(ix)}) + eval-pool ({len(ev)}) names ...")
    ix_mat = embedding.embed_names(ix["product_name"].tolist())
    ev_mat = embedding.embed_names(ev["product_name"].tolist())
    ix_mat = ix_mat / (np.linalg.norm(ix_mat, axis=1, keepdims=True) + 1e-9)
    ev_mat = ev_mat / (np.linalg.norm(ev_mat, axis=1, keepdims=True) + 1e-9)

    ix_codes = ix["code"].to_numpy()
    sims = ev_mat @ ix_mat.T  # (n_eval, n_index)
    knn = np.argpartition(-sims, kth=k, axis=1)[:, :k]

    rows = []
    for i in range(len(ev)):
        nbr = knn[i]
        nbr = nbr[np.argsort(-sims[i, nbr])]
        nbr_codes = [str(ix_codes[j]) for j in nbr]
        nbr_sims = [float(sims[i, j]) for j in nbr]
        # candidate leaves = distinct neighbour codes, ordered by first appearance
        cand, counts = [], {}
        for c in nbr_codes:
            counts[c] = counts.get(c, 0) + 1
            if c not in cand:
                cand.append(c)
        true_code = str(ev.loc[i, "code"])
        rows.append(
            {
                "name": str(ev.loc[i, "product_name"]),
                "country": str(ev.loc[i, "country"]),
                "true_code": true_code,
                "candidates": cand,
                "candidate_notes": [
                    candidate_note(c, leaf_titles, sub_note, sub_title) for c in cand
                ],
                "knn_codes": nbr_codes,
                "knn_entropy_bits": round(_entropy_bits(list(counts.values())), 4),
                "n_distinct_candidates": len(cand),
                "top_candidate_share": round(max(counts.values()) / k, 4),
                "nn_cosine": round(nbr_sims[0], 4),
                "true_in_candidates": true_code in cand,
                "knn_top1_correct": nbr_codes[0] == true_code,
            }
        )

    # stratified sample across entropy deciles so the x-axis is spanned
    ent = np.array([r["knn_entropy_bits"] for r in rows])
    order = np.argsort(ent)
    bins = np.array_split(order, 10)
    per_bin = max(1, n // 10)
    picked: list[int] = []
    for b in bins:
        take = rng.permutation(b)[:per_bin]
        picked.extend(take.tolist())
    picked = picked[:n]
    items = [rows[i] for i in picked]

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "eval_items.jsonl"
    with open(out, "w") as f:
        for r in items:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    reach = np.mean([r["true_in_candidates"] for r in items])
    knn_acc = np.mean([r["knn_top1_correct"] for r in items])
    print(f"wrote {len(items)} items -> {out}")
    print(f"  KNN reachability (true in candidates): {reach:.1%}")
    print(f"  KNN top-1 accuracy (no LLM): {knn_acc:.1%}")
    print(f"  entropy span: {ent.min():.2f} .. {ent.max():.2f} bits")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=400)
    ap.add_argument("--k", type=int, default=12)
    args = ap.parse_args()
    build(n=args.n, k=args.k)


if __name__ == "__main__":
    main()
