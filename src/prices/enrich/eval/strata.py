"""Per-stratum reporting for a trained head: coverage@98 and precision@top-60%.

Two metrics, deliberately, because they answer different questions and one of
them is unusable at small n:

  coverage@98        TP / N once tau is set so accepted precision hits 0.98. It
                     is the production number, but it has a ~+/-11pt CI on a few
                     thousand rows, so it is meaningless per-language for all but
                     the largest groups.
  precision@top-60%  precision among the highest-scoring 60% of rows. No
                     threshold search, so it is stable at small n and is the
                     metric to compare strata on.

Strata are (country | tail bucket), where the tail is grouped by the product
LANGUAGE from `country_product_languages.yaml` -- the head reads text, so the
text's distribution is language-shaped, not geography-shaped. Pooling Senegal
with Mali under `fr` pools interchangeable name distributions; pooling them by
region would pool Devanagari with Bengali.

`tau` is GLOBAL in every breakdown. A per-stratum tau would report the coverage
each stratum could get if it had its own threshold, which production does not
give it; the question here is what each stratum gets at the one operating point
that actually ships.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

TOP_FRAC = 0.60


def precision_at_top(score: np.ndarray, correct: np.ndarray,
                     frac: float = TOP_FRAC) -> tuple[float, int]:
    """Precision among the highest-scoring `frac` of rows, and how many that is.

    Ties at the boundary are cut arbitrarily by argsort order. That is fine here:
    the cut is a fixed COUNT, not a probability threshold, so a tie block cannot
    move the denominator the way it can in `choose_tau`.
    """
    n = len(score)
    if n == 0:
        return float("nan"), 0
    k = max(1, int(round(n * frac)))
    top = np.argsort(-score, kind="stable")[:k]
    return float(correct[top].mean()), k


def language_of(country: str, langmap: dict) -> str:
    """Primary product language, or `mix:<dominant>` for the multilingual ones.

    `primary` is null whenever no language clears 0.70, which is 42 countries.
    Collapsing all of those into one MIXED bucket would hide real structure, so
    they are labelled by their heaviest weighted language instead.
    """
    e = langmap.get(country) or {}
    p = e.get("primary")
    if p:
        return str(p)
    langs = e.get("languages") or {}
    return f"mix:{max(langs, key=langs.get)}" if langs else "UNKNOWN"


def build_strata(country: pd.Series, langmap: dict, floor: int = 500) -> pd.Series:
    """Country when it carries >= `floor` rows, else a per-language tail bucket."""
    counts = country.value_counts()
    head = set(counts[counts >= floor].index)
    return pd.Series(
        [c if c in head else "TAIL:" + language_of(c, langmap) for c in country],
        index=country.index,
    )


def _block(score, correct, accepted, label) -> dict:
    n = len(correct)
    fired = int(accepted.sum())
    tp = int((accepted & correct).sum())
    p60, k = precision_at_top(score, correct)
    return {
        "stratum": label,
        "n": n,
        "head_acc": round(float(correct.mean()), 4) if n else float("nan"),
        "fired": fired,
        "precision": round(tp / fired, 4) if fired else float("nan"),
        "coverage": round(tp / n, 4) if n else float("nan"),
        "prec_top60": round(p60, 4),
        "n_top60": k,
    }


def report(df: pd.DataFrame, by: str) -> pd.DataFrame:
    """Per-group metrics at the GLOBAL tau already encoded in `df.accepted`."""
    rows = [
        _block(g["gate"].to_numpy(), g["correct"].to_numpy(),
               g["accepted"].to_numpy(), key)
        for key, g in df.groupby(by, sort=False)
    ]
    return pd.DataFrame(rows).sort_values("n", ascending=False).reset_index(drop=True)


def overall(df: pd.DataFrame) -> dict:
    return _block(df["gate"].to_numpy(), df["correct"].to_numpy(),
                  df["accepted"].to_numpy(), "OVERALL")
