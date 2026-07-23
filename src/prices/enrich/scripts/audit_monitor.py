"""Basis-audit monitor -- READ half only (AUDIT_LAYER_SPEC_v2 §5 / §9.6).

Graduated from tmp/audit_layer.py's histogram-emitting main(). Observes, over
ALL accepted classifier predictions with a structural basis -- pre-audit-filter,
so rows the basis-audit would REJECT are still counted -- which pricing_basis
values actually appear per COICOP leaf. Proposes a per-leaf evidence_state
(§2) from the observed count. It PROPOSES only: it never mutates the
denylist parquet, and the human-review flag is always left unset.

Run:
    PYTHONPATH=src <venv>/bin/python src/prices/enrich/scripts/audit_monitor.py \
        [--n-confirm 10]
"""

from __future__ import annotations

import argparse
import os
from collections import Counter, defaultdict

import numpy as np
import pandas as pd

from prices.enrich import audit, config, embedding
from prices.enrich.classifier.predict import load_predictor
from prices.enrich.extract import extract

OUT_DIR = config.REPO_ROOT / "data" / "prices" / "enrich" / "_monitor"

CONTRADICTION_MIN_N = 3

CONFIRMED_CANDIDATE = "CONFIRMED_CANDIDATE"
THIN = "THIN"
UNOBSERVED = "UNOBSERVED"


def _load_cached_names() -> list[str]:
    corpus = pd.read_parquet(config.PRODUCTS_INPUT_PARQUET)
    names_all = corpus["product_name_original"].astype(str).drop_duplicates().tolist()
    z = np.load(config.CLASSIFIER_EMBED_CACHE_DIR / "vectors.npz", allow_pickle=True)
    cached = set(z["keys"].tolist())
    return [n for n in names_all if embedding._key(n) in cached]


def _predict_and_count(cached_names, denylist):
    pred = load_predictor("v6")
    r = pred.predict(cached_names)

    leaf_basis = defaultdict(Counter)
    verdicts = Counter()
    n_accepted = 0
    for nm, lf, acc in zip(cached_names, r.leaf, r.accepted):
        if not acc:
            continue
        n_accepted += 1
        basis = extract(str(nm), None, None, None).pricing_basis
        if not basis:
            continue
        leaf_basis[str(lf)][basis] += 1
        v = audit.audit(str(lf), basis, denylist)
        verdicts[v] += 1
    return leaf_basis, verdicts, n_accepted


def _evidence_state(n_leaf_total: int, n_confirm: int) -> str:
    if n_leaf_total == 0:
        return UNOBSERVED
    if n_leaf_total >= n_confirm:
        return CONFIRMED_CANDIDATE
    return THIN


def build_histogram(leaf_basis, denylist, n_confirm: int) -> pd.DataFrame:
    rows = []
    empty_entry = {
        "excluded": frozenset(),
        "action": "",
        "semantic": "",
        "evidence_state": "",
        "label": "",
        "profile": "",
    }
    for lf, bd in leaf_basis.items():
        entry = denylist.get(lf, empty_entry)
        total = sum(bd.values())
        proposed = _evidence_state(total, n_confirm)
        for b, c in bd.items():
            if b in entry["excluded"]:
                tag = f"EXCLUDED-{entry['semantic']}-{entry['action']}"
            else:
                tag = "allowed"
            rows.append(
                {
                    "leaf": lf,
                    "label": entry["label"],
                    "profile": entry["profile"],
                    "basis": b,
                    "n": c,
                    "share": round(c / total, 4),
                    "tag": tag,
                    "denylist_evidence_state": entry["evidence_state"],
                    "leaf_total_n": total,
                    "proposed_evidence_state": proposed,
                    "n_confirm": n_confirm,
                    "human_reviewed": False,
                }
            )
    return pd.DataFrame(rows).sort_values(["leaf", "n"], ascending=[True, False])


def build_contradiction_candidates(hist: pd.DataFrame) -> pd.DataFrame:
    contra = hist[hist["tag"].str.startswith("EXCLUDED")]
    return contra[contra["n"] >= CONTRADICTION_MIN_N].sort_values("n", ascending=False)


def main(n_confirm: int = 10) -> None:
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    denylist = audit.load_denylist(config.BASIS_DENYLIST_PARQUET)
    print("denylist leaves:", len(denylist))

    cached_names = _load_cached_names()
    print("cached corpus names (free to predict):", len(cached_names))

    leaf_basis, verdicts, n_accepted = _predict_and_count(cached_names, denylist)
    print("accepted predictions:", n_accepted)
    print("audit verdicts over accepted preds (pre-histogram, same population):")
    for k in (audit.PASS, audit.NO_STRUCTURAL, audit.FLAG, audit.REJECT):
        print(f"  {k:14s} {verdicts[k]:6d}")

    hist = build_histogram(leaf_basis, denylist, n_confirm)
    contra = build_contradiction_candidates(hist)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    hist_parquet = OUT_DIR / "basis_histogram.parquet"
    hist_csv = OUT_DIR / "basis_histogram.csv"
    contra_csv = OUT_DIR / "contradiction_candidates.csv"

    hist.to_parquet(hist_parquet, index=False)
    hist.to_csv(hist_csv, index=False)
    contra.to_csv(contra_csv, index=False)

    # Full evidence-state distribution over ALL denylist leaves (not just the
    # ones with observed rows above) -- leaves never seen in the corpus at
    # all are UNOBSERVED and would otherwise be invisible to the histogram.
    observed_totals = {lf: sum(bd.values()) for lf, bd in leaf_basis.items()}
    all_leaves = set(denylist) | set(observed_totals)
    state_counts = Counter(
        _evidence_state(observed_totals.get(lf, 0), n_confirm) for lf in all_leaves
    )

    print("\nn_confirm:", n_confirm)
    print("histogram rows:", len(hist))
    print("contradiction candidates (n >=", CONTRADICTION_MIN_N, "):", len(contra))
    print(
        "proposed evidence_state distribution (all denylist + observed leaves,",
        len(all_leaves),
        "total):",
    )
    for k in (CONFIRMED_CANDIDATE, THIN, UNOBSERVED):
        print(f"  {k:20s} {state_counts[k]:5d}")
    print("\nwrote", hist_parquet)
    print("wrote", hist_csv)
    print("wrote", contra_csv)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-confirm", type=int, default=10)
    args = parser.parse_args()
    main(n_confirm=args.n_confirm)
