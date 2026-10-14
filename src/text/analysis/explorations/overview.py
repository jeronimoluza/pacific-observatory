"""Overview data for the dashboard's first tab: subtopic bursts this week.

Per unit (region, subregions, countries), the subtopics (groups) bursting
this week, with:

- Burst flag: the rule of ``narratives.py`` per country (pooled weekly counts,
  >= 2.5x expected from the trailing 26-week share, >= 5 articles, Poisson
  p < 1e-4). A region or subregion row is a group bursting in >= 1 of its
  countries.
- Ratio vs usual, weekly Baker as the pipeline's weighted index (epu.py):
  X_it = group count / articles of source i in week t, sigma_i = std of X_it
  over 2024, Z_t = sum_i w_it X_it / sigma_i with w_it = source articles / unit
  articles, so Z_t = sum_i (C_it / sigma_i) / A_t. Sources with no 2024
  variation drop out, as in the pipeline. Ratio = Z this week / mean Z over a
  comparison period (2024, the 52, 26 or 8 weeks before). Sigma is always
  2024. Units sum the per-country numerators and articles, so a region pools
  all its sources (not a sum of country indices).
- N = articles mentioning the group this week. The dashboard ranks by
  N - N / ratio (articles above a usual week).
- Badge: new, peaked k weeks ago, k weeks rising, k-th week; fading rows
  (stopped bursting in the last ``FADE`` weeks) are listed apart.
- Persistence: weeks in a row (ending this week) where the ``SMOOTH``-week
  mean of Z is above ``ELEVATED`` times its 2024 mean. A group elevated for
  ``MIN_ELEVATED`` weeks with >= ``BURST_MIN`` articles this week is listed
  even when not bursting (a long crisis stops bursting once it is the usual).
- A group none of whose articles this week come from a source with 2024
  data has no ratio (``u``): Baker leaves those sources out.

Days with suspect source dumps are dropped as in ``weekly.py``. Reads each
country's ``daily/`` files (``text build --daily-history``, which writes the
per-source ``sources_terms_daily.parquet``). Writes
``outputs/text/<region>/overview.json``, read by ``small_dashboard_concepts.py``.

Run: python src/text/analysis/explorations/overview.py [--region ssa]
"""

from __future__ import annotations

import argparse
import json
from datetime import date

import numpy as np
import pandas as pd

from lead_lag import OUT
from narratives import BURST_MIN, bursts
from weekly import MASK_SHARE, MIN_WEEK, masked_days, weekly

BASE = ("2024-01-01", "2024-12-31")
PERIODS = ("2024", "52", "26", "8")  # comparison windows, weeks before this one
FADE = 3  # weeks a stopped burst stays listed as fading
TOP_CONCEPTS = 3
ELEVATED = 1.5  # x the 2024 level
SMOOTH = 4  # weeks averaged before comparing with 2024
MIN_ELEVATED = 8  # weeks in a row for a group to count as persistent


def last_week(today: date) -> pd.Timestamp:
    last = pd.Timestamp(today) - pd.Timedelta(days=1)
    return last - pd.Timedelta(days=(last.dayofweek + 1) % 7)  # back to Sunday


def week_end(d: pd.Series) -> pd.Series:
    return d + pd.to_timedelta((6 - d.dt.dayofweek) % 7, unit="D")


def country_numbers(cdir, weeks: pd.DatetimeIndex) -> dict:
    """Weekly Baker numerators, articles and counts (weeks x terms) for a country."""
    d = cdir / "daily"
    sources = pd.read_parquet(d / "sources_daily.parquet")
    bad = masked_days(sources)
    drop = set(bad[bad > MASK_SHARE].index)
    sources = sources[~sources.date.isin(drop)]
    A = (
        sources.assign(week=week_end(sources.date))
        .groupby(["week", "source_key"])
        .A_total.sum()
        .unstack(fill_value=0)
        .reindex(weeks, fill_value=0)
    )
    t = pd.read_parquet(d / "sources_terms_daily.parquet")
    t = t[~t.date.isin(drop)]
    t = (
        t.assign(week=week_end(t.date))
        .groupby(["source_key", "week", "term"], observed=True)["count"]
        .sum()
        .reset_index()
    )
    t = t[t.week.isin(weeks)]
    t["term"] = t.term.astype(str).str.replace(
        r"^(group|concept)_(.*)_A_count$", r"\2", regex=True
    )
    t["source_key"] = t.source_key.astype(str)
    t["a"] = (
        A.stack()
        .reindex(pd.MultiIndex.from_frame(t[["week", "source_key"]]))
        .to_numpy()
    )
    t["x"] = t["count"] / t["a"]

    # sigma_i per (source, term) over 2024; zero weeks (articles, no mention) count.
    in_base = (A.index >= BASE[0]) & (A.index <= BASE[1])
    n = (A[in_base] > 0).sum()
    b = t[(t.week >= BASE[0]) & (t.week <= BASE[1])]
    s = b.groupby(["source_key", "term"]).x.agg(s1="sum", s2=lambda x: (x * x).sum())
    nn = n.reindex(s.index.get_level_values("source_key")).to_numpy()
    var = (s.s2 - s.s1**2 / nn) / (nn - 1)
    sigma = np.sqrt(var.where((nn > 1) & (var > 0)))
    t = t.join(sigma.rename("sigma"), on=["source_key", "term"])
    t["c"] = t["count"] / t.sigma

    zsum = t.dropna(subset=["c"]).pivot_table(
        index="week", columns="term", values="c", aggfunc="sum", fill_value=0
    )
    counts = t.pivot_table(
        index="week", columns="term", values="count", aggfunc="sum", fill_value=0
    )
    return {
        "zsum": zsum.reindex(weeks, fill_value=0),
        "articles": A.sum(axis=1),
        "counts": counts.reindex(weeks, fill_value=0),
    }


def add(parts: list[dict]) -> dict:
    out = parts[0]
    for p in parts[1:]:
        out = {k: out[k].add(p[k], fill_value=0) for k in out}
    return out


def z_index(num: dict) -> pd.DataFrame:
    """Weekly Baker Z (weeks x groups): standardized counts / unit articles."""
    A = num["articles"]
    return num["zsum"].div(A.where(A >= MIN_WEEK), axis=0)


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


def elevated_weeks(Z: pd.DataFrame) -> pd.Series:
    """Weeks in a row, ending this week, with smoothed Z above ELEVATED x 2024."""
    base = Z.loc[BASE[0] : BASE[1]].mean()
    up = (
        Z.rolling(SMOOTH, min_periods=SMOOTH).mean().gt(ELEVATED * base.where(base > 0))
    )
    U = up.to_numpy(dtype=bool)[::-1]
    run = np.where(U.all(axis=0), len(U), np.argmax(~U, axis=0))
    return pd.Series(run, index=Z.columns)


def usual_articles(A: pd.Series) -> list[float]:
    past = A.iloc[:-1]
    return [round(float(past.loc[BASE[0] : BASE[1]].mean()), 1)] + [
        round(float(past.iloc[-int(p) :].mean()), 1) for p in PERIODS[1:]
    ]


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
    paths = sorted((OUT / args.region).glob("*/*/daily/sources_terms_daily.parquet"))
    dirs = {p.parents[1].name: p.parents[1] for p in paths}
    sub_of = {p.parents[1].name: p.parents[2].name for p in paths}
    print(f"{len(dirs)} countries, week ending {last:%Y-%m-%d}")

    nums, flags = {}, {}
    for name, cdir in dirs.items():
        nums[name] = country_numbers(cdir, weeks)
        hit = bursts(weekly(cdir))[0]
        flags[name] = hit.reindex(weeks, fill_value=False).astype(bool)

    subs = {}
    for c, s in sub_of.items():
        subs.setdefault(s, []).append(c)
    units = {"region": list(dirs)}
    units.update({f"subregion:{s}": cs for s, cs in sorted(subs.items())})
    units.update({c: [c] for c in sorted(dirs)})

    out_units = {}
    for u, members in units.items():
        num = nums[members[0]] if len(members) == 1 else add([nums[c] for c in members])
        F = pd.concat([flags[c] for c in members], axis=1).T.groupby(level=0).any().T
        bursting = {
            c: set(flags[c].columns[flags[c].iloc[-1].to_numpy()]) for c in members
        }
        Z = z_index(num)
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
        if rows or fading:
            out_units[u] = unit

    out = {
        "region": args.region,
        "generated": f"{date.today():%Y-%m-%d}",
        "week": f"{last:%Y-%m-%d}",
        "periods": list(PERIODS),
        "subregions": {s: sorted(cs) for s, cs in sorted(subs.items())},
        "labels": {
            g: label.get(g, g)
            for u in out_units.values()
            for lst in (u["rows"], u["fading"])
            for g in [r["g"] for r in lst]
        },
        "units": out_units,
        "method": {
            "burst": "weekly count >= 2.5x expected from the previous 26 weeks' share, >= 5 articles, Poisson p < 1e-4 (per country)",
            "persistent": f"{SMOOTH}-week mean of the Baker index above {ELEVATED}x its 2024 mean for >= {MIN_ELEVATED} weeks in a row, >= {BURST_MIN} articles this week",
            "ratio": "weekly Baker index (per-source share / its 2024 std, article-weighted across sources) this week / its mean over the comparison period",
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
