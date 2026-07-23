"""Evaluate the (embedding -> head) classifier on gold via cross-validation.

Scores the config-E operating point — a single global confidence gate at the
target precision plus per-leaf trap vetoes — over the gold food/bev leaves using
out-of-fold predictions (no row is scored by a head that trained on it). Reports
overall precision and coverage plus a per-leaf breakdown. This is the canonical
``prices eval`` and reproduces the deep-leaf CV result (~98% precision at ~82%
coverage on division 01).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold

from prices.enrich import config, embedding, vetoes
from prices.enrich.classifier.dataset import MIN_SUPPORT, _load_gold
from prices.enrich.classifier.train import (
    C_INV_REG,
    MAX_ITER,
    OOF_FOLDS,
    OOF_SEED,
    TARGET_PRECISION,
    _global_tau,
)


def _oof(x: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    skf = StratifiedKFold(OOF_FOLDS, shuffle=True, random_state=OOF_SEED)
    pred = np.empty(len(y), object)
    conf = np.zeros(len(y))
    for tr, te in skf.split(x, y):
        lr = LogisticRegression(max_iter=MAX_ITER, C=C_INV_REG).fit(x[tr], y[tr])
        p = lr.predict_proba(x[te])
        pred[te] = lr.classes_[p.argmax(1)]
        conf[te] = p.max(1)
    return pred, conf


def evaluate(
    division: str = config.CLASSIFIER_DEFAULT_DIVISION,
    target_precision: float = TARGET_PRECISION,
) -> dict:
    g = _load_gold()
    g = g[(g["verdict"] == "leaf") & (g["division"] == division)].copy()
    vc = g["code"].value_counts()
    g = g[g["code"].isin(set(vc[vc >= MIN_SUPPORT].index))].reset_index(drop=True)

    names = g["product_name"].astype(str).tolist()
    y = g["code"].astype(str).to_numpy()
    x = embedding.embed_names(names)

    pred, conf = _oof(x, y)
    tau = _global_tau(conf, pred == y, target_precision)
    pred = np.array(pred, dtype=object)
    force_reject = np.zeros(len(pred), dtype=bool)
    force_accept = np.zeros(len(pred), dtype=bool)
    for i, (p, n) in enumerate(zip(pred, names)):
        action = vetoes.veto_action(p, n)
        if action is None:
            continue
        if action == vetoes.REJECT:
            force_reject[i] = True
        else:
            pred[i] = action
            force_accept[i] = True
    correct = pred == y
    accepted = ((conf >= tau) & ~force_reject) | force_accept

    tp = int((accepted & correct).sum())
    fired = int(accepted.sum())
    n = len(y)
    result = {
        "division": division,
        "n_rows": n,
        "n_leaves": int(pd.Series(y).nunique()),
        "tau": round(float(tau), 4),
        "target_precision": target_precision,
        "fired": fired,
        "precision": round(tp / fired, 4) if fired else float("nan"),
        "coverage": round(tp / n, 4) if n else float("nan"),
    }

    df = pd.DataFrame({"true": y, "pred": pred, "acc": accepted, "corr": correct})
    per_leaf = []
    for leaf, grp in df.groupby("true"):
        fl = grp[grp["acc"]]
        per_leaf.append(
            {
                "leaf": leaf,
                "true_n": len(grp),
                "fired": int(len(fl)),
                "tp": int(fl["corr"].sum()),
            }
        )
    result["per_leaf"] = sorted(per_leaf, key=lambda r: -r["true_n"])
    return result


def run(
    division: str = config.CLASSIFIER_DEFAULT_DIVISION,
    target_precision: float = TARGET_PRECISION,
) -> dict:
    r = evaluate(division, target_precision)
    print(
        f"division {r['division']}: {r['n_rows']} rows / {r['n_leaves']} leaves | "
        f"tau@{target_precision:.0%}={r['tau']} | fired={r['fired']} | "
        f"precision={r['precision']:.1%} coverage={r['coverage']:.1%}"
    )
    print(f"  {'leaf':<12}{'true_N':>7}{'fired':>7}{'TP':>5}{'prec':>7}{'cov%':>7}")
    for pl in r["per_leaf"]:
        fired, tp, tn = pl["fired"], pl["tp"], pl["true_n"]
        prec = f"{tp / fired:.0%}" if fired else "-"
        cov = f"{tp / tn:.0%}" if tn else "-"
        print(f"  {pl['leaf']:<12}{tn:>7}{fired:>7}{tp:>5}{prec:>7}{cov:>7}")
    return r
