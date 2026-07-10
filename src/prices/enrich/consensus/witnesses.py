"""Witness adapters (W4.1) — thin wrappers turning already-shipped machinery
into `Vote`s the consensus gate can weigh.

Every witness is *batch* (``{norm_key -> Vote}``) and *abstain-safe*: a witness
whose backend artifact is missing (no classifier, no tier-b index, no spaCy)
returns nothing for those keys rather than raising. That is what lets `make ci`
stay green and lets the heavy corpus pass sit behind ⛔ Gate 3 — witnesses that
cannot speak simply do not vote.

Vote surfaces (kind):
  leaf         a concrete COICOP leaf code
  reject       __EXCLUDE__ / __OTHER_FORM__
  division     a 2-digit COICOP division (weak corroboration, e.g. w_source)
  plausibility plausible/implausible/unknown for a *proposed* leaf (w_price)
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from prices.enrich import label_store, lexicon as lexicon_mod
from prices.enrich.consensus import REJECT_LABELS
from prices.enrich.keys import norm_key

_DECISION_LABEL = {"exclude": "__EXCLUDE__", "other_form": "__OTHER_FORM__"}


@dataclass(frozen=True)
class Vote:
    witness: str
    label: str | None
    kind: str
    strength: float
    detail: dict = field(default_factory=dict)


# --------------------------------------------------------------------------- #
# w_memo — authoritative memory (label_store)
# --------------------------------------------------------------------------- #
def w_memo(keys) -> dict[str, Vote]:
    act = label_store.lookup(keys)
    out: dict[str, Vote] = {}
    if act.empty:
        return out
    for r in act.itertuples(index=False):
        dec = r.decision
        if dec == "leaf":
            label, kind = str(r.leaf), "leaf"
        elif dec in _DECISION_LABEL:
            label, kind = _DECISION_LABEL[dec], "reject"
        else:
            continue  # ambiguous_class -> memo abstains
        conf = float(r.confidence) if pd.notna(r.confidence) else 1.0
        out[r.canonical_key] = Vote(
            "memo", label, kind, conf, {"tier": r.tier, "provenance": r.provenance}
        )
    return out


# --------------------------------------------------------------------------- #
# w_lexicon — n-gram phrase evidence
# --------------------------------------------------------------------------- #
def _lexicon_index(lex: pd.DataFrame) -> dict[str, tuple[str, int]]:
    idx: dict[str, tuple[str, int]] = {}
    for ph, lab, n in zip(lex["phrase"], lex["label"], lex["n"]):
        idx[str(ph)] = (str(lab), int(n))
    return idx


def w_lexicon(keys, lex: pd.DataFrame | None = None) -> dict[str, Vote]:
    lex = lexicon_mod.load_lexicon() if lex is None else lex
    if lex.empty:
        return {}
    idx = _lexicon_index(lex)
    out: dict[str, Vote] = {}
    for k in keys:
        nk = norm_key(k)
        best: tuple[str, int] | None = None
        for ph in lexicon_mod._phrases(nk):
            hit = idx.get(ph)
            if hit and (best is None or hit[1] > best[1]):
                best = hit
        if best is None:
            continue
        label, n = best
        kind = "reject" if label in REJECT_LABELS else "leaf"
        # strength saturates with support; a 20-count phrase ~0.5, 200 ~0.9
        strength = min(0.95, n / (n + 20.0))
        out[nk] = Vote("lexicon", label, kind, strength, {"n": n})
    return out


# --------------------------------------------------------------------------- #
# w_model — learned classifier (W2)
# --------------------------------------------------------------------------- #
def w_model(keys, version: str | None = None) -> dict[str, Vote]:
    try:
        from prices.enrich.classifier.predict import load_predictor

        predictor = load_predictor(version)
    except Exception:
        return {}  # no trained model -> abstain
    names = [str(k) for k in keys]
    if not names:
        return {}
    pred, conf, leaf_among = predictor.scores(names)
    out: dict[str, Vote] = {}
    for k, p, c, la in zip(names, pred, conf, leaf_among):
        nk = norm_key(k)
        kind = "reject" if str(p) in REJECT_LABELS else "leaf"
        out[nk] = Vote(
            "model",
            str(p),
            kind,
            float(c),
            {"leaf_among": str(la), "version": predictor.version},
        )
    return out


# --------------------------------------------------------------------------- #
# w_knn — tier-b embedding retrieval
# --------------------------------------------------------------------------- #
def w_knn(
    rows: pd.DataFrame, name_col: str, country_col: str = "country"
) -> dict[str, Vote]:
    """rows: frame with a name column + country column. Abstains wholesale if
    tier-b is unavailable, and per-row when the country index is missing/misses."""
    try:
        from prices.enrich.tier_b import _lookup
    except Exception:
        return {}
    out: dict[str, Vote] = {}
    chan = rows["channel"] if "channel" in rows.columns else [None] * len(rows)
    cat = rows["category"] if "category" in rows.columns else [None] * len(rows)
    for name, country, ch, ca in zip(rows[name_col], rows[country_col], chan, cat):
        if not str(country):
            continue
        try:
            hit = _lookup.query(str(country), str(name), channel=ch, category=ca)
        except Exception:
            continue
        if not getattr(hit, "accepted", False):
            continue
        leaf = (hit.payload or {}).get("coicop_code")
        if not leaf:
            continue
        out[norm_key(name)] = Vote(
            "knn",
            str(leaf),
            "leaf",
            float(getattr(hit, "top1_cluster_agreement", 0.0) or 0.0),
            {
                "cosine": float(getattr(hit, "top1_cosine", 0.0) or 0.0),
                "escalation": getattr(hit, "escalation_reason", ""),
                "cross_channel": (hit.payload or {}).get("cross_channel_accept"),
            },
        )
    return out


# --------------------------------------------------------------------------- #
# w_source — source-declared COICOP division (weak corroboration)
# --------------------------------------------------------------------------- #
def _declared_division(val) -> str | None:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    if isinstance(val, str):
        codes = [c.strip() for c in val.replace(";", ",").split(",") if c.strip()]
    elif isinstance(val, (list, tuple, set)):
        codes = [str(c).strip() for c in val if str(c).strip()]
    else:
        return None
    divs = {c[:2] for c in codes if len(c) >= 2 and c[:2].isdigit()}
    return next(iter(divs)) if len(divs) == 1 else None


def w_source(
    rows: pd.DataFrame,
    name_col: str,
    declared_col: str = "declared_coicop_codes",
) -> dict[str, Vote]:
    if declared_col not in rows.columns:
        return {}
    out: dict[str, Vote] = {}
    for name, declared in zip(rows[name_col], rows[declared_col]):
        div = _declared_division(declared)
        if div is None:
            continue
        out[norm_key(name)] = Vote(
            "source", div, "division", 0.3, {"declared": str(declared)}
        )
    return out


# --------------------------------------------------------------------------- #
# w_price — plausibility of a *proposed* leaf given unit economics
# --------------------------------------------------------------------------- #
_BANDS_CACHE: dict[str, pd.DataFrame] = {}


def _bands() -> pd.DataFrame:
    if "df" not in _BANDS_CACHE:
        from prices.enrich.bands import load_price_bands

        _BANDS_CACHE["df"] = load_price_bands()
    return _BANDS_CACHE["df"]


def price_plausibility(leaf, country, basis, unit_value_usd) -> Vote:
    """Vote on whether `unit_value_usd` sits inside leaf's (country,basis) band.
    plausible / implausible / unknown — a veto/tiebreak signal, not a proposer."""
    b = _bands()
    if (
        b.empty
        or leaf is None
        or unit_value_usd is None
        or (isinstance(unit_value_usd, float) and pd.isna(unit_value_usd))
    ):
        return Vote("price", None, "plausibility", 0.0, {"verdict": "unknown"})
    m = b[
        (b["leaf"] == str(leaf))
        & (b["country"] == str(country))
        & (b["pricing_basis"] == str(basis))
    ]
    if m.empty:
        return Vote("price", str(leaf), "plausibility", 0.0, {"verdict": "unknown"})
    row = m.iloc[0]
    uv = float(unit_value_usd)
    inside = float(row["band_lo"]) <= uv <= float(row["band_hi"])
    verdict = "plausible" if inside else "implausible"
    return Vote(
        "price",
        str(leaf),
        "plausibility",
        0.6,
        {
            "verdict": verdict,
            "band_lo": float(row["band_lo"]),
            "band_hi": float(row["band_hi"]),
        },
    )
