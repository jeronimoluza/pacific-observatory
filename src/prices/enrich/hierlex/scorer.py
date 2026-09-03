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

POLICIES = ("conservative_risk", "empirical_98")


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
