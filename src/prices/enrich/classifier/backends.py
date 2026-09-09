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

SCORE_COLS = ("leaf", "conf", "accepted", "leaf_top1", "gate_score")


@dataclass(frozen=True)
class ScoreResult:
    """What a backend hands back: verdicts, plus who never got one.

    `unembedded` is kept OUT of `frame` and always keyed by NAME, whatever the
    backend's `key_cols` are, because whether a vector exists is a property of
    the name alone. It is not an empty verdict: a name with no vector was never
    scored, which is a sourcing/embedding backlog rather than a model refusal,
    and collapsing the two makes coverage unmeasurable — the rejected rows are
    the denominator.
    """

    frame: pd.DataFrame
    unembedded: frozenset[str]


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
    # The full decision table — every input_hash, rejects and unembedded
    # rows retained. `classified_path` is a filtered VIEW of it, so both
    # come out of one scoring pass and coverage stays measurable.
    decisions_path: Path
    divisions: tuple[str, ...]
    score: Callable[..., ScoreResult]
    # None means the model cannot be trained here. That is a property of the
    # backend, not a gap: a frozen bundle has no training procedure to call.
    fit: Optional[Callable[[str], dict]]

    @property
    def trainable(self) -> bool:
        return self.fit is not None


def _score_head(products: pd.DataFrame, version=None, workers: int = 1) -> ScoreResult:
    """The in-house head: embed once per unique name and score from the store.

    Every division is scored. The F&B pre-filter that used to stand here was
    justified purely as an embedding-cost cut, and the store now covers ~32.3M
    names, so it saved nothing and cost recall -- its gate is division-01 only,
    which silently dropped alcoholic beverages. Scope belongs to the build.
    """
    from prices.enrich.classifier import batch_embed, embed_store
    from prices.enrich.classifier.predict import load_predictor

    predictor = load_predictor(version)
    names = products["product_name_original"].astype(str)
    uniq = pd.Index(names.unique())
    embedded, unembedded = embed_store.split_by_store_coverage(uniq)
    leaf_by, conf_by, ok_by = batch_embed.embed_and_predict(
        predictor, pd.Index(embedded), workers=workers
    )
    frame = pd.DataFrame(
        {
            "product_name_original": list(leaf_by.keys()),
            "leaf": [leaf_by[n] for n in leaf_by],
            "conf": [float(conf_by[n]) for n in leaf_by],
            "accepted": [bool(ok_by[n]) for n in leaf_by],
            # The head's top-1 IS `leaf`; acceptance is a separate threshold on
            # `conf`, so the unaccepted top-1 is never lost and needs no second
            # column to recover. `gate_score` is that same confidence: the head
            # has no meta-gate, and inventing a distinct number here would make
            # the two backends look more alike than they are.
            "leaf_top1": [leaf_by[n] for n in leaf_by],
            "gate_score": [float(conf_by[n]) for n in leaf_by],
        }
    )
    return ScoreResult(frame=frame, unembedded=frozenset(unembedded))


def _hierlex():
    """Import the adapter, or say what is missing and how to work around it."""
    try:
        from prices.enrich import hierlex  # noqa: PLC0415

        # Importing the package alone does not bind `hierlex.driver` --
        # `hierlex/__init__.py` is a docstring and imports nothing. Every caller
        # here wants the driver, so import it by name; without this the attribute
        # exists only if some other module happened to import it first, which is
        # true under pytest and false in the pipeline.
        from prices.enrich.hierlex import driver  # noqa: PLC0415, F401
    except ImportError as exc:  # pragma: no cover - exercised via monkeypatch
        raise RuntimeError(_HIERLEX_MISSING) from exc
    return hierlex


def _score_hierlex(
    products: pd.DataFrame, version=None, workers: int = 1, tau: float | None = None
) -> ScoreResult:
    """Score the frozen bundle bucket-major over (name, country) pairs.

    The adapter owns the model; this owns the fan-out and the column contract,
    so the two can be developed apart and still meet.
    """
    hierlex = _hierlex()
    # `workers` reaches the driver now. It used to be dropped here, because a
    # whole bucket gathered at once is ~9 GB and N workers hold N of them, so
    # the driver walked buckets serially and the flag would have been a lie.
    # The driver gathers a scoring chunk at a time instead, and clamps the count
    # to a memory budget itself -- asking for sixteen gets whatever fits.
    # Forwarding it is still the thing to get wrong: it once raised TypeError on
    # every call, against a driver that had never taken the parameter, so the
    # backend test asserts both that the driver's signature carries `workers`
    # and that the value arrives.
    hierlex.driver.run(version=version, workers=workers)
    shards = hierlex.driver.load_shards(version=version)
    # `assigned_coicop` is NOT always a COICOP code. For a fallback that lands on
    # a parent with no "n.e.c." leaf, the scorer emits a synthetic
    # `<parent>.__parent_fallback__` token, and `is_leaf` is how it says so.
    # Acceptance has to carry that: the token shares the parent's prefix, so the
    # division filter downstream lets it through and it would be written out as
    # a real code.
    # Re-thresholded here rather than read from `shards["accepted"]`, which the
    # scoring run froze at whatever policy it used. The shards carry the
    # continuous score precisely so the operating point stays a downstream
    # decision, so switching it costs a re-read instead of re-scoring 7.29M
    # pairs. At the bundle's own tau this reproduces the frozen column exactly:
    # `accepted` is `cal >= tau` and nothing else (`scorer.py:127`), and the
    # float32 the shard stores round-trips the comparison without moving a row.
    from prices.enrich.hierlex import scorer as hlx_scorer  # noqa: PLC0415

    tau = hlx_scorer.resolve_tau(version, tau=tau)
    accepted = (shards["calibrated_correctness_score"].astype(float) >= tau) & shards[
        "is_leaf"
    ].astype(bool)
    # The bundle's parent-fallback rewrites a leaf the model proposed into its
    # parent's "n.e.c." sibling whenever leaf-level confidence is short of the
    # action threshold. Keep the proposed leaf instead, on the rows where the
    # rewrite landed on a real leaf.
    #
    # Measured on the bundle's own nested outer-OOF gold (the 20260908 retrain,
    # 2,154 accepted rows where the rewrite actually changed the code): the code
    # the rewrite WRITES is correct 15.6% of the time and the leaf it DISCARDS
    # is correct 75.8%. Depth-3 accuracy is identical either way -- 98.5% --
    # because the rewrite never leaves the depth-3 parent: on 162,301 production
    # rows it stays inside that prefix 100.00% of the time and the code it emits
    # ends in ".9" 100.00% of the time. So this is strictly better at leaf grain
    # and exactly neutral above it, worth +0.60 pt of leaf-exact precision at
    # zero coverage cost.
    #
    # It is not caution being removed. A fallback that is right 15.6% of the
    # time against a discarded leaf that is right 75.8% is not expressing doubt
    # about which sibling is correct, it is losing information the gate was
    # already confident in -- these rows carry a median gate_score of 0.972
    # against an acceptance threshold of 0.9437.
    #
    # `is_leaf` is still required: where the parent has no "n.e.c." leaf the
    # scorer emits the synthetic `<parent>.__parent_fallback__` token, those
    # rows are a parent-grain decision and keep going out as `fallback_parent`.
    _rewritten = shards["is_fallback"].astype(bool) & shards["is_leaf"].astype(bool)
    _leaf = shards["assigned_coicop"].where(~_rewritten, shards["proposed_leaf"])
    frame = pd.DataFrame(
        {
            "product_name_original": shards["name"].astype(str),
            "country": shards["country"].astype(str),
            "leaf": _leaf,
            # Leaf softmax score, NOT the gate score -- the same split
            # hierlex/decide.py makes. Two different numbers: acceptance is a
            # threshold on the gate, and collapsing them hides a confident leaf
            # behind a doubtful gate.
            "conf": shards["original_score"].astype(float),
            "accepted": accepted,
            # The leaf the model proposed before the gate ruled on it. Keeping it
            # separates "this country has no such product" from "it has them but
            # the gate would not commit" — two findings with different remedies.
            "leaf_top1": shards["proposed_leaf"].astype(str),
            "gate_score": shards["calibrated_correctness_score"].astype(float),
        }
    )
    # Names the driver never scored because the store has no vector for them.
    # Recovered from the shards rather than recomputed: the driver already paid
    # for this screen, and a second `split_by_store_coverage` here could disagree
    # with the one the scoring pass actually used.
    scored_names = set(frame["product_name_original"])
    all_names = set(products["product_name_original"].astype(str))
    return ScoreResult(frame=frame, unembedded=frozenset(all_names - scored_names))


def _fit_head(version: str) -> dict:
    from prices.enrich.classifier import train  # noqa: PLC0415

    return train.fit(version)


HEAD = Backend(
    name="head",
    key_cols=("product_name_original",),
    classified_path=config.CLASSIFIED_PARQUET,
    decisions_path=config.DECISIONS_PARQUET,
    divisions=config.BUILD_DIVISIONS,  # 01 food & non-alc bev + 02 alcoholic bev
    score=_score_head,
    fit=_fit_head,
)

HIERLEX = Backend(
    name="hierlex",
    key_cols=("product_name_original", "country"),
    classified_path=config.CLASSIFIED_HIERLEX_PARQUET,
    decisions_path=config.DECISIONS_HIERLEX_PARQUET,
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
