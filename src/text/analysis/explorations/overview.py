"""Overview data for the dashboard's first tab: subtopic bursts this week.

Per unit (region, subregions, countries), the subtopics (groups) bursting
this week, with:

- Burst flag: the rule of ``narratives.py`` per country (pooled weekly counts,
  >= 2.5x expected from the trailing 26-week share, >= 5 articles, Poisson
  p < 1e-4). A region or subregion row is a group bursting in >= 1 of its
  countries.
- Ratio vs usual: the weekly Baker index the build writes to
  ``weekly/baker.parquet`` (``src/text/analysis/baker.py``: plain mean of
  per-source shares over their 2024 std, over the source panel; regions and
  subregions combine their countries as Baker's European EPU). Ratio = index
  this week / its mean over a comparison period (2024, the 52, 26 or 8 weeks
  before).
- N = articles mentioning the group this week. The dashboard ranks by
  N - N / ratio (articles above a usual week).
- Badge: new, peaked k weeks ago, k weeks rising, k-th week; fading rows
  (stopped bursting in the last ``FADE`` weeks) are listed apart.
- Persistence: weeks in a row (ending this week) where the ``SMOOTH``-week
  mean of Z is above ``ELEVATED`` times its 2024 mean. A group elevated for
  ``MIN_ELEVATED`` weeks with >= ``BURST_MIN`` articles this week is listed
  even when not bursting (a long crisis stops bursting once it is the usual).
- A group none of whose articles this week come from a panel source has no
  ratio (``u``): Baker leaves the other sources out.

Heartbeat (``beat`` per unit): the last ``BEAT_DAYS`` UTC days, ending
today, of daily articles and group counts (masked days null), each group's
usual weekly count per comparison period, and its importance in the last
``FADE`` + 1 weeks (bursting, persistent or both). The dashboard computes the
7-day states (Pressing, Came Back, Gone quiet, pace) from the browser clock.

Days with suspect source dumps are dropped from the counts as in
``weekly.py``. Reads each country's ``daily/`` files and every unit's
``weekly/baker.parquet`` (a full ``text build --region <r> --daily-history``,
aggregates included). Writes
``outputs/text/<region>/overview.json``, read by ``small_dashboard_concepts.py``.

Run: python src/text/analysis/explorations/overview.py [--region ssa]
"""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timezone

import numpy as np
import pandas as pd

from lead_lag import OUT
from narratives import BURST_MIN, bursts
from weekly import MASK_SHARE, masked_days, weekly

BASE = ("2024-01-01", "2024-12-31")
PERIODS = ("2024", "52", "26", "8")  # comparison windows, weeks before this one
FADE = 3  # weeks a stopped burst stays listed as fading
TOP_CONCEPTS = 3
ELEVATED = 1.5  # x the 2024 level
SMOOTH = 4  # weeks averaged before comparing with 2024
MIN_ELEVATED = 8  # weeks in a row for a group to count as persistent
BEAT_DAYS = 21  # 7-day window + the 14 days before it (Came Back)
HISTORY = 10  # 2024 articles for a group to "come back"


def last_week(today: date) -> pd.Timestamp:
    last = pd.Timestamp(today) - pd.Timedelta(days=1)
    return last - pd.Timedelta(days=(last.dayofweek + 1) % 7)  # back to Sunday


def week_end(d: pd.Series) -> pd.Series:
    return d + pd.to_timedelta((6 - d.dt.dayofweek) % 7, unit="D")


def country_numbers(cdir, weeks: pd.DatetimeIndex, days: pd.DatetimeIndex) -> dict:
    """Weekly and daily articles and term counts (periods x terms) for a country.

    Daily values on masked days are NaN.
    """
    d = cdir / "daily"
    sources = pd.read_parquet(d / "sources_daily.parquet")
    bad = masked_days(sources)
    drop = set(bad[bad > MASK_SHARE].index)
    sources = sources[~sources.date.isin(drop)]
    A = (
        sources.groupby(week_end(sources.date))
        .A_total.sum()
        .reindex(weeks, fill_value=0)
    )
    t = pd.read_parquet(d / "sources_terms_daily.parquet")
    t = t[~t.date.isin(drop)]
    counts = (
        t.groupby([week_end(t.date), "term"], observed=True)["count"]
        .sum()
        .unstack(fill_value=0)
        .reindex(weeks, fill_value=0)
    )
    daily = (
        t[t.date.isin(days)]
        .groupby(["date", "term"], observed=True)["count"]
        .sum()
        .unstack(fill_value=0)
        .reindex(days, fill_value=0)
    )
    for c in (counts, daily):
        c.columns = c.columns.astype(str).str.replace(
            r"^(group|concept)_(.*)_A_count$", r"\2", regex=True
        )
    dA = sources.groupby("date").A_total.sum().reindex(days, fill_value=0)
    masked = days.isin(list(drop))
    dA[masked] = np.nan
    daily[masked] = np.nan
    return {"articles": A, "counts": counts, "d_articles": dA, "d_counts": daily}


def add(parts: list[dict]) -> dict:
    out = parts[0]
    for p in parts[1:]:
        out = {k: out[k].add(p[k], fill_value=0) for k in out}
    return out


def baker_index(unit_dir, weeks: pd.DatetimeIndex) -> pd.DataFrame:
    """The unit's weekly Baker index of groups (weeks x groups), from the build."""
    Z = pd.read_parquet(unit_dir / "weekly" / "baker.parquet")
    Z = Z[[c for c in Z.columns if c.startswith("group_")]]
    Z.columns = Z.columns.str.removeprefix("group_")
    return Z.reindex(weeks)


def ratios(Z: pd.DataFrame, groups: list[str]) -> dict[str, list]:
    """Ratio of this week's Z to the mean Z of each comparison period."""
    Z = Z.reindex(columns=groups, fill_value=0)
    now, past = Z.iloc[-1], Z.iloc[:-1]
    means = [past.loc[BASE[0] : BASE[1]].mean()] + [
        past.iloc[-int(p) :].mean() for p in PERIODS[1:]
    ]
    out = {}
    for g in groups:
        r = [now[g] / m[g] if m[g] > 0 else np.nan for m in means]
        out[g] = [round(float(x), 2) if np.isfinite(x) else None for x in r]
    return out


def elevated_weeks(Z: pd.DataFrame, end: int = 0) -> pd.Series:
    """Weeks in a row, ending ``end`` weeks ago, with smoothed Z above ELEVATED x 2024."""
    base = Z.loc[BASE[0] : BASE[1]].mean()
    up = (
        Z.rolling(SMOOTH, min_periods=SMOOTH).mean().gt(ELEVATED * base.where(base > 0))
    )
    U = up.to_numpy(dtype=bool)[::-1][end:]
    run = np.where(U.all(axis=0), len(U), np.argmax(~U, axis=0))
    return pd.Series(run, index=Z.columns)


def usual_articles(A: pd.Series) -> list[float]:
    past = A.iloc[:-1]
    return [round(float(past.loc[BASE[0] : BASE[1]].mean()), 1)] + [
        round(float(past.iloc[-int(p) :].mean()), 1) for p in PERIODS[1:]
    ]


def _num(x) -> float | None:
    return None if pd.isna(x) else round(float(x), 1)


def beat(num: dict, F: pd.DataFrame, Z: pd.DataFrame, groups: set[str]) -> dict:
    """Heartbeat inputs of a unit: daily counts of the last BEAT_DAYS days.

    Groups listed: mentioned in those days or important (bursting or
    persistent in the last FADE + 1 weeks; "bp" when both).
    """
    burst = set(F.columns[F.iloc[-1 - FADE :].any().to_numpy()])
    runs = [elevated_weeks(Z, k) for k in range(FADE + 1)]
    run = pd.concat(runs, axis=1).max(axis=1)
    persistent = set(run.index[run >= MIN_ELEVATED])
    D = num["d_counts"]
    mentioned = set(D.columns[D.fillna(0).sum() > 0])
    W = num["counts"]
    h2024 = W.loc[BASE[0] : BASE[1]].sum()
    out = {}
    for g in sorted((mentioned | burst | persistent) & groups):
        imp = ("b" if g in burst else "") + ("p" if g in persistent else "")
        d = D[g] if g in D else num["d_articles"] * 0  # zeros, masked days kept
        row = {
            "d": [None if pd.isna(x) else int(x) for x in d],
            "u": usual_articles(W[g]) if g in W else [0.0] * len(PERIODS),
        }
        if imp:
            row["i"] = imp
        if h2024.get(g, 0) >= HISTORY:
            row["h"] = 1
        out[g] = row
    return {
        "a": [_num(x) for x in num["d_articles"]],
        "ua": usual_articles(num["articles"]),
        "g": out,
    }


def badge(F: np.ndarray, N: np.ndarray) -> list:
    """Status of a group from its burst flags F and counts N (last = this week)."""
    if not F[-1]:
        k = int(np.flatnonzero(F[::-1])[0])
        return ["fade", k]
    back = np.flatnonzero(~F[::-1])
    run = int(back[0]) if len(back) else len(F)
    if run == 1:
        return ["new"]
    peak = int(np.argmax(N[-run:][::-1]))  # weeks ago; ties go to the latest
    if peak > 0:
        return ["peak", peak]
    up = np.flatnonzero(~(np.diff(N[-run:]) > 0)[::-1])
    rising = int(up[0]) if len(up) else run - 1
    return ["rise", rising] if rising >= 2 else ["wk", run]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--region", default="ssa")
    args = ap.parse_args()

    schema = json.loads((OUT / "dashboard_data" / "keywords_schema.json").read_text())
    parent, label, concepts, clabel = {}, {}, {}, {}
    for h in schema["headings"].values():
        for gid, g in h["groups"].items():
            parent[gid] = g.get("parent")
            label[gid] = f"{h['label']} · {g['label']}"
        for cid, c in h["concepts"].items():
            concepts.setdefault(c["group"], []).append(cid)
            clabel[cid] = c["label"]

    def ancestors(g):
        out = set()
        while parent.get(g):
            g = parent[g]
            out.add(g)
        return out

    last = last_week(date.today())
    weeks = pd.date_range("2015-01-04", last, freq="W-SUN")
    asof = datetime.now(timezone.utc)
    days = pd.date_range(end=pd.Timestamp(asof.date()), periods=BEAT_DAYS, freq="D")
    paths = sorted((OUT / args.region).glob("*/*/daily/sources_terms_daily.parquet"))
    dirs = {p.parents[1].name: p.parents[1] for p in paths}
    sub_of = {p.parents[1].name: p.parents[2].name for p in paths}
    print(f"{len(dirs)} countries, week ending {last:%Y-%m-%d}")

    nums, flags = {}, {}
    for name, cdir in dirs.items():
        nums[name] = country_numbers(cdir, weeks, days)
        hit = bursts(weekly(cdir))[0]
        flags[name] = hit.reindex(weeks, fill_value=False).astype(bool)

    subs = {}
    for c, s in sub_of.items():
        subs.setdefault(s, []).append(c)
    units = {"region": list(dirs)}
    unit_dirs = {"region": OUT / args.region / "_aggregate", **dirs}
    unit_dirs.update(
        {f"subregion:{s}": OUT / args.region / s / "_aggregate" for s in subs}
    )
    units.update({f"subregion:{s}": cs for s, cs in sorted(subs.items())})
    units.update({c: [c] for c in sorted(dirs)})

    out_units = {}
    for u, members in units.items():
        num = nums[members[0]] if len(members) == 1 else add([nums[c] for c in members])
        F = pd.concat([flags[c] for c in members], axis=1).T.groupby(level=0).any().T
        bursting = {
            c: set(flags[c].columns[flags[c].iloc[-1].to_numpy()]) for c in members
        }
        Z = baker_index(unit_dirs[u], weeks)
        run = elevated_weeks(Z)
        now = num["counts"].iloc[-1]
        persistent = [
            g
            for g in run.index[run >= MIN_ELEVATED]
            if now.get(g, 0) >= BURST_MIN and g in label
        ]
        burst = list(F.columns[F.iloc[-1 - FADE :].any().to_numpy()])
        recent = burst + [g for g in persistent if g not in set(burst)]
        N = num["counts"].reindex(columns=recent, fill_value=0)
        rs = ratios(Z, recent)
        rows, fading = [], []
        for g in recent:
            b = badge(F[g].to_numpy(), N[g].to_numpy()) if g in burst else None
            cs = num["counts"].iloc[-1].reindex(concepts.get(g, []), fill_value=0)
            row = {
                "g": g,
                "n": int(N[g].iloc[-1]),
                "r": rs[g],
                "b": b,
                "c": [
                    clabel[c]
                    for c in cs[cs > 0]
                    .sort_values(ascending=False)
                    .index[:TOP_CONCEPTS]
                ],
            }
            if row["n"] and not Z[g].iloc[-1] > 0:
                row["r"], row["u"] = [None] * len(PERIODS), 1
            if run.get(g, 0) >= MIN_ELEVATED:
                row["p"] = int(run[g])
            if len(members) > 1:
                row["in"] = sorted(c for c in members if g in bursting[c])
            faded = b and b[0] == "fade" and "p" not in row
            (fading if faded else rows).append(row)
        for lst in (rows, fading):
            covered = set().union(*[ancestors(r["g"]) for r in lst])
            lst[:] = [r for r in lst if r["g"] not in covered]
        unit = {"rows": rows, "fading": fading}
        unit["beat"] = beat(num, F, Z, set(label))
        if u == "region":
            A = num["articles"]
            unit["kpi"] = {
                "articles": int(A.iloc[-1]),
                "usual": usual_articles(A),
                "subtopics": int(F.iloc[-1].sum()),
                "countries": sum(1 for c in members if bursting[c]),
                "new": sum(
                    int((flags[c].iloc[-1] & ~flags[c].iloc[-2]).sum()) for c in members
                ),
            }
        if rows or fading or unit["beat"]["g"]:
            out_units[u] = unit

    out = {
        "region": args.region,
        "generated": f"{date.today():%Y-%m-%d}",
        "week": f"{last:%Y-%m-%d}",
        "periods": list(PERIODS),
        "asof": f"{asof:%Y-%m-%dT%H:%MZ}",
        "beat_start": f"{days[0]:%Y-%m-%d}",
        "subregions": {s: sorted(cs) for s, cs in sorted(subs.items())},
        "labels": {
            g: label.get(g, g)
            for u in out_units.values()
            for g in [r["g"] for lst in (u["rows"], u["fading"]) for r in lst]
            + list(u["beat"]["g"])
        },
        "units": out_units,
        "method": {
            "burst": "weekly count >= 2.5x expected from the previous 26 weeks' share, >= 5 articles, Poisson p < 1e-4 (per country)",
            "persistent": f"{SMOOTH}-week mean of the Baker index above {ELEVATED}x its 2024 mean for >= {MIN_ELEVATED} weeks in a row, >= {BURST_MIN} articles this week",
            "ratio": "weekly Baker index (per-source share / its 2024 std, plain mean over sources publishing in >= 50% of 2024 weeks; regions average their countries) this week / its mean over the comparison period",
        },
    }
    path = OUT / args.region / "overview.json"
    path.write_text(json.dumps(out, separators=(",", ":")))
    k = out_units["region"]["kpi"]
    print(f"region: {len(out_units['region']['rows'])} rows, kpi {k}")
    rows = [r for v in out_units.values() for r in v["rows"]]
    print(
        f"rows {len(rows)}: persistent {sum('p' in r for r in rows)}"
        f" (not bursting {sum('p' in r and not r['b'] for r in rows)}),"
        f" no ratio {sum('u' in r for r in rows)}"
    )
    print(f"{len(out_units)} units; wrote {path} ({path.stat().st_size / 1e3:.0f} KB)")


if __name__ == "__main__":
    main()
