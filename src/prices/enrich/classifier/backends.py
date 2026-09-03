"""Which model assigns the COICOP leaf, and whether it can be trained here.

Two backends coexist, and the difference that matters is not accuracy but
ownership:

  - **hierlex** (default) is HierLex-Select v1, a frozen third-party bundle. It
    is scored, never fitted — the weights arrived as a package and the
    do-not-retrain decision is deliberate. `fit` is therefore `None`, and the
    training seam raises rather than silently falling back to something else.
  - **head** is the in-house (embedding -> logistic softmax) classifier. It is
    the one this repo can still train, via `classifier/train.py`.

They differ structurally in two ways the rest of the pipeline has to respect.
HierLex scores at **(name, country)** grain because country is one of its gate
features, where the head is country-blind and scores at name grain — hence
`key_cols`. And each writes its **own** output file, so running one never
overwrites the other and both can be compared against the same corpus.

The training placeholder is real, not decorative: `fit_backend` is where a
future retrain lands, and today it either calls the head's `train.fit` or tells
you exactly why the chosen backend has nothing to fit.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import pandas as pd

from prices.enrich import config

SCORE_COLS = ("leaf", "conf", "accepted")

_HIERLEX_MISSING = (
    "the hierlex adapter is not installed on this branch.\n"
    "`prices.enrich.hierlex` wraps the frozen HierLex-Select bundle and is "
    "developed separately; this branch carries the stage, driver and CLI seam "
    "it plugs into but not the adapter itself.\n"
    "Until it lands, score with the in-house head instead:\n"
    "    prices process --stage classify --backend head"
)


@dataclass(frozen=True)
class Backend:
    """One way to assign a leaf, and everything the stage needs to run it."""

    name: str
    key_cols: tuple[str, ...]
    classified_path: Path
    divisions: tuple[str, ...]
    score: Callable[..., pd.DataFrame]
    # None means the model cannot be trained here. That is a property of the
    # backend, not a gap: a frozen bundle has no training procedure to call.
    fit: Optional[Callable[[str], dict]]

    @property
    def trainable(self) -> bool:
        return self.fit is not None


def _score_head(products: pd.DataFrame, version=None, workers: int = 1) -> pd.DataFrame:
    """The in-house head, unchanged: pre-filter to the division, embed the
    survivors once per unique name, score from the store."""
    from prices.enrich.classifier import batch_embed, fb_filter
    from prices.enrich.classifier.predict import load_predictor

    predictor = load_predictor(version)
    names = products["product_name_original"].astype(str)
    uniq = pd.Index(names.unique())
    scoped = fb_filter.in_scope_names(uniq, config.CLASSIFIER_DEFAULT_DIVISION)
    uniq = pd.Index([n for n in uniq if n in scoped])
    leaf_by, conf_by, ok_by = batch_embed.embed_and_predict(
        predictor, uniq, workers=workers
    )
    return pd.DataFrame(
        {
            "product_name_original": list(leaf_by.keys()),
            "leaf": [leaf_by[n] for n in leaf_by],
            "conf": [float(conf_by[n]) for n in leaf_by],
            "accepted": [bool(ok_by[n]) for n in leaf_by],
        }
    )


def _hierlex():
    """Import the adapter, or say what is missing and how to work around it."""
    try:
        from prices.enrich import hierlex  # noqa: PLC0415
    except ImportError as exc:  # pragma: no cover - exercised via monkeypatch
        raise RuntimeError(_HIERLEX_MISSING) from exc
    return hierlex


def _score_hierlex(
    products: pd.DataFrame, version=None, workers: int = 1
) -> pd.DataFrame:
    """Score the frozen bundle bucket-major over (name, country) pairs.

    The adapter owns the model; this owns the fan-out and the column contract,
    so the two can be developed apart and still meet.
    """
    hierlex = _hierlex()
    hierlex.driver.run(version=version, workers=workers)
    shards = hierlex.driver.load_shards(version=version)
    return pd.DataFrame(
        {
            "product_name_original": shards["name"].astype(str),
            "country": shards["country"].astype(str),
            "leaf": shards["assigned_coicop"],
            "conf": shards["calibrated_correctness_score"].astype(float),
            "accepted": shards["accepted"].astype(bool),
        }
    )


def _fit_head(version: str) -> dict:
    from prices.enrich.classifier import train  # noqa: PLC0415

    return train.fit(version)


HEAD = Backend(
    name="head",
    key_cols=("product_name_original",),
    classified_path=config.CLASSIFIED_PARQUET,
    divisions=(config.CLASSIFIER_DEFAULT_DIVISION,),
    score=_score_head,
    fit=_fit_head,
)

HIERLEX = Backend(
    name="hierlex",
    key_cols=("product_name_original", "country"),
    classified_path=config.CLASSIFIED_HIERLEX_PARQUET,
    divisions=config.BUILD_DIVISIONS,
    score=_score_hierlex,
    fit=None,  # frozen bundle: scored, never fitted
)

BACKENDS = {b.name: b for b in (HIERLEX, HEAD)}


def get(name: str | None = None) -> Backend:
    name = name or config.CLASSIFIER_BACKEND
    try:
        return BACKENDS[name]
    except KeyError:
        raise ValueError(
            f"unknown classifier backend {name!r}; have {sorted(BACKENDS)}"
        ) from None


def fit_backend(name: str | None = None, version: str = "") -> dict:
    """Train the chosen backend, or refuse for a reason worth reading.

    This is the seam a future retrain hangs off. It exists now so that adding
    training back is wiring a function in here, not rediscovering where the
    pipeline would have called it.
    """
    backend = get(name)
    if backend.fit is None:
        raise NotImplementedError(
            f"the {backend.name!r} backend is a frozen bundle and is not trained "
            "in this repo — it is versioned, sha256-verified and scored as-is. "
            "To train the in-house model instead: prices train-classifier"
        )
    return backend.fit(version)
