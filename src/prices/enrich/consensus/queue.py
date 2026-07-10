"""Conflict queue (W4.3) — rank gate conflicts so human/model verdict effort
lands where it moves the most price series.

score = w_obs·log1p(obs_count) + w_leaf_gap·leaf_gap + w_severity·severity
  obs_count    observations behind the contested name (from the corpus)
  severity     number of distinct labels the witnesses proposed
  leaf_gap     number of distinct COICOP divisions among those labels
               (cross-division disagreement is worse than sibling-leaf noise)

`prices queue export --top N` slices the ranked parquet into an agent-ready CSV
whose schema is deliberately plain so slices can go to Claude agents or codex.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pandas as pd

from prices.enrich.consensus import CONFLICTS_PARQUET, gate
from prices.enrich.keys import norm_key

QUEUE_COLS = [
    "canonical_key",
    "example_name",
    "obs_count",
    "severity",
    "leaf_gap",
    "score",
    "competing_votes",
    "reason",
]


def _labels(votes_json: str) -> list[str]:
    try:
        vs = json.loads(votes_json)
    except Exception:
        return []
    return [
        v["label"] for v in vs if v.get("kind") in ("leaf", "reject") and v.get("label")
    ]


def _severity(votes_json: str) -> int:
    return len(set(_labels(votes_json)))


def _leaf_gap(votes_json: str) -> int:
    divs = {lbl[:2] for lbl in _labels(votes_json) if lbl[:2].isdigit()}
    return len(divs)


def _competing(votes_json: str) -> str:
    try:
        vs = json.loads(votes_json)
    except Exception:
        return ""
    parts = [f"{v['w']}={v['label']}({v['strength']})" for v in vs if v.get("label")]
    return "; ".join(parts)


def build_queue(
    conflicts: pd.DataFrame,
    corpus: pd.DataFrame,
    name_col: str,
    obs_col: str = "n_observations",
    policy: dict | None = None,
    path=CONFLICTS_PARQUET,
) -> pd.DataFrame:
    policy = policy or gate.load_policy()
    r = policy.get("queue_ranking", {})
    w_obs, w_gap, w_sev = (
        r.get("w_obs", 1.0),
        r.get("w_leaf_gap", 0.5),
        r.get("w_severity", 0.3),
    )

    obs = pd.Series(0, index=[], dtype="int64")
    example: dict[str, str] = {}
    if not corpus.empty:
        c = corpus.copy()
        c["_k"] = c[name_col].map(norm_key)
        if obs_col in c.columns:
            obs = c.groupby("_k")[obs_col].sum()
        for k, nm in zip(c["_k"], c[name_col]):
            example.setdefault(k, str(nm))

    rows = []
    for rec in conflicts.itertuples(index=False):
        vj = rec.witness_votes
        key = rec.canonical_key
        oc = int(obs.get(key, 0))
        sev = _severity(vj)
        gap = _leaf_gap(vj)
        score = w_obs * math.log1p(oc) + w_gap * gap + w_sev * sev
        rows.append(
            {
                "canonical_key": key,
                "example_name": example.get(key, key),
                "obs_count": oc,
                "severity": sev,
                "leaf_gap": gap,
                "score": round(float(score), 4),
                "competing_votes": _competing(vj),
                "reason": getattr(rec, "reason", ""),
            }
        )

    q = pd.DataFrame(rows, columns=QUEUE_COLS)
    if not q.empty:
        q = q.sort_values("score", ascending=False).reset_index(drop=True)
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    q.to_parquet(p, index=False)
    return q


def load_queue(path=CONFLICTS_PARQUET) -> pd.DataFrame:
    p = Path(path)
    if not p.exists():
        return pd.DataFrame(columns=QUEUE_COLS)
    return pd.read_parquet(p)


def export_slice(top: int, out_path, path=CONFLICTS_PARQUET) -> pd.DataFrame:
    q = load_queue(path).head(top)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    q.to_csv(out, index=False)
    return q
