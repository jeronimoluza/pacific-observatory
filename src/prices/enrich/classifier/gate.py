"""Meta-gate: a second model that decides whether to ACCEPT the head's top-1.

The head's own softmax confidence is a poor accept/reject signal. Coverage at a
precision floor is bound by how well confidence RANK-ORDERS correct answers, not
by accuracy, so a model trained to predict "will top-1 be correct?" and gated on
ITS score buys coverage the raw threshold cannot. Measured all-scope, leaf-exact
at the 98% floor: raw gate 0.6997 -> this gate 0.7497.

Two consequences worth stating, because both have burned experiments here:

  - Any confidence transform that merely REORDERS the head's existing
    probabilities (temperature, per-prefix recalibration, class priors) is
    subsumed by this gate and shows no lift once it runs. Only features carrying
    information the head never had survive -- which is why the neighbour block
    below, and not a recalibration, is the largest single lever (+3.2pt).
  - A new confidence idea must be measured THROUGH the gate. Measured against
    the raw gate instead it reads 3x-25x too optimistic.

`leaf_support` and `leaf_target_enc` are the only fold-dependent features: both
are statistics OF the predicted leaf's correctness, so computing them over all
rows would leak the answer. They are recomputed inside each fold from the
training side only, and at inference come from the tables the trainer persisted.
"""

from __future__ import annotations

import re

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.model_selection import StratifiedKFold

N_FOLDS = 5
SEED = 42
K_NEIGHBOURS = 25
MAX_ITER = 200
# Batching only -- results are identical at any value. 2048 held a
# chunk x pool similarity block of ~790 MB at full scope, and argpartition
# doubles that; 512 keeps the search inside the memory the box actually has.
_KNN_CHUNK = 512

NON_LATIN_RANGES = [
    (0x4E00, 0x9FFF),  # CJK unified
    (0x3040, 0x30FF),  # hiragana/katakana
    (0xAC00, 0xD7A3),  # hangul
    (0x0400, 0x04FF),  # cyrillic
    (0x0E00, 0x0E7F),  # thai
    (0x0600, 0x06FF),  # arabic
]

CONFIDENCE_COLS = ["top1", "top2", "margin", "ratio", "entropy_full", "entropy_top10"]
PARENT_COLS = [
    "parent_mass_of_pred",
    "grandparent_mass_of_pred",
    "parent_margin",
    "agreement_flag",
]
TAXONOMY_COLS = ["leaf_support", "n_siblings"]
NAME_COLS = [
    "name_char_len",
    "name_token_count",
    "name_has_digit",
    "name_non_latin",
    "name_frac_nonascii",
]
TARGET_ENC_COLS = ["leaf_target_enc"]
LEXICAL_COLS = ["lex_top1", "lex_margin", "lex_agree"]
KNN_COLS = [
    "knn_agree",
    "knn_top1_sim",
    "knn_same_ratio",
    "knn_entropy",
    "knn_pred_present",
    "knn_margin_sim",
]

# The shipped featureset ("base+knn"). The wider "full" set adds country one-hots,
# script fractions and cross-family agreement for +0.31pt, but the cross-family
# block needs a SECOND embedding head (a depth-3 prefix model) at inference; that
# is not worth 0.31pt. Dropping the lexical block instead would cost 0.34pt and
# saves only a char-ngram TF-IDF, which is cheap, so the lexical block stays.
GATE_COLS = (
    CONFIDENCE_COLS
    + PARENT_COLS
    + TAXONOMY_COLS
    + NAME_COLS
    + TARGET_ENC_COLS
    + LEXICAL_COLS
    + KNN_COLS
)

# feature -> monotone direction. Only relationships we are willing to assert a
# priori; an unconstrained booster has to rediscover them from noisy tail data
# and does measurably worse for it.
MONOTONE = {
    "top1": 1,
    "margin": 1,
    "ratio": 1,
    "leaf_target_enc": 1,
    "entropy_full": -1,
    "entropy_top10": -1,
}

FOLD_DEPENDENT = {"leaf_support", "leaf_target_enc"}


def parent_of(code: str) -> str:
    """Strip one dotted level. COICOP depth is NOT uniform -- division 01 leaves
    are depth-5 and most of 02..15 are depth-4 -- so a parent is never "the first
    N levels"."""
    return ".".join(str(code).split(".")[:-1])


def _mass_by(classes: np.ndarray, proba: np.ndarray, keyfunc):
    keys = np.array([keyfunc(c) for c in classes])
    uniq = np.array(sorted(set(keys)))
    col = {u: j for j, u in enumerate(uniq)}
    m = np.zeros((proba.shape[0], len(uniq)))
    for j, k in enumerate(keys):
        m[:, col[k]] += proba[:, j]
    return uniq, m


def name_features(names) -> dict[str, np.ndarray]:
    n = len(names)
    out = {k: np.zeros(n) for k in NAME_COLS}
    digit_rx = re.compile(r"\d")
    for i, s in enumerate(names):
        s = str(s)
        out["name_char_len"][i] = len(s)
        out["name_token_count"][i] = len(s.split())
        out["name_has_digit"][i] = 1.0 if digit_rx.search(s) else 0.0
        out["name_frac_nonascii"][i] = sum(1 for ch in s if ord(ch) > 127) / max(len(s), 1)
        for ch in s:
            o = ord(ch)
            if any(lo <= o <= hi for lo, hi in NON_LATIN_RANGES):
                out["name_non_latin"][i] = 1.0
                break
    return out


def static_features(classes: np.ndarray, proba: np.ndarray, names) -> dict:
    """Everything that is a deterministic function of one row's own (proba, name)
    plus static taxonomy structure -- no cross-row information, so no fold loop."""
    n = proba.shape[0]
    eps = 1e-12
    leaf_pred = classes[proba.argmax(1)]

    sorted_p = np.sort(proba, axis=1)
    top1, top2 = sorted_p[:, -1], sorted_p[:, -2]
    p_safe = np.clip(proba, eps, 1.0)
    top10 = sorted_p[:, -10:]
    top10_norm = np.clip(top10 / np.clip(top10.sum(1, keepdims=True), eps, None), eps, 1.0)

    puniq, pmass = _mass_by(classes, proba, parent_of)
    guniq, gmass = _mass_by(classes, proba, lambda c: parent_of(parent_of(c)))
    p_idx = {u: j for j, u in enumerate(puniq)}
    g_idx = {u: j for j, u in enumerate(guniq)}
    pred_parent = np.array([parent_of(c) for c in leaf_pred])
    pred_grand = np.array([parent_of(parent_of(c)) for c in leaf_pred])
    p_sorted = np.sort(pmass, axis=1)

    parent_of_class = np.array([parent_of(c) for c in classes])
    sibs = {p: int((parent_of_class == p).sum()) for p in set(parent_of_class)}

    feats = {
        "top1": top1,
        "top2": top2,
        "margin": top1 - top2,
        "ratio": np.clip(top1 / (top2 + eps), 0, 1e6),
        "entropy_full": -(p_safe * np.log(p_safe)).sum(1),
        "entropy_top10": -(top10_norm * np.log(top10_norm)).sum(1),
        "parent_mass_of_pred": pmass[np.arange(n), [p_idx[p] for p in pred_parent]],
        "grandparent_mass_of_pred": gmass[np.arange(n), [g_idx[p] for p in pred_grand]],
        "parent_margin": p_sorted[:, -1] - p_sorted[:, -2],
        "agreement_flag": (pred_parent == puniq[pmass.argmax(1)]).astype(float),
        "n_siblings": np.array([sibs[p] - 1 for p in pred_parent], dtype=float),
    }
    feats.update(name_features(names))
    return feats


def lexical_features(classes_lex, proba_lex, leaf_pred, names) -> dict:
    """The lexical head's three summary features. `lex_agree` compares the
    POST-veto lexical prediction, so a trap veto that rewrites one head's answer
    cannot register as a disagreement with the other."""
    from prices.enrich.classifier.oof import apply_vetoes

    sl = np.sort(proba_lex, axis=1)
    lex_pred, _, _ = apply_vetoes(classes_lex[proba_lex.argmax(1)], names)
    return {
        "lex_top1": proba_lex.max(1),
        "lex_margin": sl[:, -1] - sl[:, -2],
        "lex_agree": (lex_pred == leaf_pred).astype(float),
    }


def knn_features(nbr_idx, nbr_sim, pool_labels, leaf_pred) -> dict:
    """Neighbour-agreement block. `pool_labels[nbr_idx]` are the gold labels of
    each row's nearest gold neighbours; agreement with the head's prediction runs
    ~0.80 on correct rows against ~0.36 on wrong ones, which is information the
    head's own probabilities do not contain."""
    n, k = nbr_idx.shape
    nbr_lab = pool_labels[nbr_idx]
    same = nbr_lab == leaf_pred[:, None]
    big = np.float32(-1e9)
    s_same = np.where(same, nbr_sim, big).max(1)
    s_diff = np.where(~same, nbr_sim, big).max(1)
    s_same = np.where(s_same == big, 0.0, s_same)
    s_diff = np.where(s_diff == big, 1e-6, s_diff)
    ent = np.zeros(n)
    for i in range(n):
        _, c = np.unique(nbr_lab[i], return_counts=True)
        p = c / k
        ent[i] = -(p * np.log(p + 1e-12)).sum()
    return {
        "knn_agree": same.mean(1).astype(float),
        "knn_top1_sim": nbr_sim[:, 0].astype(float),
        "knn_same_ratio": (s_same / np.maximum(s_diff, 1e-6)).astype(float),
        "knn_entropy": ent,
        "knn_pred_present": same.any(1).astype(float),
        "knn_margin_sim": (nbr_sim[:, 0] - nbr_sim[:, -1]).astype(float),
    }


def _topk(query: np.ndarray, pool: np.ndarray, k: int):
    sims = query @ pool.T
    top = np.argpartition(-sims, k, axis=1)[:, :k]
    rows = np.arange(len(query))[:, None]
    order = np.argsort(-sims[rows, top], axis=1)
    top = top[rows, order]
    return top, sims[rows, top]


def knn_within_folds(x: np.ndarray, y: np.ndarray, k: int = K_NEIGHBOURS):
    """Neighbours for gold rows, with the pool restricted to the OTHER head folds.

    Searching all of gold would let a row find a near-duplicate of itself that the
    head also trained on, so `knn_agree` would report the answer rather than
    predict it. The folds here must be the HEAD's folds for that to hold.
    """
    n = len(y)
    idx = np.zeros((n, k), np.int64)
    sim = np.zeros((n, k), np.float32)
    xn = x / (np.linalg.norm(x, axis=1, keepdims=True) + 1e-9)
    skf = StratifiedKFold(N_FOLDS, shuffle=True, random_state=SEED)
    for tr, te in skf.split(x, y):
        pool = xn[tr]
        for s in range(0, len(te), _KNN_CHUNK):
            q = te[s : s + _KNN_CHUNK]
            top, sims = _topk(xn[q], pool, k)
            idx[q] = tr[top]
            sim[q] = sims
    return idx, sim


def knn_query(x: np.ndarray, pool: np.ndarray, k: int = K_NEIGHBOURS):
    """Neighbours for NEW rows against the whole gold pool (no fold restriction --
    an unseen row cannot find itself)."""
    xn = x / (np.linalg.norm(x, axis=1, keepdims=True) + 1e-9)
    pn = pool / (np.linalg.norm(pool, axis=1, keepdims=True) + 1e-9)
    idx = np.zeros((len(xn), k), np.int64)
    sim = np.zeros((len(xn), k), np.float32)
    for s in range(0, len(xn), _KNN_CHUNK):
        top, sims = _topk(xn[s : s + _KNN_CHUNK], pn, k)
        idx[s : s + _KNN_CHUNK] = top
        sim[s : s + _KNN_CHUNK] = sims
    return idx, sim


def _make(cols) -> HistGradientBoostingClassifier:
    mono = np.array([MONOTONE.get(c, 0) for c in cols])
    return HistGradientBoostingClassifier(
        random_state=SEED, max_iter=MAX_ITER, monotonic_cst=mono
    )


def leaf_stats(leaf_pred, correct) -> tuple[dict, dict, float]:
    """Per-predicted-leaf support count and correctness rate, plus the global rate
    used for leaves never predicted on the training side."""
    support: dict[str, int] = {}
    hits: dict[str, float] = {}
    for lp, c in zip(leaf_pred, correct):
        support[lp] = support.get(lp, 0) + 1
        hits[lp] = hits.get(lp, 0.0) + float(c)
    enc = {lp: hits[lp] / support[lp] for lp in support}
    return support, enc, float(np.mean(correct))


def _matrix(feats, cols, rows, leaf_pred, support, enc, gmean) -> np.ndarray:
    x = np.zeros((len(rows), len(cols)))
    lp = leaf_pred[rows]
    for j, c in enumerate(cols):
        if c == "leaf_support":
            x[:, j] = [support.get(p, 0) for p in lp]
        elif c == "leaf_target_enc":
            x[:, j] = [enc.get(p, gmean) for p in lp]
        else:
            x[:, j] = feats[c][rows]
    return x


def cross_fit(feats, leaf_pred, correct, cols=GATE_COLS) -> np.ndarray:
    """Out-of-fold gate score for every gold row -- the array `tau_gate` is set on."""
    n = len(correct)
    correct = np.asarray(correct).astype(int)
    leaf_pred = np.asarray(leaf_pred)
    score = np.zeros(n)
    skf = StratifiedKFold(N_FOLDS, shuffle=True, random_state=SEED)
    for tr, te in skf.split(np.zeros(n), correct):
        support, enc, gmean = ({}, {}, float(correct[tr].mean()))
        if FOLD_DEPENDENT & set(cols):
            support, enc, gmean = leaf_stats(leaf_pred[tr], correct[tr])
        xtr = _matrix(feats, cols, tr, leaf_pred, support, enc, gmean)
        xte = _matrix(feats, cols, te, leaf_pred, support, enc, gmean)
        m = _make(cols).fit(xtr, correct[tr])
        score[te] = m.predict_proba(xte)[:, 1]
    return score


def fit(feats, leaf_pred, correct, cols=GATE_COLS) -> dict:
    """Final gate, fitted on ALL gold. Returned with the leaf tables it needs at
    inference, since those cannot be recomputed without labels."""
    correct = np.asarray(correct).astype(int)
    leaf_pred = np.asarray(leaf_pred)
    support, enc, gmean = leaf_stats(leaf_pred, correct)
    rows = np.arange(len(correct))
    m = _make(cols).fit(
        _matrix(feats, cols, rows, leaf_pred, support, enc, gmean), correct
    )
    return {
        "model": m,
        "cols": list(cols),
        "leaf_support": support,
        "leaf_target_enc": enc,
        "global_rate": gmean,
    }


def score(bundle: dict, feats, leaf_pred) -> np.ndarray:
    leaf_pred = np.asarray(leaf_pred)
    rows = np.arange(len(leaf_pred))
    x = _matrix(
        feats,
        bundle["cols"],
        rows,
        leaf_pred,
        bundle["leaf_support"],
        bundle["leaf_target_enc"],
        bundle["global_rate"],
    )
    return bundle["model"].predict_proba(x)[:, 1]
