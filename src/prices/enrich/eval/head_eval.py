"""Evaluate the (embedding -> head -> meta-gate) classifier on gold. `prices eval`.

The metric is COVERAGE AT A PRECISION FLOOR, not accuracy. The classifier may
decline: a threshold is set at the highest-recall point whose accepted set still
holds `--target-precision`, and coverage is (correct AND accepted) / all rows. A
more accurate model whose confidence RANK-ORDERS worse scores LOWER here, so
rank-ordering is the thing being measured.

Both gates are reported from one run, because the delta between them is the
entire case for the meta-gate and reporting either alone is misleading:

  raw   -- threshold on the head's own top-1 softmax probability
  gate  -- threshold on a second model's estimate of "will top-1 be correct?"

Scope defaults to ALL divisions rather than food. That is not scope creep: the
same model measures ~4pt HIGHER across all divisions than restricted to division
01, because it can spend confidence where the taxonomy is easy. Restricting the
scope costs coverage.

The three OOF tables (head, lexical, neighbours) are the expensive part -- ~1
hour at full scope -- so they are cached on disk under a key covering the block
layout, the weights, the scope and the exact row set. Change any of those and the
cache misses rather than silently answering for a different configuration.
"""

from __future__ import annotations

import pandas as pd

from prices.enrich import config
from prices.enrich.classifier import gate, oof, tables

TARGET_PRECISION = oof.TARGET_PRECISION
scope_gold = tables.scope_gold


def evaluate(scope: str = None, target_precision: float = TARGET_PRECISION,
             verbose: bool = True) -> dict:
    scope = scope or config.CLASSIFIER_DEFAULT_SCOPE
    g = scope_gold(scope)
    names = g["product_name"].astype(str).tolist()
    y = g["code"].astype(str).to_numpy()
    n = len(y)
    if verbose:
        print(f"scope={scope}: {n} rows / {g['code'].nunique()} leaves "
              f"({g.attrs['dropped_uncovered']} rows dropped as unembedded)", flush=True)

    cls, proba, cls_lex, proba_lex, nbr_idx, nbr_sim, _ = tables.oof_tables(
        g, scope, verbose=verbose
    )
    feats, leaf_pred, correct, force_rej, force_acc = tables.gate_inputs(
        cls, proba, cls_lex, proba_lex, nbr_idx, nbr_sim, y, names
    )
    if verbose:
        print("  cross-fitting the meta-gate", flush=True)
    gate_score = gate.cross_fit(feats, leaf_pred, correct)

    arms = {}
    for arm, s in (("raw", proba.max(1)), ("gate", gate_score)):
        tau = oof.choose_tau(s, correct, target_precision)
        arms[arm] = oof.summarize(s, correct, force_rej, force_acc, tau)

    accepted = arms["gate"]["accepted"]
    result = {
        "scope": scope,
        "n_rows": n,
        "n_leaves": int(pd.Series(y).nunique()),
        "n_dropped_uncovered": int(g.attrs["dropped_uncovered"]),
        "target_precision": target_precision,
        "head_accuracy": round(float(correct.mean()), 4),
        "blocks": [b["tag"] for b in config.CLASSIFIER_EMBED_ENSEMBLE],
        "weights": [float(b.get("weight", 1.0)) for b in config.CLASSIFIER_EMBED_ENSEMBLE],
        "gate_features": len(gate.GATE_COLS),
    }
    for arm in ("raw", "gate"):
        a = arms[arm]
        result[arm] = {k: a[k] for k in ("tau", "fired", "precision", "coverage")}

    df = pd.DataFrame({"true": y, "acc": accepted, "corr": correct})
    result["per_leaf"] = sorted(
        (
            {"leaf": leaf, "true_n": len(grp), "fired": int(grp["acc"].sum()),
             "tp": int((grp["acc"] & grp["corr"]).sum())}
            for leaf, grp in df.groupby("true")
        ),
        key=lambda r: -r["true_n"],
    )
    return result


def run(scope: str = None, target_precision: float = TARGET_PRECISION,
        top: int = 25) -> dict:
    r = evaluate(scope, target_precision)
    print(
        f"\nscope {r['scope']}: {r['n_rows']} rows / {r['n_leaves']} leaves | "
        f"blocks {'+'.join(r['blocks'])} w={r['weights']} | "
        f"head accuracy {r['head_accuracy']:.1%}"
    )
    print(f"  {'gate':<6}{'tau':>8}{'fired':>8}{'precision':>11}{'coverage':>10}")
    for arm in ("raw", "gate"):
        a = r[arm]
        print(f"  {arm:<6}{a['tau']:>8.4f}{a['fired']:>8}"
              f"{a['precision']:>10.1%}{a['coverage']:>10.1%}")
    lift = (r["gate"]["coverage"] - r["raw"]["coverage"]) * 100
    print(f"  meta-gate lift: {lift:+.2f} coverage points")
    if r["gate"]["precision"] < target_precision - 1e-9:
        print(f"  WARNING realized precision {r['gate']['precision']:.4f} is below "
              f"the {target_precision:.2f} floor — a tied score block crossed it")

    print(f"\n  {'leaf':<12}{'true_N':>7}{'fired':>7}{'TP':>6}{'prec':>7}{'cov%':>7}"
          f"   (top {top} by support)")
    for pl in r["per_leaf"][:top]:
        fired, tp, tn = pl["fired"], pl["tp"], pl["true_n"]
        prec = f"{tp / fired:.0%}" if fired else "-"
        cov = f"{tp / tn:.0%}" if tn else "-"
        print(f"  {pl['leaf']:<12}{tn:>7}{fired:>7}{tp:>6}{prec:>7}{cov:>7}")
    return r
