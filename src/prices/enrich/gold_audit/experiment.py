"""The free experiment: is the neighbourhood signal worth targeting on?

Before buying any LLM adjudication, answer one question using only what is
already on disk:

    Are gold rows whose label disagrees with their local embedding
    neighbourhood disproportionately responsible for out-of-fold errors?

If yes, ``neighbor_disagrees`` is a cheap targeting signal and paid
re-adjudication can be aimed with it. If no, the money should go elsewhere and
this scaffold has cost nothing but an afternoon.

Three outputs, all descriptive — no model is fit here:

* a 2x2 of ``neighbor_disagrees`` x ``oof_disagrees`` with lift and the share of
  all OOF errors the flagged rows account for
* OOF error rate per ``purity_at_k`` decile, plus whether that rate falls
  monotonically as purity rises
* the same 2x2 for the original-labeler disagreement flag, so the new signal can
  be compared against the one the labeling process already produced

Rows without an OOF prediction are excluded from every table; the counts report
how many those were so the denominator stays honest.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from prices.enrich.gold_audit import EXPERIMENT_FILE, ensure_run_dir, oof, signals

DECILES = 10


def _rate(mask: pd.Series, errs: pd.Series) -> float:
    n = int(mask.sum())
    return float(errs[mask].mean()) if n else float("nan")


def _two_by_two(flag: pd.Series, errs: pd.Series) -> dict:
    """Error rate with and without the flag, plus lift and error recall."""
    flagged, unflagged = flag.fillna(False), ~flag.fillna(False)
    r_flag, r_base = _rate(flagged, errs), _rate(unflagged, errs)
    n_errs = int(errs.sum())
    return {
        "n_flagged": int(flagged.sum()),
        "n_unflagged": int(unflagged.sum()),
        "err_rate_flagged": r_flag,
        "err_rate_unflagged": r_base,
        "lift": float(r_flag / r_base) if r_base else float("nan"),
        "errors_captured": int(errs[flagged].sum()),
        "share_of_all_errors": float(errs[flagged].sum() / n_errs) if n_errs else 0.0,
        "share_of_corpus_flagged": float(flagged.mean()) if len(flag) else 0.0,
    }


def _purity_deciles(purity: pd.Series, errs: pd.Series) -> dict:
    """OOF error rate by purity decile, and whether it declines monotonically."""
    ok = purity.notna()
    if ok.sum() < DECILES:
        return {"bins": [], "monotonic_decreasing": None}
    bins = pd.qcut(purity[ok], DECILES, labels=False, duplicates="drop")
    rates = errs[ok].groupby(bins).mean()
    counts = errs[ok].groupby(bins).size()
    seq = rates.to_numpy(dtype=float)
    return {
        "bins": [
            {
                "decile": int(b),
                "purity_min": float(purity[ok][bins == b].min()),
                "purity_max": float(purity[ok][bins == b].max()),
                "n": int(counts.loc[b]),
                "err_rate": float(rates.loc[b]),
            }
            for b in rates.index
        ],
        "monotonic_decreasing": bool(np.all(np.diff(seq) <= 0)),
        "spread": float(seq[0] - seq[-1]) if len(seq) else float("nan"),
    }


def run(run_id: str) -> dict:
    df = signals.load(run_id)
    scored = df[df["oof_status"] == oof.STATUS_OK].copy()
    errs = scored["oof_disagrees"].astype(bool)

    original_disagreement = (
        scored["disagreement_type"].fillna("agree").ne("agree")
        if "disagreement_type" in scored.columns
        else pd.Series(False, index=scored.index)
    )

    result = {
        "run_id": run_id,
        "n_gold": int(len(df)),
        "n_oof_scored": int(len(scored)),
        "n_oof_unscored": int(len(df) - len(scored)),
        "n_oof_errors": int(errs.sum()),
        "neighbor_disagrees": _two_by_two(scored["neighbor_disagrees"], errs),
        "original_labeler_disagreed": _two_by_two(original_disagreement, errs),
        "dupe_conflict": _two_by_two(scored["dupe_conflict"], errs),
        "purity_deciles": _purity_deciles(scored["purity_at_k"], errs),
    }

    path = ensure_run_dir(run_id) / EXPERIMENT_FILE
    path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def format_report(result: dict) -> str:
    """Human-readable summary for the CLI."""
    lines = [
        f"gold rows              {result['n_gold']}",
        f"  with OOF prediction  {result['n_oof_scored']}",
        f"  without              {result['n_oof_unscored']}",
        f"  OOF errors           {result['n_oof_errors']}",
        "",
        f"{'signal':<28}{'flagged':>9}{'err%':>8}{'base%':>8}{'lift':>7}{'errs caught':>13}",
    ]
    for key in ("neighbor_disagrees", "original_labeler_disagreed", "dupe_conflict"):
        s = result[key]
        lines.append(
            f"{key:<28}{s['n_flagged']:>9}"
            f"{100 * s['err_rate_flagged']:>8.1f}"
            f"{100 * s['err_rate_unflagged']:>8.1f}"
            f"{s['lift']:>7.2f}"
            f"{100 * s['share_of_all_errors']:>12.1f}%"
        )
    dec = result["purity_deciles"]
    lines += ["", f"purity monotone decreasing: {dec['monotonic_decreasing']}"]
    for b in dec["bins"]:
        lines.append(
            f"  decile {b['decile']:>2}  purity {b['purity_min']:.2f}-{b['purity_max']:.2f}"
            f"  n={b['n']:>6}  err={100 * b['err_rate']:.1f}%"
        )
    return "\n".join(lines)
