"""Load a trained (embedding -> head) classifier and score raw product names.

``predict(names)`` embeds each RAW name, runs the logistic head, and applies the
operating point: accept the top-1 leaf only when its probability clears the
bundle's global gate `tau` AND the name does not trip that leaf's trap veto.
Returns the argmax leaf, its confidence, and the accept decision; the caller
assigns the COICOP code only where ``accepted`` is True.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import joblib
import numpy as np

from prices.enrich import embedding, vetoes
from prices.enrich.classifier import MODEL_FILE, read_latest, version_dir


@dataclass
class Prediction:
    leaf: np.ndarray  # top-1 leaf per name (post-reroute)
    conf: np.ndarray  # top-1 probability
    accepted: np.ndarray  # bool: conf >= tau, minus vetoes, plus reroutes


class Predictor:
    def __init__(self, version: str):
        bundle = joblib.load(version_dir(version) / MODEL_FILE)
        self.version = version
        self.clf = bundle["clf"]
        self.classes = np.asarray(bundle["classes"])
        self.tau = float(bundle["tau"])
        self.division = bundle.get("division")

    def predict(self, names) -> Prediction:
        names = [str(n) for n in names]
        if not names:
            empty_s = np.empty(0, object)
            return Prediction(empty_s, np.empty(0), np.empty(0, bool))
        x = embedding.embed_names(names)
        p = self.clf.predict_proba(x)
        top = p.argmax(axis=1)
        leaf = np.array(self.classes[top], dtype=object)
        conf = p[np.arange(len(top)), top]
        accepted = conf >= self.tau
        for i, (lf, nm) in enumerate(zip(leaf, names)):
            action = vetoes.veto_action(lf, nm)
            if action is None:
                continue
            if action == vetoes.REJECT:
                accepted[i] = False
            else:
                leaf[i] = action
                accepted[i] = True
        return Prediction(leaf, conf, accepted)


@lru_cache(maxsize=4)
def _cached(version: str) -> Predictor:
    return Predictor(version)


def load_predictor(version: str | None = None) -> Predictor:
    v = version or read_latest()
    if v is None:
        raise FileNotFoundError(
            "no classifier version available (train one via `prices train-classifier`)"
        )
    return _cached(v)


def predict(names, version: str | None = None) -> Prediction:
    return load_predictor(version).predict(names)
