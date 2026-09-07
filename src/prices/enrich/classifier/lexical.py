"""Char-ngram lexical head — an auxiliary signal for the meta-gate, not a classifier.

This model is never asked for an answer. Its three summary features (top-1 mass,
runner-up margin, and whether it agrees with the embedding head) are worth +0.34pt
of coverage@98 to the gate, which is what justifies carrying it. On its own it is
far weaker than the embedding head.

It is character-level rather than word-level on purpose: a word analyzer produces
ZERO features for a large share of this corpus, which is ~21% CJK/Thai/Cyrillic
and often unsegmented.

`min_df` is an absolute document count, so it has to be rescaled whenever the
gold set grows or the whole point of it is lost. At 49,605 rows min_df=5 yielded
~77k features; at 120,579 rows the same 5 yields 152,650, whose dense
n_features x n_classes coefficients are ~7.8 GB inside L-BFGS and killed a v22
run outright. 12 is 5 carried over at the same relative frequency (5 x 2.43) and
lands back at 70,525 features. Hyperparameters do not survive a scope change,
and a 2.4x larger gold set is a scope change.

The 2026-09-07 gold set is 278,490 rows, so the same relative frequency puts it
at 28 (12 x 2.31, equivalently 5 x 5.61). The default tracks the current gold;
`PRICES_LEXICAL_MIN_DF` overrides it, which is how a run reproducing an older
model pins that model's value (v22 = 12) instead of silently re-tuning it.
"""

from __future__ import annotations

import os

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold

from prices.enrich.classifier.oof import C_INV_REG, MAX_ITER, OOF_FOLDS, OOF_SEED

NGRAM = (3, 5)
MIN_DF = int(os.environ.get("PRICES_LEXICAL_MIN_DF", "28"))
ANALYZER = "char_wb"


def _vectorizer() -> TfidfVectorizer:
    return TfidfVectorizer(analyzer=ANALYZER, ngram_range=NGRAM, min_df=MIN_DF)


def oof_proba(names, y: np.ndarray, verbose: bool = False):
    """OOF lexical probability table on the SAME folds as the embedding head.

    StratifiedKFold's split depends only on y's order and values, not on the
    feature matrix, so this table lines up row-for-row with the embedding's --
    which is what lets the gate read both for a single row. The vectorizer is
    re-fitted per fold on the training side only.
    """
    import time

    names = np.array([str(n) for n in names], dtype=object)
    classes = np.array(sorted(set(y)))
    idx = {c: i for i, c in enumerate(classes)}
    proba = np.zeros((len(y), len(classes)))
    skf = StratifiedKFold(OOF_FOLDS, shuffle=True, random_state=OOF_SEED)
    for k, (tr, te) in enumerate(skf.split(names, y), 1):
        t0 = time.time()
        vec = _vectorizer()
        xtr = vec.fit_transform(names[tr])
        lr = LogisticRegression(max_iter=MAX_ITER, C=C_INV_REG).fit(xtr, y[tr])
        p = lr.predict_proba(vec.transform(names[te]))
        for j, c in enumerate(lr.classes_):
            proba[te, idx[c]] = p[:, j]
        if verbose:
            print(f"    lex fold {k}/{OOF_FOLDS} {time.time() - t0:.0f}s", flush=True)
    return classes, proba


def fit(names, y: np.ndarray) -> dict:
    names = [str(n) for n in names]
    vec = _vectorizer()
    x = vec.fit_transform(names)
    lr = LogisticRegression(max_iter=MAX_ITER, C=C_INV_REG).fit(x, y)
    return {"vectorizer": vec, "model": lr, "classes": lr.classes_}


def predict_proba(bundle: dict, names):
    x = bundle["vectorizer"].transform([str(n) for n in names])
    return np.asarray(bundle["classes"]), bundle["model"].predict_proba(x)
