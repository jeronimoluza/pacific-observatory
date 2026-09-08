"""Cross-validated scoring primitives shared by train and eval.

Both paths must agree bit-for-bit on how rows are folded, how the trap vetoes are
applied and how the acceptance threshold is chosen -- otherwise the number `prices
eval` reports is not the operating point `prices process` runs at. They live here
rather than in either caller so there is one copy to change.

Order matters and is easy to get wrong: the vetoes are applied BEFORE correctness
is computed, and the threshold is then set against post-veto correctness. Setting
it against the raw argmax instead moves the reported coverage, because a veto can
turn a wrong high-confidence row into a right one (or reject it outright).
"""

from __future__ import annotations

import numpy as np
from sklearn.model_selection import StratifiedKFold

from prices.enrich import vetoes
from prices.enrich.classifier import minibatch

C_INV_REG = 10.0
MAX_ITER = 2000
# Epochs for the mini-batch head. See `minibatch` for why LBFGS is gone.
HEAD_EPOCHS = 120
OOF_FOLDS = 5
OOF_SEED = 42
TARGET_PRECISION = 0.98


def oof_proba(x: np.ndarray, y: np.ndarray, verbose: bool = False,
              sample_weight: np.ndarray | None = None,
              checkpoint: str | None = None):
    """Out-of-fold class list and the full (N, n_classes) probability table.

    The table is kept whole rather than collapsed to argmax because the gate needs
    the runner-up mass, the entropies and the parent marginal.

    `sample_weight` reweights the TRAINING side of each fold only. Evaluation
    stays unweighted on purpose: coverage@98 is a statement about the natural row
    population, so reweighting the denominator would answer a different question
    than the one the metric is asked.
    """
    import time

    import os as _os
    from pathlib import Path as _Path

    skf = StratifiedKFold(OOF_FOLDS, shuffle=True, random_state=OOF_SEED)
    classes = np.array(sorted(set(y)))
    idx = {c: i for i, c in enumerate(classes)}
    proba = np.zeros((len(y), len(classes)))
    done = np.zeros(OOF_FOLDS, bool)

    # Resume. The split is a pure function of (OOF_FOLDS, OOF_SEED, y), so a
    # fold an earlier process finished is the same fold now. A run that dies in
    # fold 4 used to cost all five.
    if checkpoint and _Path(checkpoint).exists():
        with np.load(checkpoint, allow_pickle=False) as z:
            if list(z["classes"].astype(str)) == list(classes.astype(str)):
                proba, done = z["proba"], z["done"]
                if verbose and done.any():
                    print(f"    resuming: folds {list(np.where(done)[0] + 1)} already done",
                          flush=True)

    for k, (tr, te) in enumerate(skf.split(x, y), 1):
        if done[k - 1]:
            continue
        t0 = time.time()
        # Seeded per fold so the folds are independent draws but the run as a
        # whole still reproduces exactly.
        head = minibatch.fit_head(
            x, y, tr, seed=OOF_SEED + k, epochs=HEAD_EPOCHS,
            sample_weight=sample_weight, c_inv_reg=C_INV_REG, verbose=verbose,
        )
        p = minibatch.predict_proba_indexed(x, te, head.w, head.b)
        for j, c in enumerate(head.classes_):
            proba[te, idx[c]] = p[:, j]
        done[k - 1] = True
        if checkpoint:
            # Atomic: a crash mid-write must not leave a torn file the next run
            # trusts.
            tmp = str(checkpoint) + ".tmp.npz"
            np.savez(tmp, classes=classes, proba=proba, done=done)
            _os.replace(tmp, checkpoint)
        if verbose:
            print(f"    fold {k}/{OOF_FOLDS} {time.time() - t0:.0f}s", flush=True)
    return classes, proba


def apply_vetoes(pred, names):
    """Per-leaf trap vetoes. Returns (possibly-rewritten pred, forced-reject mask,
    forced-accept mask)."""
    pred = np.array(pred, dtype=object)
    force_rej = np.zeros(len(pred), bool)
    force_acc = np.zeros(len(pred), bool)
    for i, (p, n) in enumerate(zip(pred, names)):
        a = vetoes.veto_action(p, n)
        if a is None:
            continue
        if a == vetoes.REJECT:
            force_rej[i] = True
        else:
            pred[i] = a
            force_acc[i] = True
    return pred, force_rej, force_acc


def choose_tau(score: np.ndarray, correct: np.ndarray, target: float) -> float:
    """Highest-recall threshold whose cumulative precision, over rows sorted by
    descending score, still meets `target`. 1.01 means unreachable.

    Rows tied at the boundary are admitted as a block, so a large tie could in
    principle land the accepted set under `target`. Callers assert the realized
    precision rather than trusting this; with ~50k near-distinct scores the tied
    blocks here are one or two rows wide.
    """
    order = np.argsort(-score)
    cum = np.cumsum(correct[order].astype(float)) / (np.arange(len(order)) + 1)
    ok = np.where(cum >= target)[0]
    return float(score[order][ok[-1]]) if len(ok) else 1.01


def summarize(score, correct, force_rej, force_acc, tau) -> dict:
    accepted = ((score >= tau) & ~force_rej) | force_acc
    tp = int((accepted & correct).sum())
    fired = int(accepted.sum())
    n = len(correct)
    return {
        "tau": round(float(tau), 4),
        "fired": fired,
        "precision": round(tp / fired, 4) if fired else float("nan"),
        "coverage": round(tp / n, 4) if n else float("nan"),
        "accepted": accepted,
    }
