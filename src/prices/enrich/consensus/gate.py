"""Consensus gate (W4.2) — weigh a name's witness Votes into an accept
(label, tier, confidence) or a conflict record.

The tiers and thresholds live in ``static/consensus_policy.yaml`` (never
hardcoded — they are recalibrated against gold v5). ``decide`` is a pure
function over a list of Votes so it is fully unit-testable with synthetic
votes, no backend required. ``run`` glues the witnesses + gate over a corpus
and returns accepted rows (label_store-shaped) plus conflict rows (queue-shaped).
"""

from __future__ import annotations

import json
from dataclasses import dataclass

import pandas as pd
import yaml

from prices.enrich.consensus import POLICY_PATH, REJECT_LABELS
from prices.enrich.consensus.witnesses import Vote

_MUST_KNN_MODEL_CASCADE = {"model", "knn", "cascade"}
_PRIMARY = {"leaf", "reject"}

_DECISION = {"__EXCLUDE__": "exclude", "__OTHER_FORM__": "other_form"}


@dataclass(frozen=True)
class GateResult:
    status: str  # "accept" | "conflict" | "abstain"
    label: str | None
    decision: str | None  # leaf | exclude | other_form (label_store) — accept only
    tier: str | None  # T0_memo | T0_lexicon | T1_consensus | T2_model
    confidence: float
    votes_json: str
    reason: str


def load_policy(path=POLICY_PATH) -> dict:
    return yaml.safe_load(open(path, encoding="utf-8"))


def _decision_for(label: str) -> str:
    return _DECISION.get(label, "leaf")


def _serialize(votes) -> str:
    return json.dumps(
        [
            {
                "w": v.witness,
                "label": v.label,
                "kind": v.kind,
                "strength": round(v.strength, 4),
            }
            for v in votes
        ],
        ensure_ascii=False,
        sort_keys=True,
    )


def _t2_conf(policy: dict, script: str) -> float | None:
    base = policy["tiers"]["T2"].get("conf_model")
    ov = policy.get("per_script_overrides", {}).get(script, {})
    if "T2_conf_model" in ov:
        return ov["T2_conf_model"]  # may be None -> disables model-only accepts
    return base


def decide(votes: list[Vote], script: str, policy: dict) -> GateResult:
    blob = _serialize(votes)
    primary = [v for v in votes if v.kind in _PRIMARY]
    if not primary:
        return GateResult("abstain", None, None, None, 0.0, blob, "no-primary-witness")

    by_label: dict[str, dict[str, Vote]] = {}
    for v in primary:
        by_label.setdefault(v.label, {})[v.witness] = v
    labels = list(by_label)

    memo = next((v for v in primary if v.witness == "memo"), None)
    if memo is not None:
        return GateResult(
            "accept",
            memo.label,
            _decision_for(memo.label),
            "T0_memo",
            float(memo.strength),
            blob,
            "memo-authority",
        )

    # reject stance (calibrated vs gold v5): the v0 model predicts __EXCLUDE__/
    # __OTHER_FORM__ for out-of-vocab items, and lexicon/cascade share that GREEN
    # blind spot, so reject-consensus is corroborated-but-wrong ~83% of the time.
    # With reject_consensus == "queue" we drop non-memo reject votes here, letting a
    # surviving leaf win and routing reject-only rows to the conflict queue for
    # adjudication rather than auto-writing a false reject.
    if policy.get("reject_consensus", "queue") == "queue":
        primary = [v for v in primary if v.label not in REJECT_LABELS]
        if not primary:
            return GateResult(
                "conflict", None, None, None, 0.0, blob, "reject-consensus-queued"
            )
        by_label = {}
        for v in primary:
            by_label.setdefault(v.label, {})[v.witness] = v
        labels = list(by_label)

    conf = policy["conflict"]
    if len(labels) >= conf.get("min_disagreeing", 2):
        return GateResult(
            "conflict", None, None, None, 0.0, blob, "witness-disagreement"
        )

    label = labels[0]
    agree = by_label[label]
    best_strength = max(v.strength for v in agree.values())
    if best_strength < conf.get("or_conf_below", 0.50) and label not in REJECT_LABELS:
        # sole weak proposer — send to the queue rather than auto-accept
        if not (len(agree) == 1 and "lexicon" in agree):
            return GateResult("conflict", None, None, None, 0.0, blob, "low-confidence")

    # T1 — >=N agreeing incl one of {model,knn,cascade} (model gated by conf)
    t1 = policy["tiers"]["T1"]
    strong = {
        w
        for w, v in agree.items()
        if w != "model" or v.strength >= t1.get("conf_model", 0.70)
    }
    anchor = strong & _MUST_KNN_MODEL_CASCADE
    if len(strong) >= t1.get("min_agreeing", 2) and anchor:
        c = sum(agree[w].strength for w in strong) / len(strong)
        return GateResult(
            "accept",
            label,
            _decision_for(label),
            "T1_consensus",
            float(c),
            blob,
            "consensus:" + "+".join(sorted(strong)),
        )

    # T2 — model-only high confidence (per-script gated)
    t2c = _t2_conf(policy, script)
    mv = agree.get("model")
    if t2c is not None and mv is not None and mv.strength >= t2c:
        return GateResult(
            "accept",
            label,
            _decision_for(label),
            "T2_model",
            float(mv.strength),
            blob,
            "model-high-conf",
        )

    # T0 — lexicon-only accept (min_votes 1), when it is the sole consensus label
    lv = agree.get("lexicon")
    if lv is not None:
        return GateResult(
            "accept",
            label,
            _decision_for(label),
            "T0_lexicon",
            float(lv.strength),
            blob,
            "lexicon-only",
        )

    return GateResult("conflict", None, None, None, 0.0, blob, "insufficient-support")


def result_frame(
    rows: list[tuple[str, GateResult]],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split (canonical_key, GateResult) rows into (accepts, conflicts) frames.
    `accepts` is label_store-shaped; `conflicts` is queue-shaped."""
    acc, con = [], []
    for key, r in rows:
        if r.status == "accept":
            acc.append(
                {
                    "canonical_key": key,
                    "leaf": r.label if r.decision == "leaf" else None,
                    "decision": r.decision,
                    "tier": r.tier,
                    "confidence": r.confidence,
                    "witness_votes": r.votes_json,
                    "provenance": f"consensus:{r.reason}",
                }
            )
        elif r.status == "conflict":
            con.append(
                {
                    "canonical_key": key,
                    "witness_votes": r.votes_json,
                    "reason": r.reason,
                }
            )
    acc_cols = [
        "canonical_key",
        "leaf",
        "decision",
        "tier",
        "confidence",
        "witness_votes",
        "provenance",
    ]
    accepts = pd.DataFrame(acc) if acc else pd.DataFrame(columns=acc_cols)
    conflicts = (
        pd.DataFrame(con)
        if con
        else pd.DataFrame(columns=["canonical_key", "witness_votes", "reason"])
    )
    return accepts, conflicts
