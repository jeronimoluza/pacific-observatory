"""One currency per `input_hash`, whatever order the raw rows arrive in.

`prepare` used to take the `"first"` currency of an `input_hash`'s rows. The row
order came from an unsorted directory listing, so the same raw tree prepared on
ext4 and on exFAT gave a different currency for every hash seen under more than
one currency (W42 panel36: 20,896 in bosnia, 1,675 in ukraine).

Rule: the currency on the most rows of the hash wins; a tie goes to the
lexically smallest code. Every hash with more than one currency is logged with
its counts so a person can review it.
"""

from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger(__name__)
SAMPLE = 5


def modal_currency(df: pd.DataFrame, log: bool = False) -> pd.Series:
    """Per row of `df`, the chosen currency of its `input_hash`."""
    cur = df["currency"].fillna("").astype(str)
    counts = (
        pd.DataFrame({"input_hash": df["input_hash"], "currency": cur})
        .groupby(["input_hash", "currency"], sort=False)
        .size()
        .reset_index(name="n")
        .sort_values(["input_hash", "n", "currency"], ascending=[True, False, True])
    )
    if log:
        mixed = counts[counts["input_hash"].duplicated(keep=False)]
        if not mixed.empty:
            hashes = mixed["input_hash"].drop_duplicates()
            sample = []
            for h in hashes.head(SAMPLE):
                rows = mixed.loc[mixed["input_hash"] == h, ["currency", "n"]]
                sample.append(
                    f"{h}: " + ",".join(f"{c}={n}" for c, n in rows.itertuples(index=False))
                )
            logger.info(
                "[prepare] %d input_hash with more than one currency"
                " (modal wins, tie lexical): %s",
                len(hashes),
                "; ".join(sample),
            )
    pick = counts.drop_duplicates("input_hash").set_index("input_hash")["currency"]
    return df["input_hash"].map(pick)
