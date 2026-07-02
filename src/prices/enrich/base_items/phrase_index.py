"""Food sub-label phrase index — pins a name to a concrete non-GREEN leaf.

Faithful port of _food_phrase_index / _sub_ngram / _grams / _norm from
apple_three_bucket.py. Reads the shipped tier-b anchor store so a name whose
longest food n-gram matches an anchor label is routed to that anchor's COICOP
leaf (form_mover) instead of the base_item's default leaf.
"""

from __future__ import annotations

import re

from prices.enrich.keywords import _registry as registry

TOK = re.compile(r"[a-z0-9]+")
FOOD_DIVS = {"01", "02"}


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", s.lower())).strip()


def _grams(s: str) -> list[str]:
    ts = _norm(s).split()
    return [" ".join(ts[i : i + 3]) for i in range(len(ts) - 2)] + [
        " ".join(ts[i : i + 2]) for i in range(len(ts) - 1)
    ]


def food_phrase_index() -> dict[str, tuple[str, str]]:
    """{n-gram phrase -> (anchor_id, coicop_code)} over food-division anchors."""
    store = registry._sub_labels_store()
    idx: dict[str, tuple[str, str]] = {}
    for cls in FOOD_DIVS:
        for _lf, recs in store.get(cls, {}).items():
            for d in recs:
                sid, code = str(d["id"]), str(d["numeric_id"])
                phrases = [str(d["label"]).lower()]
                for _lg, kws in d.get("keywords_by_lang", {}).items():
                    phrases += [str(k).lower() for k in kws]
                for ph in phrases:
                    ts = TOK.findall(ph)
                    if len(ts) >= 2:
                        idx[" ".join(ts)] = (sid, code)
    return idx


def sub_ngram(name: str, idx: dict[str, tuple[str, str]]):
    """Longest food sub-label phrase (>=2 tok) present -> (phrase, id, code)."""
    for g in sorted(set(_grams(name)), key=lambda g: -len(g.split())):
        if g in idx:
            return (g,) + idx[g]
    return None
