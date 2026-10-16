"""How long a carried-forward price is shown after its observation.

Two kinds of source (``publication`` in the YAML):

- ``announcement``: the authority publishes only when the price changes
  (state-controlled prices). A price holds until the next observation with
  no cap while the source is alive -- its last collect without errors
  (``last_ok`` in ``data/fuel/_status/<region>.json``) is at most
  ``ALIVE_DAYS`` old; otherwise it holds until ``last_ok + ALIVE_DAYS``.
  Without any liveness record the scheduled cap applies.
- ``scheduled`` (default): the source publishes on a calendar, so a price
  is carried at most twice its cadence.
"""

from __future__ import annotations

import pandas as pd

CADENCE_DAYS = {
    "daily": 1,
    "weekly": 7,
    "biweekly": 14,
    "monthly": 31,
    "quarterly": 92,
    "yearly": 366,
    # No calendar: 2 x 92 = 184 days (the 90th-percentile gap of the
    # irregular sources is 32-185 days).
    "irregular": 92,
}
ALIVE_DAYS = 14


def carry_end(
    start: pd.Timestamp,
    next_start: pd.Timestamp | None,
    cadence: str,
    publication: str,
    last_ok: pd.Timestamp | None,
    today: pd.Timestamp,
) -> pd.Timestamp:
    """Last day a price observed on ``start`` is shown."""
    if publication == "announcement" and next_start is not None:
        end = next_start - pd.Timedelta(days=1)
    elif publication == "announcement" and last_ok is not None:
        alive = (today - last_ok).days <= ALIVE_DAYS
        end = today if alive else last_ok + pd.Timedelta(days=ALIVE_DAYS)
    else:
        end = start + pd.Timedelta(days=2 * CADENCE_DAYS[cadence] - 1)
        if next_start is not None:
            end = min(end, next_start - pd.Timedelta(days=1))
    return max(min(end, today), start)
