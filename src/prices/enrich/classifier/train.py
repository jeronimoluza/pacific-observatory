"""Train the (embedding -> head) COICOP classifier.

The head is a logistic regression over L2-normalized Qwen3-Embedding vectors of
the RAW gold product name. A single GLOBAL confidence gate `tau` is derived at a
target precision from cross-validated out-of-fold predictions on gold (per-leaf
taus miscalibrate out-of-distribution and were rejected). The bundle carries its
own `tau` so prediction never depends on a stale config default.

Operating point config E (global tau + trap vetoes) reproduces ~98% precision at
~82% coverage in 5-fold CV on the food/bev gold. Persists one joblib bundle
{clf, classes, tau, division}.
"""

from __future__ import annotations

import time

import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold

from prices.enrich import config, embedding
from prices.enrich.classifier import MODEL_FILE, version_dir
from prices.enrich.classifier.dataset import load_table

C_INV_REG = 10.0
MAX_ITER = 2000
OOF_FOLDS = 5
OOF_SEED = 42
TARGET_PRECISION = 0.98


def _global_tau(conf: np.ndarray, correct: np.ndarray, target: float) -> float:
    """Highest-recall confidence threshold whose cumulative precision (rows sorted
    by descending confidence) still meets `target`. 1.01 = unreachable."""
    order = np.argsort(-conf)
    cum_prec = np.cumsum(correct[order].astype(float)) / (np.arange(len(order)) + 1)
    ok = np.where(cum_prec >= target)[0]
    return float(conf[order][ok[-1]]) if len(ok) else 1.01


def _derive_tau(x: np.ndarray, y: np.ndarray) -> float:
    skf = StratifiedKFold(OOF_FOLDS, shuffle=True, random_state=OOF_SEED)
    pred = np.empty(len(y), object)
    conf = np.zeros(len(y))
    for tr, te in skf.split(x, y):
        lr = LogisticRegression(max_iter=MAX_ITER, C=C_INV_REG).fit(x[tr], y[tr])
        p = lr.predict_proba(x[te])
        pred[te] = lr.classes_[p.argmax(1)]
        conf[te] = p.max(1)
    return _global_tau(conf, pred == y, TARGET_PRECISION)


def fit(version: str) -> dict:
    df = load_table(version)
    names = df["name"].astype(str).tolist()
    y = df["label"].to_numpy()
    division = (
        str(df["division"].iloc[0]) if len(df) else config.CLASSIFIER_DEFAULT_DIVISION
    )

    t0 = time.time()
    x = embedding.embed_names(names)
    embed_secs = time.time() - t0

    t0 = time.time()
    tau = _derive_tau(x, y)
    clf = LogisticRegression(max_iter=MAX_ITER, C=C_INV_REG).fit(x, y)
    fit_secs = time.time() - t0

    classes = list(clf.classes_)
    bundle = {
        "version": version,
        "clf": clf,
        "classes": classes,
        "tau": tau,
        "division": division,
        "embed_model": config.CLASSIFIER_EMBED_MODEL,
    }
    vdir = version_dir(version)
    vdir.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, vdir / MODEL_FILE)

    return {
        "version": version,
        "division": division,
        "n_train": int(len(names)),
        "n_classes": len(classes),
        "tau": round(tau, 4),
        "n_iter": int(np.max(clf.n_iter_)),
        "converged": bool(np.max(clf.n_iter_) < MAX_ITER),
        "embed_secs": round(embed_secs, 1),
        "fit_secs": round(fit_secs, 1),
    }
