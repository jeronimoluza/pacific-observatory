"""Train the (embedding -> head -> meta-gate) COICOP classifier.

Three models are fitted and travel together, because the operating point is a
property of all three at once:

  head     logistic regression over the weighted, L2-normalized ensemble
           embedding of the RAW gold product name
  lexical  char-ngram TF-IDF head, present only to feed three features to the gate
  gate     a monotone-constrained booster predicting "will the head's top-1 be
           correct?", whose score -- not the head's own confidence -- is what the
           acceptance threshold is set on

`tau` is derived from CROSS-VALIDATED out-of-fold scores: no row contributes a
threshold that a model trained on it produced. The bundle carries its own tau so
prediction never depends on a stale config default.

Inference also needs a neighbour pool, since six of the gate's features describe
a row's nearest GOLD neighbours. The gold embedding matrix is therefore persisted
alongside the bundle (float16, ~0.8 GB). Note the asymmetry, which is deliberate:
training searches neighbours with the row's own fold held out, so a near-duplicate
cannot leak its label; at inference the row is unseen and the whole pool is used.
"""

from __future__ import annotations

import time

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

from prices.enrich import config
from prices.enrich.classifier import (
    MODEL_FILE,
    OOF_FILE,
    POOL_FILE,
    gate,
    lexical,
    oof,
    tables,
    version_dir,
)

C_INV_REG = oof.C_INV_REG
MAX_ITER = oof.MAX_ITER
OOF_FOLDS = oof.OOF_FOLDS
OOF_SEED = oof.OOF_SEED
TARGET_PRECISION = oof.TARGET_PRECISION


def fit(version: str, scope: str | None = None, verbose: bool = True,
        g: pd.DataFrame | None = None,
        sample_weight: np.ndarray | None = None) -> dict:
    """Fit head + lexical + gate and derive tau from cross-validated OOF scores.

    `g` overrides the row set `scope` would select. It exists so a run can
    reproduce an EARLIER model on that model's exact rows: comparing a new number
    against an old one is only meaningful on one row set, and re-deriving the set
    from today's gold silently changes it. `scope` remains the cache label and the
    bundle's recorded scope, so pass a distinct string whenever the rows are not
    what that scope would ordinarily yield.

    `sample_weight` reweights the head's training rows only -- not the gate, and
    not the evaluation. See `oof.oof_proba`.
    """
    scope = scope or config.CLASSIFIER_DEFAULT_SCOPE
    if g is None:
        g = tables.scope_gold(scope)
    names = g["product_name"].astype(str).tolist()
    y = g["code"].astype(str).to_numpy()
    if verbose:
        print(f"training {version} scope={scope}: {len(y)} rows / "
              f"{g['code'].nunique()} leaves", flush=True)

    t0 = time.time()
    cls, proba, cls_lex, proba_lex, nbr_idx, nbr_sim, x = tables.oof_tables(
        g, scope, verbose=verbose, keep_x=True, sample_weight=sample_weight
    )
    oof_secs = time.time() - t0

    feats, leaf_pred, correct, force_rej, force_acc = tables.gate_inputs(
        cls, proba, cls_lex, proba_lex, nbr_idx, nbr_sim, y, names
    )

    t0 = time.time()
    if verbose:
        print("  cross-fitting the gate to set tau", flush=True)
    gate_score = gate.cross_fit(feats, leaf_pred, correct)
    tau_gate = oof.choose_tau(gate_score, correct, TARGET_PRECISION)
    tau_raw = oof.choose_tau(proba.max(1), correct, TARGET_PRECISION)
    oof_summary = oof.summarize(gate_score, correct, force_rej, force_acc, tau_gate)

    if verbose:
        print("  fitting final head / lexical / gate on all rows", flush=True)
    clf = LogisticRegression(max_iter=MAX_ITER, C=C_INV_REG).fit(
        x, y, sample_weight=sample_weight
    )
    lex_bundle = lexical.fit(names, y)
    gate_bundle = gate.fit(feats, leaf_pred, correct)
    fit_secs = time.time() - t0

    vdir = version_dir(version)
    vdir.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            "version": version,
            "scope": scope,
            "clf": clf,
            "classes": list(clf.classes_),
            "lexical": lex_bundle,
            "gate": gate_bundle,
            "tau": tau_gate,
            "tau_raw": tau_raw,
            "target_precision": TARGET_PRECISION,
            "blocks": [
                {"tag": b["tag"], "dim": b.get("dim"), "weight": b.get("weight", 1.0)}
                for b in config.CLASSIFIER_EMBED_ENSEMBLE
            ],
        },
        vdir / MODEL_FILE,
    )
    # Neighbour pool for inference. float16 halves it at ~5e-4 relative error on
    # unit vectors, which is far below the similarity differences the gate reads.
    np.savez(vdir / POOL_FILE, mat=x.astype(np.float16), labels=np.array(y, dtype=str))

    pd.DataFrame(
        {
            "name": names,
            "label": y,
            "oof_pred": np.array(leaf_pred, dtype=str),
            "oof_conf": proba.max(1),
            "oof_gate": gate_score,
            "oof_accepted": oof_summary["accepted"],
        }
    ).to_parquet(vdir / OOF_FILE, index=False)

    return {
        "version": version,
        "scope": scope,
        "n_train": int(len(names)),
        "weighted": sample_weight is not None,
        "n_classes": int(len(clf.classes_)),
        "head_accuracy": round(float(correct.mean()), 4),
        "tau": round(float(tau_gate), 4),
        "tau_raw": round(float(tau_raw), 4),
        "precision": oof_summary["precision"],
        "coverage": oof_summary["coverage"],
        "n_iter": int(np.max(clf.n_iter_)),
        "converged": bool(np.max(clf.n_iter_) < MAX_ITER),
        "oof_secs": round(oof_secs, 1),
        "fit_secs": round(fit_secs, 1),
    }


def _global_tau(conf: np.ndarray, correct: np.ndarray, target: float) -> float:
    """Highest-recall threshold whose cumulative precision still meets `target`.

    Kept as the name the gold-audit tests reach for. It forwards to
    `oof.choose_tau`, which is the definition -- the acceptance threshold has to
    be the same function everywhere or `prices eval` reports an operating point
    that `prices process` does not run at.
    """
    return oof.choose_tau(conf, correct, target)


def cross_val_oof(x: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Out-of-fold `(pred, conf)` over the tau-setting fold split.

    Exposed so the gold audit scores labels against the *same* folds that set
    `tau`; a second StratifiedKFold elsewhere would drift from the frontier the
    audit reports against. It delegates to `oof.oof_proba` rather than running
    its own fold loop, so there is exactly one copy of the split to keep in
    sync -- the duplicate that used to live here drifted from it silently.
    """
    classes, proba = oof.oof_proba(x, y)
    return classes[proba.argmax(1)], proba.max(1)
