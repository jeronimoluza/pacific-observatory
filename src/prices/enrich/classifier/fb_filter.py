"""Cheap char-ngram pre-filter that decides which product names are in-scope for
the (embedding -> head) classifier BEFORE the expensive ensemble embed.

Embedding the full 1.585M-name corpus through 0.6B+4B+8B costs ~95h on 16GB, but
the only live deliverable is COICOP division 01 (food & beverages), ~22% of the
corpus. The bake-off winner (2026-07-28) is a HashingVectorizer(char_wb, (2,5),
2**20) + LogisticRegression(C=10) operating at tau=0.33 — ~98% gold / ~93% real
F&B recall at a 24% corpus pass-rate, a 4.2x embed cut. The vectorizer is
stateless, so the joblib bundle is self-contained.

Router-shaped on purpose: ``route(names)`` returns ``{division: names}``. Today
only division 01 has a gate, so it returns ``{"01": survivors}``; when a second
division gets its own gate this becomes the multiclass division router with no
change to the classify caller. ``in_scope_names(names, division)`` falls back to
"embed everything" for a division that has no gate, preserving prior behavior.
"""

from __future__ import annotations

from functools import lru_cache

import joblib
import numpy as np

from prices.enrich import config

FB_GATE_PATH = config.ENRICH_DIR / "_models" / "fb_gate.joblib"


@lru_cache(maxsize=1)
def _gate():
    b = joblib.load(FB_GATE_PATH)
    return b["vec"], b["clf"], float(b["threshold"])


def fb_proba(names) -> np.ndarray:
    vec, clf, _ = _gate()
    x = vec.transform([str(n) for n in names])
    return clf.predict_proba(x)[:, 1]


def route(names) -> dict[str, list[str]]:
    names = [str(n) for n in names]
    _, _, thr = _gate()
    proba = fb_proba(names)
    return {"01": [n for n, p in zip(names, proba) if p >= thr]}


def in_scope_names(names, division: str) -> set[str]:
    """Names to embed for `division`. Falls back to all names when no gate
    exists for that division (so a non-01 run behaves as before)."""
    routed = route(names)
    if division not in routed:
        return {str(n) for n in names}
    return set(routed[division])
