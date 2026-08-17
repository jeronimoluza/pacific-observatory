"""Group suspect rows into adjudication batches by the dispute they raise.

Rank-ordered batches mix unrelated questions: one line asks whether a lipstick
is cosmetics or personal care, the next whether a cracker is a biscuit or a
savoury snack. The adjudicator re-reads a fresh definition block every line and
answers each question once, so nothing accumulates.

Grouping by **dispute pair** — the unordered ``(gold, oof_pred)`` couple —
turns the job into one binary question asked forty times. The definitions load
once per batch, the answers become mutually comparable, and a systematic
convention error shows up as a systematic flip rather than forty independent
coin tosses.

The measured shape of the division-01 both-disagree set: 3,403 rows over 1,120
pairs, 75% of rows sharing a pair with at least one other row, the largest pair
98 rows. Concentrated enough for grouping to pay, too dispersed for a handful of
hand-written convention rulings to cover.

**Controls.** Every batch is seeded with rows whose gold label nothing disputes,
carrying the same two candidates as the real rows and indistinguishable from
them in the exported JSONL. An adjudicator that is reasoning about the product
leaves them alone; one that is echoing whichever candidate looks model-endorsed
flips them. Without this the round can launder the classifier's own opinion back
into gold, and the retrain would look like an improvement it isn't.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

DEFAULT_BATCH_SIZE = 40
CONTROL_SHARE = 0.05
MIN_CONTROLS = 2

# Fixed so a re-export of the same run yields byte-identical batches: the
# candidate shuffle and the control draw must not drift between invocations.
SEED = 20260817


def dispute_pair(code: object, pred: object) -> tuple[str, str] | None:
    """The unordered couple of codes in dispute, or None if there is no dispute."""
    if not isinstance(code, str) or not isinstance(pred, str):
        return None
    if not code or not pred or code == pred:
        return None
    a, b = sorted((code, pred))
    return (a, b)


def control_pool(suspects: pd.DataFrame) -> pd.DataFrame:
    """Rows no signal disputes: unanimous neighbourhood and the head agrees.

    Deliberately stricter than ``suspicion_score <= 0`` alone. A row with no
    score but an impure neighbourhood is a weak control — flipping it would be
    defensible, so it cannot serve as evidence of an anchored adjudicator."""
    ok = suspects["oof_correct"].astype("boolean").fillna(False)
    pure = suspects["purity_at_k"].fillna(0.0) >= 1.0
    quiet = suspects["suspicion_score"] <= 0
    return suspects[ok & pure & quiet]


def _draw_controls(
    pool: pd.DataFrame,
    pair: tuple[str, str],
    n: int,
    used: set,
    rng: np.random.Generator,
) -> pd.DataFrame:
    """Undisputed rows whose own code is one of the pair, so they blend in.

    A control drawn from an unrelated code would stand out the moment the
    adjudicator read the product name against the two candidates offered."""
    cand = pool[pool["code"].isin(pair) & ~pool["gold_row_id"].isin(used)]
    if cand.empty or n <= 0:
        return cand.head(0)
    take = min(n, len(cand))
    pick = rng.choice(len(cand), size=take, replace=False)
    return cand.iloc[np.sort(pick)]


def plan(
    picked: pd.DataFrame,
    pool: pd.DataFrame,
    batch_size: int = DEFAULT_BATCH_SIZE,
    control_share: float = CONTROL_SHARE,
    max_pairs: int | None = None,
) -> list[dict]:
    """Split `picked` into per-pair batches, each seeded with controls.

    Returns one dict per batch: the pair, the rows to export (real + control,
    interleaved by the shuffle), and the control ids kept out of the JSONL so
    the flip rate stays measurable after ingest."""
    rng = np.random.default_rng(SEED)

    work = picked.copy()
    work["dispute_pair"] = [
        dispute_pair(c, p) for c, p in zip(work["code"], work["oof_pred"])
    ]
    work = work[work["dispute_pair"].notna()].copy()
    work["pair_key"] = ["|".join(p) for p in work["dispute_pair"]]

    order = work["pair_key"].value_counts()
    if max_pairs is not None:
        order = order.head(max_pairs)

    batches: list[dict] = []
    used: set = set()

    for pair_key in order.index:
        grp = work[work["pair_key"] == pair_key]
        pair = tuple(pair_key.split("|"))
        # Split evenly rather than filling batches to `batch_size` and leaving a
        # runt: a 54-row group becomes 27+27, not 40+14. A two-row trailing batch
        # would carry more controls than real rows, which is both wasted labeling
        # and a tell that the controls are there.
        n_chunks = max(1, -(-len(grp) // batch_size))
        base, rem = divmod(len(grp), n_chunks)
        sizes = [base + 1] * rem + [base] * (n_chunks - rem)
        start = 0
        for size in sizes:
            chunk, start = grp.iloc[start : start + size], start + size
            if not len(chunk):
                continue
            n_ctrl = max(MIN_CONTROLS, round(control_share * len(chunk)))
            ctrl = _draw_controls(pool, pair, n_ctrl, used, rng)
            used.update(ctrl["gold_row_id"].tolist())

            rows = pd.concat([chunk, ctrl], ignore_index=True)
            rows = rows.iloc[rng.permutation(len(rows))].reset_index(drop=True)

            batches.append(
                {
                    "pair": list(pair),
                    "rows": rows,
                    "n_real": int(len(chunk)),
                    "control_row_ids": ctrl["gold_row_id"].tolist(),
                    "control_expected": dict(
                        zip(ctrl["gold_row_id"], ctrl["code"], strict=False)
                    ),
                }
            )

    return batches
