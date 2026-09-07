"""Gold scoping and the cached cross-validated tables that train and eval share.

Producing the three out-of-fold tables (head, lexical, neighbours) is the entire
cost of both `prices eval` and `prices train-classifier` — about an hour at full
scope — and both need exactly the same ones. They are computed once, cached on
disk, and reused, so a train that follows an eval is nearly free.

The cache key covers the block layout, the block weights, the scope and the exact
row set. Any of those changing MUST miss the cache: reusing a table across a
different vector space or a different gold set answers confidently for a model
that was never run.
"""

from __future__ import annotations

import hashlib
import json

import numpy as np
import pandas as pd

from prices.enrich import config, embedding
from prices.enrich.classifier import gate, lexical, oof
from prices.enrich.classifier.dataset import MIN_SUPPORT, _load_gold

CACHE_DIR = config.ENRICH_DIR / "_eval_cache"


def scope_gold(scope: str = "all", min_support: int = MIN_SUPPORT) -> pd.DataFrame:
    """Rows the head is trained/evaluated on. Filters, in this order:

      1. `verdict == "leaf"` — drop rows the labelers refused to place at a leaf
      2. the requested scope
      3. per-leaf support >= min_support
      4. names the embedding store actually covers

    (4) exists because the GPU embedding run did not cover gold completely
    (~0.3% of names). Those rows are dropped rather than back-filled from the
    older MLX store: mixing two vector spaces inside one matrix is silently
    harmful. Dropping them can push a thin leaf under the support floor, so (3)
    is re-applied afterwards.
    """
    g = _load_gold()
    g = g[g["verdict"] == "leaf"].copy()
    if scope == "food":
        g = g[g["division"] == "01"]
    elif scope == "nonfood":
        g = g[g["division"] != "01"]
    elif scope != "all":
        g = g[g["division"] == scope]
    vc = g["code"].value_counts()
    g = g[g["code"].isin(set(vc[vc >= min_support].index))].reset_index(drop=True)

    covered = embedding.covered_mask(g["product_name"].astype(str).tolist())
    n_drop = int((~covered).sum())
    g = g[covered].reset_index(drop=True)
    vc = g["code"].value_counts()
    thin = set(vc[vc < min_support].index)
    if thin:
        g = g[~g["code"].isin(thin)].reset_index(drop=True)
    g.attrs["dropped_uncovered"] = n_drop
    g.attrs["dropped_leaves"] = sorted(thin)
    return g


def cache_key(g: pd.DataFrame, scope: str,
              sample_weight: np.ndarray | None = None) -> str:
    blocks = [
        (b["tag"], float(b.get("weight", 1.0))) for b in config.CLASSIFIER_EMBED_ENSEMBLE
    ]
    h = hashlib.sha256()
    h.update(json.dumps([scope, blocks], sort_keys=True).encode())
    h.update(pd.util.hash_pandas_object(g["product_name"], index=False).values.tobytes())
    h.update(pd.util.hash_pandas_object(g["code"], index=False).values.tobytes())
    # Weights change the fitted head, so they MUST change the key: reusing an
    # unweighted table for a weighted run would report the wrong model.
    if sample_weight is not None:
        h.update(np.asarray(sample_weight, dtype=np.float64).tobytes())
    return h.hexdigest()[:16]


def oof_tables(g: pd.DataFrame, scope: str, verbose: bool = True,
               keep_x: bool = False, sample_weight: np.ndarray | None = None):
    """`(classes, proba, classes_lex, proba_lex, nbr_idx, nbr_sim, x)`.

    `x` is the embedding matrix; it is returned only when `keep_x` (training needs
    it to fit the final head and to persist the neighbour pool, evaluation does
    not and it is ~1.5 GB). A cache hit with `keep_x` still has to re-read the
    vectors, but not to re-fit anything.

    The three tables checkpoint independently. Head OOF is ~80 minutes at full
    scope and used to be discarded whenever a LATER stage died -- which is how a
    v22 run lost all five folds to an OOM inside the lexical fit. Each stage now
    lands on disk as soon as it finishes, so a crash costs only the stage that
    crashed.
    """
    names = g["product_name"].astype(str).tolist()
    y = g["code"].astype(str).to_numpy()
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    key = cache_key(g, scope, sample_weight)
    path = CACHE_DIR / f"oof_{key}.npz"
    head_path = CACHE_DIR / f"oofhead_{key}.npz"
    lex_path = CACHE_DIR / f"ooflex_{key}.npz"
    spill = CACHE_DIR / f"x_{key}.npy"

    if path.exists():
        if verbose:
            print(f"  reusing cached OOF tables: {path.name}", flush=True)
        with np.load(path, allow_pickle=False) as z:
            out = (z["classes"].astype(str), z["proba"], z["classes_lex"].astype(str),
                   z["proba_lex"], z["nbr_idx"], z["nbr_sim"])
        x = embedding.embed_names(names) if keep_x else None
        return (*out, x)

    if verbose:
        print(f"  embedding {len(names)} names "
              f"({'+'.join(b['tag'] for b in config.CLASSIFIER_EMBED_ENSEMBLE)})",
              flush=True)
    x = embedding.embed_names(names)

    if head_path.exists():
        if verbose:
            print(f"  reusing head OOF checkpoint: {head_path.name}", flush=True)
        with np.load(head_path, allow_pickle=False) as z:
            classes, proba = z["classes"].astype(str), z["proba"]
    else:
        if verbose:
            print(f"  head OOF on {x.shape}", flush=True)
        classes, proba = oof.oof_proba(x, y, verbose=verbose, sample_weight=sample_weight)
        np.savez(head_path, classes=classes, proba=proba)

    # The lexical fold fits are the memory peak of the whole run: a dense
    # n_features x n_classes coefficient matrix, of which L-BFGS keeps roughly
    # twenty copies. The embedding matrix is not read again until the neighbour
    # search, so spill it rather than hold 3.7 GB resident across that peak.
    np.save(spill, x)
    del x

    if lex_path.exists():
        if verbose:
            print(f"  reusing lexical OOF checkpoint: {lex_path.name}", flush=True)
        with np.load(lex_path, allow_pickle=False) as z:
            classes_lex, proba_lex = z["classes_lex"].astype(str), z["proba_lex"]
    else:
        if verbose:
            print("  lexical OOF", flush=True)
        classes_lex, proba_lex = lexical.oof_proba(names, y, verbose=verbose)
        np.savez(lex_path, classes_lex=classes_lex, proba_lex=proba_lex)

    if verbose:
        print("  neighbour search (pool restricted to other folds)", flush=True)
    # Read-only mmap: the search builds its own normalised copy, so the raw
    # matrix only has to be readable, and page cache is reclaimable in a way a
    # second anonymous 3.7 GB array is not.
    nbr_idx, nbr_sim = gate.knn_within_folds(np.load(spill, mmap_mode="r"), y)

    np.savez_compressed(path, classes=classes, proba=proba, classes_lex=classes_lex,
                        proba_lex=proba_lex, nbr_idx=nbr_idx, nbr_sim=nbr_sim)
    if verbose:
        print(f"  cached OOF tables -> {path.name}", flush=True)
    # Materialise only here, with the search's temporaries already released.
    return (classes, proba, classes_lex, proba_lex, nbr_idx, nbr_sim,
            np.load(spill) if keep_x else None)


def gate_inputs(classes, proba, classes_lex, proba_lex, nbr_idx, nbr_sim, y, names):
    """Assemble the gate's feature dict and the post-veto correctness it predicts."""
    leaf_pred = classes[proba.argmax(1)]
    pred, force_rej, force_acc = oof.apply_vetoes(leaf_pred, names)
    correct = pred == y
    feats = gate.static_features(classes, proba, names)
    feats.update(gate.lexical_features(classes_lex, proba_lex, leaf_pred, names))
    feats.update(gate.knn_features(nbr_idx, nbr_sim, y, leaf_pred))
    return feats, leaf_pred, correct, force_rej, force_acc
