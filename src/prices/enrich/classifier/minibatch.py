"""Mini-batch multinomial softmax, the solver the LBFGS head cannot replace.

`LogisticRegression(solver="lbfgs")` hard-codes float64 (`_logistic.py:1242`), so
a fold slice of the 7,680-dim embedding is materialised at 8 bytes/cell before
the optimiser starts: 13.2 GB at full gold scale. Measured on 2026-09-08, the
slice is never returned to the OS either -- `del xtr` released exactly 0.00 GB --
so anonymous memory grew ~7.4 GB per fold and fold 3 was OOM-killed at 26.6 GB.

This trainer never materialises a fold. It indexes the memmap one batch at a
time, so the resident training set is `batch_size x d x 4` bytes -- 126 MB at
4096 x 7680 -- and that figure is flat in the number of rows and in the number of
folds.

The upstream package documents 5 epochs, batch 4096, lr 0.01 with plain SGD
(`docs/REPRODUCTION.md:44`). Measured against an LBFGS reference on 48k of our
rows, that configuration scores 0.1375 against LBFGS's 0.8570 -- it predicts a
single class and the argmax does not move between epoch 5 and epoch 15. The
cause is feature scale, not the solver: our base is four L2-normalised blocks
concatenated, so a cell is ~0.023, and plain SGD at lr 0.01 moves a weight by
~1e-5 per step while separating logits needs weights near 0.5. That is ~50,000
steps; 5 epochs is 60. Upstream features are scaled differently, so the constant
does not port.

Hence Adam by default. Its step size is set by the ratio of the gradient to its
own RMS, so it is invariant to that scale factor and reaches the same optimum in
a step budget that fits. Plain SGD is kept for reproducing the upstream number
exactly, not for use.

L2 follows sklearn's parameterisation so `C` means here what it means there:
sklearn minimises `C * sum(loss) + 0.5 * ||w||^2`, which against a mean-loss
gradient is a weight decay of `1 / (C * n_train)`. The bias is not penalised,
matching sklearn.
"""

from __future__ import annotations

import time

import numpy as np

# Calibrated 2026-09-08 against an LBFGS reference on 48k rows / 308 classes:
# LBFGS 0.8570, adam@1e-3 0.8655, adam@3e-3 0.8638, adam@1e-2 0.8610. Every
# Adam setting beat the reference; accuracy fell monotonically as lr rose
# while training loss fell, which is the overfitting direction, so the
# smallest rate tested is the operating point.
EPOCHS = 120
BATCH_SIZE = 4096
LEARNING_RATE = 1e-3
OPTIMIZER = "adam"
ADAM_BETA1 = 0.9
ADAM_BETA2 = 0.999
ADAM_EPS = 1e-8


def _softmax_rows(z: np.ndarray) -> np.ndarray:
    """Row-wise softmax, max-subtracted so `exp` cannot overflow."""
    z = z - z.max(axis=1, keepdims=True)
    np.exp(z, out=z)
    z /= z.sum(axis=1, keepdims=True)
    return z


def fit_minibatch_softmax_indexed(
    x,
    y_idx: np.ndarray,
    rows: np.ndarray,
    n_classes: int,
    seed: int,
    epochs: int = EPOCHS,
    batch_size: int = BATCH_SIZE,
    lr: float = LEARNING_RATE,
    sample_weight: np.ndarray | None = None,
    c_inv_reg: float = 10.0,
    optimizer: str = OPTIMIZER,
    verbose: bool = False,
):
    """Fit softmax weights over `x[rows]` without ever materialising `x[rows]`.

    `y_idx` is already class-index encoded and aligned to `x`, not to `rows`;
    `rows` selects the training subset. `sample_weight` is likewise indexed by
    the full array. Determinism comes from `seed`: the per-epoch permutation is
    drawn from a fresh `default_rng(seed + epoch)`, so a rerun reproduces the
    weights bit-for-bit.
    """
    d = x.shape[1]
    n = len(rows)
    w = np.zeros((d, n_classes), np.float32)
    b = np.zeros(n_classes, np.float32)
    decay = np.float32(1.0 / (c_inv_reg * n))
    losses = []
    t0 = time.time()

    if optimizer == "adam":
        mw = np.zeros_like(w)
        vw = np.zeros_like(w)
        mb = np.zeros_like(b)
        vb = np.zeros_like(b)
        step = 0
    elif optimizer != "sgd":
        raise ValueError(f"unknown optimizer {optimizer!r}")

    for epoch in range(epochs):
        rng = np.random.default_rng(seed + epoch)
        order = rows[rng.permutation(n)]
        epoch_loss = 0.0
        seen = 0
        for s in range(0, n, batch_size):
            take = order[s : s + batch_size]
            xb = np.asarray(x[take], np.float32)
            yb = y_idx[take]
            m = len(take)

            p = _softmax_rows(xb @ w + b)
            # Cross-entropy on the true class only; clipped because a saturated
            # softmax underflows to 0 and log(0) would poison the diagnostic.
            row_loss = -np.log(np.maximum(p[np.arange(m), yb], 1e-12))

            g = p
            g[np.arange(m), yb] -= 1.0
            if sample_weight is not None:
                sw = sample_weight[take].astype(np.float32)
                g *= sw[:, None]
                row_loss = row_loss * sw
                denom = np.float32(max(sw.sum(), 1e-12))
            else:
                denom = np.float32(m)
            g /= denom

            gw = xb.T @ g + decay * w
            gb = g.sum(axis=0)

            if optimizer == "sgd":
                w -= lr * gw
                b -= lr * gb
            else:
                # Bias correction is applied to the step rather than to the
                # moments, so the moment buffers stay float32 and in place.
                step += 1
                mw *= ADAM_BETA1
                mw += (1.0 - ADAM_BETA1) * gw
                vw *= ADAM_BETA2
                vw += (1.0 - ADAM_BETA2) * (gw * gw)
                mb *= ADAM_BETA1
                mb += (1.0 - ADAM_BETA1) * gb
                vb *= ADAM_BETA2
                vb += (1.0 - ADAM_BETA2) * (gb * gb)
                bc = np.float32(
                    lr * np.sqrt(1.0 - ADAM_BETA2 ** step) / (1.0 - ADAM_BETA1 ** step)
                )
                w -= bc * mw / (np.sqrt(vw) + ADAM_EPS)
                b -= bc * mb / (np.sqrt(vb) + ADAM_EPS)

            epoch_loss += float(row_loss.sum())
            seen += m
        losses.append(epoch_loss / max(seen, 1))
        if verbose:
            print("      epoch %d/%d  loss %.4f  %.0fs"
                  % (epoch + 1, epochs, losses[-1], time.time() - t0), flush=True)

    diag = {
        "optimizer": optimizer,
        "epochs": epochs,
        "batch_size": batch_size,
        "lr": lr,
        "seed": seed,
        "n_train": int(n),
        "n_classes": int(n_classes),
        "loss_per_epoch": losses,
        "seconds": time.time() - t0,
    }
    return w, b, diag


def predict_proba_indexed(x, rows: np.ndarray, w: np.ndarray, b: np.ndarray,
                          batch: int = BATCH_SIZE) -> np.ndarray:
    """Softmax probabilities for `x[rows]`, scored a batch at a time."""
    out = np.empty((len(rows), w.shape[1]), np.float32)
    for s in range(0, len(rows), batch):
        take = rows[s : s + batch]
        out[s : s + batch] = _softmax_rows(np.asarray(x[take], np.float32) @ w + b)
    return out


class SoftmaxHead:
    """Fitted head with sklearn's predict surface, so callers need no change.

    The bundle is pickled by `train.fit` and reloaded by `predict` and the eval
    path, all of which call `.classes_` and `.predict_proba`. Presenting that
    surface keeps the solver swap contained to the fit sites; nothing downstream
    can tell the difference except by the missing `.coef_` shape convention
    (sklearn stores (n_classes, d), this stores its transpose, since the forward
    pass wants (d, n_classes) and transposing per call is pure waste).

    Scoring stays chunked. Callers hand it the full production matrix, and a
    float32 copy of that is a resident-memory decision, not a correctness one.
    """

    def __init__(self, w: np.ndarray, b: np.ndarray, classes: np.ndarray, diag: dict):
        self.w = np.asarray(w, np.float32)
        self.b = np.asarray(b, np.float32)
        self.classes_ = np.asarray(classes)
        self.diag = diag

    def predict_proba(self, x, batch: int = BATCH_SIZE) -> np.ndarray:
        out = np.empty((len(x), self.w.shape[1]), np.float32)
        for s in range(0, len(x), batch):
            chunk = np.asarray(x[s : s + batch], np.float32)
            out[s : s + batch] = _softmax_rows(chunk @ self.w + self.b)
        return out

    def predict(self, x) -> np.ndarray:
        return self.classes_[self.predict_proba(x).argmax(1)]


def fit_head(x, y: np.ndarray, rows: np.ndarray | None = None, *, seed: int,
             epochs: int = EPOCHS, batch_size: int = BATCH_SIZE,
             lr: float = LEARNING_RATE, sample_weight: np.ndarray | None = None,
             c_inv_reg: float = 10.0, optimizer: str = OPTIMIZER,
             verbose: bool = False) -> SoftmaxHead:
    """Fit a `SoftmaxHead` over `x[rows]` from string labels `y`.

    `y` is indexed by the full array, matching `rows`, so the caller never has to
    slice the label vector to line it up.
    """
    if rows is None:
        rows = np.arange(len(y))
    classes = np.array(sorted(set(y[rows].tolist())))
    cidx = {c: i for i, c in enumerate(classes)}
    y_idx = np.full(len(y), -1, np.int64)
    for c, i in cidx.items():
        y_idx[y == c] = i
    w, b, diag = fit_minibatch_softmax_indexed(
        x, y_idx, rows, len(classes), seed, epochs=epochs, batch_size=batch_size,
        lr=lr, sample_weight=sample_weight, c_inv_reg=c_inv_reg,
        optimizer=optimizer, verbose=verbose,
    )
    return SoftmaxHead(w, b, classes, diag)
