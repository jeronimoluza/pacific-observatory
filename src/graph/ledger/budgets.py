"""Per-source budgets and streaks derived from the run ledger.

Runs of a source, in time order (start, else the Monday of the week). A prices
``raw:<week>`` row is dropped when the same source has a collect-ledger row that week
(both describe the same run; the ledger has the real duration). BLOCKED rows are not runs.

Rule (written here so the number can be argued with):

- window = the last ``n`` runs with a duration and status DONE, ZERO or TIMEOUT
  (FAIL is usually a fast crash and would pull the budget down);
- p50, p95 = linear percentiles of duration_s in the window;
- budget_s = max(``floor_s``, p95 x ``margin``), rounded up to the minute;
- censored = the window has a TIMEOUT: the true duration is >= the cap, so p95 and the
  budget are lower bounds (for those, raise the cap, never lower it);
- budget_prev_s = the same rule without the last run; over_budget = the last run's
  duration > budget_prev_s (needs >= 2 earlier runs);
- zero_streak = consecutive most recent runs with new_rows == 0 (a run with unknown rows
  ends the count); new_zero_streak = zero_streak >= 2 and the source had rows before it,
  text only: a prices week with 0 raw rows is not a zero by itself (a fetcher without
  delta writes none); whether a prices source is in zero is
  ``graph.checks.raw_sources.zero_color``, read by ``silent_zeros`` and ``graph status``;
- stalled = the last run went ``stall_min`` minutes or more without progress (prices:
  Scrapy logstats with neither pages nor items growing; text: runner STUCK).
"""

from __future__ import annotations

import math

N = 8
MARGIN = 1.5
FLOOR_S = 60
STALL_MIN = 15
TIMED = {"DONE", "ZERO", "TIMEOUT"}


def runs_in_order(runs):
    import pandas as pd

    from graph.ledger.store import week_monday

    df = runs[runs["status"] != "BLOCKED"].copy()
    led = df[df["origin"] == "ledger"][["pipeline", "country", "source", "week"]].drop_duplicates()
    led["has_ledger"] = True
    df = df.merge(led, on=["pipeline", "country", "source", "week"], how="left")
    df = df[~((df["origin"] == "raw_items") & df["has_ledger"].eq(True))]
    monday = pd.to_datetime(df["week"].map(lambda w: week_monday(w) if isinstance(w, str) else None), utc=True)
    df["order_ts"] = df["start_utc"].fillna(monday)
    return df.sort_values(["pipeline", "country", "source", "order_ts", "run_id"]).drop(columns="has_ledger")


def _budget(durations: list[float], margin: float, floor_s: int):
    import numpy as np

    if not durations:
        return None, None, None
    p50, p95 = (float(np.percentile(durations, q)) for q in (50, 95))
    return p50, p95, max(floor_s, math.ceil(p95 * margin / 60) * 60)


def derive(runs, n: int = N, margin: float = MARGIN, floor_s: int = FLOOR_S, stall_min: int = STALL_MIN):
    import pandas as pd

    out = []
    for (pipeline, country, source), g in runs_in_order(runs).groupby(["pipeline", "country", "source"], sort=False):
        timed = g[g["status"].isin(TIMED) & g["duration_s"].notna()]
        win = timed.tail(n)
        p50, p95, budget = _budget(win["duration_s"].tolist(), margin, floor_s)
        prev = timed.iloc[:-1].tail(n)
        _, _, budget_prev = _budget(prev["duration_s"].tolist(), margin, floor_s) if len(prev) >= 2 else (None, None, None)
        streak = 0
        for v in reversed(g["new_rows"].tolist()):
            if pd.isna(v) or v != 0:
                break
            streak += 1
        before = g["new_rows"].iloc[: len(g) - streak]
        had_rows = bool((before.fillna(0) > 0).any())
        last = g.iloc[-1]
        last_dur = last["duration_s"]
        stall = last["max_stall_s"]
        out.append({
            "pipeline": pipeline, "region": last["region"], "country": country, "source": source,
            "n_runs": len(g), "n_window": len(win), "p50_s": p50, "p95_s": p95, "budget_s": budget,
            "margin": margin, "censored": bool((win["status"] == "TIMEOUT").any()),
            "n_timeout_window": int((win["status"] == "TIMEOUT").sum()),
            "budget_prev_s": budget_prev,
            "over_budget": bool(budget_prev is not None and pd.notna(last_dur) and last_dur > budget_prev),
            "zero_streak": streak, "had_rows_before": had_rows,
            "new_zero_streak": pipeline == "text" and streak >= 2 and had_rows,
            "last_run_id": last["run_id"], "last_status": last["status"],
            "last_rows": last["new_rows"], "last_duration_s": last_dur,
            "last_start_utc": last["start_utc"], "last_max_stall_s": stall,
            "stalled": bool(pd.notna(stall) and stall >= stall_min * 60),
            "first_week": g["week"].min(), "last_week": g["week"].max(),
        })
    df = pd.DataFrame(out)
    for c in ("n_runs", "n_window", "zero_streak", "n_timeout_window"):
        df[c] = df[c].astype("int64")
    df["last_rows"] = df["last_rows"].astype("Int64")
    return df


def silent_zeros(week: str, n: int = 4):
    """Prices silent zeros of ``week``, by ``graph.checks.raw_sources`` itself (one definition):
    its red ``cero silencioso`` findings, plus the fetchers without delta it holds yellow.
    It reads the week's ledgers with their ``_fullrun`` retries and the raw files on disk;
    the ledger's weekly rows alone miss the retries and the fetchers' observation dates."""
    import pandas as pd

    from graph.checks import raw_sources as R

    out = []
    for r in R.read(week, n=n):
        color = R.zero_color(r)
        if color:
            out.append({"country": r["country"], "source": r["source"], "color": color,
                        "baseline": r["baseline"], "last_obs": r["last_obs"], "scaffolding": r["scaffolding"]})
    return pd.DataFrame(out, columns=["country", "source", "color", "baseline", "last_obs", "scaffolding"])


def zero_runs(runs, last: int = 2):
    """Text sources with 0 new rows in each of the last ``last`` prod staged runs."""
    from graph.ledger.text import RUN_DIR

    t = runs[(runs["pipeline"] == "text") & runs["new_rows"].notna()]
    ids = sorted(r for r in t["run_id"].unique() if RUN_DIR.match(r))[-last:]
    t = t[t["run_id"].isin(ids)]
    g = t.groupby(["region", "country", "source"]).agg(n=("run_id", "nunique"), rows=("new_rows", "sum"),
                                                      statuses=("status", lambda s: ",".join(sorted(set(s)))))
    return ids, g[(g["n"] == len(ids)) & (g["rows"] == 0)].reset_index()
