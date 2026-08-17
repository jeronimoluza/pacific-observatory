"""Rank gold rows by how likely their label is wrong.

The score is a transparent weighted sum of the boolean signals from
``signals.py``. It is deliberately not a fitted model: there is no ground truth
about which gold labels are wrong (that is the thing being bought), so anything
fitted here would be circular. A linear sum with named weights can be read,
argued with, and overridden.

Weights are a starting point, not a result. ``experiment.py`` reports which
signals actually separate OOF errors; re-weight from that evidence rather than
from intuition, and record the change in the run manifest.

The strongest weight goes to confident OOF disagreement, because a head that is
*sure* the gold is wrong is either finding a real error or exposing a
convention the gold applies inconsistently — both worth an adjudicator. The
weakest goes to plain original-labeler disagreement, which is already the signal
the adjudication pass acted on, so it is partly spent.
"""

from __future__ import annotations

import pandas as pd

from prices.enrich.gold_audit import SUSPECTS_FILE, ensure_run_dir, run_dir, signals

DEFAULT_WEIGHTS: dict[str, float] = {
    "oof_confidently_disagrees": 3.0,
    "oof_disagrees": 2.0,
    "neighbor_disagrees": 2.0,
    "dupe_conflict": 1.5,
    "confusion_pair": 1.0,
    "adjudicator_required": 1.0,
    "low_confidence": 1.0,
    "original_disagreement": 0.5,
}

ADJUDICATED_SOURCES = {"gate1_adjudicated", "adjudicated_opus"}


def _indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Boolean columns matching DEFAULT_WEIGHTS keys, one per signal."""
    ind = pd.DataFrame(index=df.index)
    for col in (
        "oof_confidently_disagrees",
        "oof_disagrees",
        "neighbor_disagrees",
        "dupe_conflict",
        "confusion_pair",
    ):
        ind[col] = df[col].fillna(False).astype(bool)

    ind["adjudicator_required"] = (
        df.get("label_source", pd.Series("", index=df.index))
        .fillna("")
        .isin(ADJUDICATED_SOURCES)
    )
    ind["low_confidence"] = (
        df.get("confidence", pd.Series("", index=df.index))
        .fillna("")
        .isin({"low", "medium"})
    )
    ind["original_disagreement"] = (
        df.get("disagreement_type", pd.Series("agree", index=df.index))
        .fillna("agree")
        .ne("agree")
    )
    return ind


def rank(run_id: str, weights: dict[str, float] | None = None) -> dict:
    """Write ``suspects.parquet``: every gold row with its signals, score and rank."""
    w = weights or DEFAULT_WEIGHTS
    df = signals.load(run_id)
    ind = _indicators(df)

    out = df.copy()
    for col in ind.columns:
        out[col] = ind[col]
    out["suspicion_score"] = sum(ind[c].astype(float) * wt for c, wt in w.items())
    out["reasons"] = [
        ",".join(c for c in ind.columns if row[c]) for _, row in ind.iterrows()
    ]

    out = out.sort_values("suspicion_score", ascending=False).reset_index(drop=True)
    out["suspicion_rank"] = out.index + 1
    out.to_parquet(ensure_run_dir(run_id) / SUSPECTS_FILE, index=False)

    scored = out["suspicion_score"]
    return {
        "run_id": run_id,
        "weights": w,
        "n_rows": int(len(out)),
        "n_any_signal": int((scored > 0).sum()),
        "score_quantiles": {
            q: float(scored.quantile(q)) for q in (0.5, 0.9, 0.95, 0.99)
        },
        "signal_counts": {c: int(ind[c].sum()) for c in ind.columns},
    }


def load(run_id: str) -> pd.DataFrame:
    return pd.read_parquet(run_dir(run_id) / SUSPECTS_FILE)


def top(run_id: str, n: int, division: str | None = None) -> pd.DataFrame:
    df = load(run_id)
    if division:
        df = df[df["division"] == division]
    return df[df["suspicion_score"] > 0].head(n)
