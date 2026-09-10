"""Resident HierLex-Select scorer — load the frozen models once, score many chunks.

The bundle ships a CLI that reads a table, materializes every embedding, scores,
and exits. At corpus scale that CLI cannot run: its embedding matrix alone is
7.29M x 7680 float32 (~220 GB), and per-chunk reinvocation would reload 1.1 GB of
lexical pipelines for every chunk. This module keeps the loaded models resident
and exposes the bundle's own `main()` sequence as a function over an
already-materialized chunk, so the scoring path is byte-for-byte the vendored
code and only the batching around it is ours.

Scoring is keyed on (name, country), not name. Country is a categorical gate
feature and drives `country_leaf_support`, so the same product name in two
countries is two different rows to this model — unlike the in-house head, which
is country-blind. The corpus has 7.29M pairs against 7.16M names, so pair grain
costs 1.8% more scoring and no extra embedding.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

import joblib
import numpy as np
import pandas as pd

from prices.enrich.hierlex import package

BUNDLE_POLICIES = ("conservative_risk", "empirical_98")

# Operating points solved in this repo, as opposed to the two the bundle ships.
# Each is the LOWEST tau whose accepted set still meets the named precision, so
# each buys the most coverage that target allows.
#
# These are calibration-specific: a tau is a threshold on THIS bundle's Platt
# output, so it is meaningless against another bundle. Solved against
# `hierlex_select_v1_20260910`; re-solve before pointing them at any other.
#
# That warning is not theoretical, and the 20260908 -> 20260910 retrain is the
# worked example. `target_95` moved 0.5893 -> 0.6988. Left stale, the old value
# accepts 271,764 rows of the new audit at 94.21% -- it misses the target by
# 0.79 points and ships ~2,145 extra wrong labels as trusted, on the gold audit
# alone, before scaling to the production corpus. Nothing raises: the stale tau
# is a perfectly valid float and the run looks clean.
#
# Solved on the bundle's own nested-OOF audit (`implementation_oof_decisions`,
# 307,773 rows, balanced 5-fold), and cross-validated before being written down:
# choosing tau on four folds and measuring precision on the fifth reproduces the
# target to within 0.002 points at every level, and the per-fold tau spread at
# `target_95` is 0.6942-0.7008. The curve is also flat there -- tau +/-0.10
# moves precision only 94.3%-95.9% -- so a small error in this number is not a
# cliff.
#
# These are OOF scores, so the taus transfer to production rows, which the
# bundle never trained on. They do NOT transfer to the ~308k gold rows, whose
# production scores are in-sample and inflated; validate against the OOF audit,
# never against the production cache.
LOCAL_TAUS = {
    "target_95": 0.6987841129302979,
    "target_92": 0.309093713760376,
    "target_90": 0.1546705812215805,
}

POLICIES = BUNDLE_POLICIES + tuple(LOCAL_TAUS)


def resolve_tau(
    version: str | None = None,
    policy: str | None = None,
    tau: float | None = None,
) -> float:
    """The acceptance threshold to apply, without loading the bundle.

    An explicit `tau` wins outright; otherwise `policy` (defaulting to the
    configured one) is looked up in the bundle's thresholds and then in
    `LOCAL_TAUS`. Reads the manifest rather than the models because callers want
    a float and loading 1.65 GB of weights to get one is the thing this avoids.
    """
    from prices.enrich import config  # noqa: PLC0415 - avoids an import cycle

    if tau is None:
        tau = config.HIERLEX_TAU
    if tau is not None:
        tau = float(tau)
        if not 0.0 <= tau <= 1.0:
            raise ValueError(f"tau must lie in [0, 1], got {tau!r}")
        return tau
    policy = policy or config.HIERLEX_POLICY
    if policy in LOCAL_TAUS:
        return float(LOCAL_TAUS[policy])
    if policy not in BUNDLE_POLICIES:
        raise ValueError(f"unknown policy {policy!r}; expected one of {POLICIES}")
    meta = package.manifest(package.resolve(version))
    return float(meta["thresholds"]["thresholds"][f"lexical_correctness_gate_{policy}"])


@dataclass
class Scorer:
    version: str
    mod: ModuleType
    model_dir: Path
    classes: np.ndarray
    class_set: frozenset
    w_leaf: np.ndarray
    b_leaf: np.ndarray
    w_pref: np.ndarray
    b_pref: np.ndarray
    prefix3_classes: np.ndarray
    raw_pipe: object
    lex2_pipe: object
    gate: object
    platt: object
    supports: dict
    fallback_cfg: dict
    expected_cols: list
    thresholds: dict

    def tau(self, policy: str) -> float:
        return float(self.thresholds[f"lexical_correctness_gate_{policy}"])

    def score(
        self,
        names: np.ndarray,
        countries: np.ndarray,
        x: np.ndarray,
        policy: str = "conservative_risk",
        batch_size: int = 4096,
    ) -> pd.DataFrame:
        """One row per input (name, country). `x` is the weighted 7,680-d block.

        Mirrors the bundle's `main()` step for step. The order matters: the
        prefix3 reweight has to happen before the action frame, because the
        action frame's argmax is taken on the REWEIGHTED distribution, and the
        gate was fitted on features derived from that same frame.
        """
        m = self.mod
        if x.shape[1] != 7680:
            raise ValueError(f"expected 7,680 embedding dimensions, got {x.shape[1]}")
        if not (len(names) == len(countries) == len(x)):
            raise ValueError("names, countries and embeddings must be the same length")
        if policy not in POLICIES:
            raise ValueError(f"unknown policy {policy!r}; expected one of {POLICIES}")

        names = np.asarray(names, dtype=object)
        countries = np.asarray(
            [str(c or "missing").lower() for c in countries], dtype=object
        )
        names_norm = np.array([m.normalize_title(str(s)) for s in names], dtype=object)
        script = np.array([m.script_family(str(s)) for s in names], dtype=object)

        softmax = m.predict_linear_softmax(x, self.w_leaf, self.b_leaf, batch_size)
        pref = m.predict_linear_softmax(x, self.w_pref, self.b_pref, batch_size)
        prefix3 = m.reweight_prefix(self.classes, softmax, self.prefix3_classes, pref)

        raw_lex = m.align_proba(
            self.raw_pipe.named_steps["clf"].classes_,
            self.raw_pipe.predict_proba(names),
            self.classes,
        )
        lex2 = m.align_proba(
            self.lex2_pipe.named_steps["clf"].classes_,
            self.lex2_pipe.predict_proba(names_norm),
            self.classes,
        )

        frame = m.action_frame_inference(
            np.arange(len(names)),
            self.classes,
            prefix3,
            names,
            countries,
            script,
            self.fallback_cfg,
        )
        feat = m.build_prefix3_lex_features(
            frame,
            self.classes,
            names,
            self.supports,
            {"softmax": softmax, "prefix3": prefix3},
            raw_lex,
            lex2,
        )
        missing = sorted(set(self.expected_cols) - set(feat.columns))
        if missing:
            raise ValueError(f"missing gate feature columns: {missing[:10]}")

        raw_score = self.gate.predict_proba(feat)[:, 1]
        cal = self.platt.predict_proba(raw_score.reshape(-1, 1))[:, 1]
        tau = self.tau(policy)
        accepted = cal >= tau

        assigned = frame["final_action"].astype(str).to_numpy()
        return pd.DataFrame(
            {
                "name": names.astype(str),
                "country": countries.astype(str),
                "assigned_coicop": assigned,
                "proposed_leaf": frame["proposed_leaf"].astype(str).to_numpy(),
                "is_fallback": frame["is_fallback"].astype(bool).to_numpy(),
                # `final_action` is a real leaf for an exact action and for a
                # fallback that lands on the parent's "n.e.c." leaf, but a
                # synthetic `<parent>.__parent_fallback__` token when the parent
                # has no such leaf. Only the former is a usable COICOP code.
                "is_leaf": np.isin(assigned, self.classes),
                "original_score": frame["original_score"].astype(float).to_numpy(),
                "raw_correctness_score": raw_score.astype(np.float32),
                "calibrated_correctness_score": cal.astype(np.float32),
                "accepted": accepted,
                "parent_pred": frame["parent_pred"].astype(str).to_numpy(),
                "parent_score": frame["parent_score"].astype(float).to_numpy(),
                "script": script.astype(str),
            }
        )


def load(version: str | None = None, check: bool = True) -> Scorer:
    """Load a frozen bundle into memory. ~5 s and ~4 GB, dominated by the two
    lexical pipelines; hold the result for the whole run."""
    pkg = package.resolve(version)
    if check:
        problems = package.verify(pkg)
        if problems:
            raise RuntimeError(
                f"HierLex bundle {pkg.name} failed integrity check:\n  "
                + "\n  ".join(problems)
            )
    mod = package.load_module(pkg)
    md = pkg / "models"

    classes = np.load(md / "classes.npy", allow_pickle=False).astype(str)
    leaf = np.load(md / "embedding_leaf_softmax.npz", allow_pickle=False)
    pref = np.load(md / "embedding_prefix3_softmax.npz", allow_pickle=False)
    if not np.array_equal(leaf["classes"].astype(str), classes):
        raise ValueError("leaf softmax class axis does not match classes.npy")

    import json

    return Scorer(
        version=package.manifest(pkg)["method_version"],
        mod=mod,
        model_dir=md,
        classes=classes,
        class_set=frozenset(classes.tolist()),
        w_leaf=leaf["weights"].astype(np.float32),
        b_leaf=leaf["intercept"].astype(np.float32),
        w_pref=pref["weights"].astype(np.float32),
        b_pref=pref["intercept"].astype(np.float32),
        prefix3_classes=pref["prefix3_classes"].astype(str),
        raw_pipe=joblib.load(md / "raw_lexical_pipeline.joblib"),
        lex2_pipe=joblib.load(md / "normalized_lexical_v2_pipeline.joblib"),
        gate=joblib.load(md / "correctness_gate_pipeline.joblib"),
        platt=joblib.load(md / "platt_calibrator.joblib"),
        supports=mod.load_supports(md),
        fallback_cfg=json.loads(
            (md / "fallback_config.json").read_text(encoding="utf-8")
        ),
        expected_cols=json.loads(
            (md / "gate_feature_columns.json").read_text(encoding="utf-8")
        ),
        thresholds=json.loads((md / "thresholds.json").read_text(encoding="utf-8"))[
            "thresholds"
        ],
    )
