"""Resolution documents (W5) — the executor-agnostic bridge between a verdict
producer (``prices auto-verdicts`` LLM, or a dispatched agent running the
``resolve-price-conflicts`` skill, or codex) and ``prices queue apply``.

A resolution document is plain JSON so any executor can emit it:

  {"resolver": "gemini-3.1-flash-lite",          # default provenance stamp
   "resolutions": [
     {"canonical_key": "...", "decision": "leaf",
      "leaf": "01.1.1.3.9", "confidence": 0.9, "rationale": "..."},
     {"canonical_key": "...", "decision": "exclude", "confidence": 0.95},
     {"canonical_key": "...", "decision": "escalate",
      "rationale": "cross-family disagreement"}],
   "gazetteer": [                                 # optional flywheel verdicts
     {"item": "pineapple",
      "verdicts": [{"token": "juice", "role": "form", "leaf": "01.2.1.1.1"}]}]}

``decision`` is one of leaf | exclude | other_form | ambiguous_class | escalate.
``escalate`` rows are never written to the label_store — they carry to
adjudication. ``leaf`` decisions require a taxonomy-valid ``leaf`` code.

``merge_resolution_sets`` folds several documents (e.g. two family agents on the
same slice) and escalates any canonical_key the sets resolve differently — that
disagreement is itself signal, per W5.3.
"""

from __future__ import annotations

import pandas as pd

from prices.enrich.keys import norm_key

DECISIONS = {"leaf", "exclude", "other_form", "ambiguous_class"}
ESCALATE = "escalate"
_ALL = DECISIONS | {ESCALATE}

_DECISION_LABEL = {"exclude": "__EXCLUDE__", "other_form": "__OTHER_FORM__"}


def parse_resolutions(
    payload: dict, valid_leaves: set[str] | None = None
) -> list[dict]:
    """Validate a resolution document and return normalized rows.

    Each returned row: {canonical_key, decision, leaf, confidence, rationale,
    resolver}. Raises ValueError on any schema violation. When ``valid_leaves``
    is given, every ``leaf`` decision must name a code in that set.
    """
    if not isinstance(payload, dict):
        raise ValueError("resolution payload must be a JSON object")
    default_resolver = str(payload.get("resolver") or "unknown")
    items = payload.get("resolutions")
    if not isinstance(items, list) or not items:
        raise ValueError("'resolutions' must be a non-empty list")

    out: list[dict] = []
    for i, r in enumerate(items):
        if not isinstance(r, dict):
            raise ValueError(f"resolution #{i} must be an object")
        key = norm_key(str(r.get("canonical_key", "")))
        if not key:
            raise ValueError(f"resolution #{i} missing 'canonical_key'")
        decision = str(r.get("decision", "")).strip()
        if decision not in _ALL:
            raise ValueError(
                f"resolution #{i} ('{key}') decision '{decision}' not in {sorted(_ALL)}"
            )
        leaf = str(r.get("leaf") or "").strip() or None
        if decision == "leaf":
            if not leaf:
                raise ValueError(
                    f"resolution #{i} ('{key}') leaf decision requires a 'leaf'"
                )
            if valid_leaves is not None and leaf not in valid_leaves:
                raise ValueError(
                    f"resolution #{i} ('{key}') leaf '{leaf}' is not a valid COICOP leaf"
                )
        else:
            leaf = None
        conf = r.get("confidence")
        out.append(
            {
                "canonical_key": key,
                "decision": decision,
                "leaf": leaf,
                "confidence": float(conf) if conf is not None else None,
                "rationale": str(r.get("rationale") or ""),
                "resolver": str(r.get("resolver") or default_resolver),
            }
        )
    return out


def merge_resolution_sets(sets: list[list[dict]]) -> tuple[list[dict], list[dict]]:
    """Fold several parsed resolution lists into (applicable, escalated).

    A canonical_key that appears with conflicting (decision, leaf) across the
    sets is escalated rather than applied. Explicit ``escalate`` rows are also
    routed to the escalated bucket. Keys resolved identically (or by only one
    set) pass through to ``applicable`` (last writer wins on metadata).
    """
    by_key: dict[str, list[dict]] = {}
    for rows in sets:
        for r in rows:
            by_key.setdefault(r["canonical_key"], []).append(r)

    applicable: list[dict] = []
    escalated: list[dict] = []
    for key, rows in by_key.items():
        stances = {(r["decision"], r["leaf"]) for r in rows}
        has_escalate = any(r["decision"] == ESCALATE for r in rows)
        if has_escalate or len({s for s in stances if s[0] != ESCALATE}) > 1:
            escalated.append({**rows[-1], "reason": "cross-resolver-disagreement"})
            continue
        applicable.append(rows[-1])
    return applicable, escalated


def to_store_rows(resolutions: list[dict]) -> pd.DataFrame:
    """Shape applicable resolutions into a label_store.append-ready frame at
    tier T3_adjudicated. ``escalate`` rows are dropped (they are not decisions)."""
    rows = []
    for r in resolutions:
        if r["decision"] == ESCALATE:
            continue
        rows.append(
            {
                "canonical_key": r["canonical_key"],
                "leaf": r["leaf"] if r["decision"] == "leaf" else None,
                "decision": r["decision"],
                "tier": "T3_adjudicated",
                "confidence": r["confidence"],
                "witness_votes": {
                    "resolver": r["resolver"],
                    "rationale": r["rationale"],
                },
                "provenance": f"apply:{r['resolver']}",
            }
        )
    cols = [
        "canonical_key",
        "leaf",
        "decision",
        "tier",
        "confidence",
        "witness_votes",
        "provenance",
    ]
    return pd.DataFrame(rows, columns=cols)
