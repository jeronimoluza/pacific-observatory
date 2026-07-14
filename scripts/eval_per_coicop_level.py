"""Per-COICOP-level CV coverage + precision for the food/bev head (division 01).

The head predicts a 5-level leaf. This rolls the out-of-fold leaf probabilities up
to each COICOP granularity and gates each level independently at the same target
precision, so you can read the classic hierarchy tradeoff: coarse levels are near
full coverage at high precision; the leaf is the strict operating point.

Levels (dotted COICOP, e.g. 01.1.4.4.2):
  L1 division   01           L2 group    01.1        L3 class 01.1.4
  L4 subclass   01.1.4.4     L5 leaf     01.1.4.4.2

For each level k: aggregate leaf probabilities by k-level prefix (sum siblings),
take the argmax node + its summed prob as confidence, derive tau@target on the
out-of-fold correctness, and report coverage (fired/all) and precision (tp/fired).
Leaf-level trap vetoes (production overlay) are applied by leaf-argmax at every
level so L5 reproduces `prices eval`. Reuses the exact CV machinery of head_eval.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from prices.enrich import config, embedding, vetoes  # noqa: E402
from prices.enrich.classifier.dataset import MIN_SUPPORT, _load_gold  # noqa: E402
from prices.enrich.classifier.train import (  # noqa: E402
    C_INV_REG,
    MAX_ITER,
    OOF_FOLDS,
    OOF_SEED,
    TARGET_PRECISION,
    _global_tau,
)

LEVELS = [(1, "division"), (2, "group"), (3, "class"), (4, "subclass"), (5, "leaf")]


def _prefix(code: str, k: int) -> str:
    return ".".join(str(code).split(".")[:k])


def _oof_proba(x: np.ndarray, y: np.ndarray, classes: list) -> np.ndarray:
    """Out-of-fold probability matrix aligned to the global class column order."""
    cidx = {c: i for i, c in enumerate(classes)}
    proba = np.zeros((len(y), len(classes)))
    skf = StratifiedKFold(OOF_FOLDS, shuffle=True, random_state=OOF_SEED)
    for tr, te in skf.split(x, y):
        lr = LogisticRegression(max_iter=MAX_ITER, C=C_INV_REG).fit(x[tr], y[tr])
        p = lr.predict_proba(x[te])
        for j, c in enumerate(lr.classes_):
            proba[te, cidx[c]] = p[:, j]
    return proba


def run(division: str = config.CLASSIFIER_DEFAULT_DIVISION) -> pd.DataFrame:
    g = _load_gold()
    g = g[(g["verdict"] == "leaf") & (g["division"] == division)].copy()
    vc = g["code"].value_counts()
    g = g[g["code"].isin(set(vc[vc >= MIN_SUPPORT].index))].reset_index(drop=True)

    names = g["product_name"].astype(str).tolist()
    y = g["code"].astype(str).to_numpy()
    classes = sorted(set(y))
    x = embedding.embed_names(names)
    proba = _oof_proba(x, y, classes)

    # production leaf veto (leaf-argmax based) — drop the row everywhere it applies
    leaf_pred = np.array(classes)[proba.argmax(1)]
    vetoed = np.array(
        [vetoes.is_vetoed(p, n) for p, n in zip(leaf_pred, names)], dtype=bool
    )
    n = len(y)

    rows = []
    for k, label in LEVELS:
        nodes = [_prefix(c, k) for c in classes]
        unodes = sorted(set(nodes))
        nidx = {nd: i for i, nd in enumerate(unodes)}
        agg = np.zeros((len(classes), len(unodes)))
        for i, nd in enumerate(nodes):
            agg[i, nidx[nd]] = 1.0
        node_p = proba @ agg  # row x node summed probability
        pred_node = np.array(unodes)[node_p.argmax(1)]
        conf = node_p.max(1)
        true_node = np.array([_prefix(c, k) for c in y])
        correct = pred_node == true_node

        tau = _global_tau(conf, correct, TARGET_PRECISION)
        accepted = (conf >= tau) & (~vetoed)
        fired = int(accepted.sum())
        tp = int((accepted & correct).sum())
        rows.append(
            {
                "level": f"L{k} {label}",
                "n_nodes": len(unodes),
                "tau": round(float(tau), 4),
                "fired": fired,
                "coverage": round(fired / n, 4) if n else float("nan"),
                "precision": round(tp / fired, 4) if fired else float("nan"),
            }
        )
    df = pd.DataFrame(rows)
    print(f"division {division} — {n} food/bev gold rows, {len(classes)} leaves")
    print(
        f"CV: {OOF_FOLDS}-fold OOF, target precision {TARGET_PRECISION:.0%}, per-level gate\n"
    )
    show = df.copy()
    show["coverage"] = (show["coverage"] * 100).round(1).astype(str) + "%"
    show["precision"] = (show["precision"] * 100).round(1).astype(str) + "%"
    print(show.to_string(index=False))
    return df


if __name__ == "__main__":
    run()
